#!/usr/bin/env python3
"""
Summarize resource usage (mean, std, max) from docker-logs only,
emit boxplot-friendly stats (Q1/median/Q3) of per-run means,
and also produce role-level time series with a robust, low-noise variant.

Run from: experiments/multiple-offers/

Scans:
  {clique,qbft}/*-mecs/docker-logs/*.csv

Each CSV columns expected:
  timestamp,cpu_percent,mem_mb,mem_limit_mb,mem_percent,
  blk_read_mb,blk_write_mb,net_rx_mb,net_tx_mb

Outputs:
  ./_summary/resource_usage_per_run.csv
  ./_summary/resource_usage_overall.csv
      - legacy columns preserved (e.g., cpu_percent_mean, cpu_percent_std, cpu_percent_max)
      - boxplot columns: <metric>_mean_median, <metric>_mean_q1, <metric>_mean_q3
      - NEW: duplicates rows with aggregation in {per_run, per_node_median}
  ./_summary/resource_usage_overall_per_role.csv
      - same structure as "overall", split by role={consumer,provider}
      - NEW: aggregation in {per_run, per_node_median}
  ./_summary/resource_usage_time_by_role.csv
      - time series for each (consensus, mec_count, role, elapsed_s)
      - contains both aggregation variants:
          * per_run: <metric>_mean, <metric>_std (as before)
          * per_node_median: <metric>_median, <metric>_q1, <metric>_q3, <metric>_median_smooth
      - columns: consensus,mec_count,role,elapsed_s,files,aggregation[,nodes,rolling_window_s]
"""

from pathlib import Path
import re
import pandas as pd
import numpy as np
import argparse

ROOT = Path(".").resolve()
SUMMARY_DIR = ROOT / "_summary"
SUMMARY_DIR.mkdir(exist_ok=True)

# ------- tunables -------
GLOB_PATTERN = "**/docker-logs/*.csv"
ROLLING_WINDOW_S = 5  # smoothing window for the low-noise time series

METRIC_COLS = [
    "cpu_percent",
    "mem_mb",
    "blk_read_mb",
    "blk_write_mb",
    "net_rx_mb",
    "net_tx_mb",
]

# Parse filenames like validator1_run_3.csv (node name may be non-numeric)
re_file = re.compile(r"(?P<node>[^/\\]+)_run_(?P<run>\d+)\.csv$", re.IGNORECASE)


def extract_context(csv_path: Path):
    # .../multiple-offers/{consensus}/{N-mecs}/docker-logs/file.csv
    consensus = csv_path.parts[-4]
    mec_dir = csv_path.parts[-3]
    m = re.search(r"(\d+)-mecs", mec_dir)
    mec_count = int(m.group(1)) if m else np.nan

    fm = re_file.search(csv_path.name)
    node = fm.group("node") if fm else csv_path.stem
    run = int(fm.group("run")) if fm else np.nan
    return consensus, mec_count, node, run


def summarize_file(csv_path: Path):
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return None, f"read-failed: {e}"

    needed = ["timestamp"] + METRIC_COLS
    missing = [c for c in needed if c not in df.columns]
    if missing:
        return None, f"missing-cols: {missing}"

    # Sort by time just in case
    df = df.sort_values("timestamp", kind="stable")

    # Convert all metrics to numeric and compute per-file stats
    metrics = {}
    for col in METRIC_COLS:
        s = pd.to_numeric(df[col], errors="coerce")
        metrics[f"{col}_mean"] = float(s.mean()) if s.notna().any() else np.nan
        metrics[f"{col}_std"]  = float(s.std(ddof=1)) if s.notna().sum() > 1 else np.nan
        metrics[f"{col}_max"]  = float(s.max()) if s.notna().any() else np.nan

    metrics["samples"] = int(len(df))
    return metrics, None


# ---------- quantile helpers & column flattener ----------

def q1(s):
    s = pd.to_numeric(s, errors="coerce")
    return float(s.quantile(0.25))
q1.__name__ = "q1"

def q3(s):
    s = pd.to_numeric(s, errors="coerce")
    return float(s.quantile(0.75))
q3.__name__ = "q3"

def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Turn MultiIndex columns from .agg([...]) into flat 'col_func' names,
    but preserve groupers (where the func-level is ''/None).
    """
    out = df.copy()
    if not isinstance(out.columns, pd.MultiIndex):
        # Nothing to do
        return out

    new_cols = []
    for c in out.columns:
        if not isinstance(c, tuple):
            new_cols.append(str(c))
            continue
        top, bot = c
        # preserve groupers (bot empty/None)
        if bot in (None, "",):
            new_cols.append(str(top))
        else:
            func_name = bot if isinstance(bot, str) and bot else getattr(bot, "__name__", str(bot))
            new_cols.append(f"{top}_{func_name}")
    out.columns = new_cols
    return out



# ---------- role split helper (80/20, at least 1 provider) ----------

def consumers_for(mec_count: int) -> int:
    """
    Infer number of consumers for a given mec_count using your 80/20 split.
    Ensures at least 1 provider:
      4  -> 3/1, 10 -> 8/2, 20 -> 16/4, 30 -> 24/6, etc.
    """
    mec_count = int(mec_count)
    providers = max(1, mec_count // 5)
    return mec_count - providers

def role_for_node(node_name: str, mec_count: int) -> str:
    """Resolve role from node name like 'validator1' using 80/20 split."""
    m = re.search(r"(\d+)$", str(node_name))
    if not m:
        return ""  # unknown; caller may skip
    idx = int(m.group(1))
    return "consumer" if idx <= consumers_for(mec_count) else "provider"


# ---------- time-by-role builders ----------

def _build_per_run_time_series(files):
    """
    Original behavior: per-file per-second averages, then across files:
      <metric>_mean and <metric>_std for each (consensus,mec_count,role,elapsed_s).
    """
    rows = []
    skipped = 0

    for f in files:
        consensus, mec_count, node, run = extract_context(f)
        role = role_for_node(node, mec_count)
        if not role:
            skipped += 1
            continue

        try:
            df = pd.read_csv(f, usecols=["timestamp"] + METRIC_COLS)
        except Exception:
            skipped += 1
            continue
        if df.empty:
            continue

        df = df.sort_values("timestamp", kind="stable")
        t0s = pd.to_numeric(df["timestamp"], errors="coerce").dropna()
        if t0s.empty:
            continue
        t0 = int(t0s.iloc[0])

        df["elapsed_s"] = ((pd.to_numeric(df["timestamp"], errors="coerce") - t0) / 1000.0).round().astype("Int64")
        df = df.dropna(subset=["elapsed_s"]).copy()
        df["elapsed_s"] = df["elapsed_s"].astype(int)

        for m in METRIC_COLS:
            df[m] = pd.to_numeric(df[m], errors="coerce")

        gb = df.groupby("elapsed_s", as_index=False)[METRIC_COLS].mean()
        gb["consensus"] = consensus
        gb["mec_count"] = int(mec_count) if pd.notna(mec_count) else mec_count
        gb["role"] = role
        gb["file"] = str(f)
        gb["node"] = node
        gb["run"] = run

        rows.append(gb)

    if not rows:
        if skipped:
            print(f"[warn] per-run time series: all files skipped ({skipped} skipped).")
        return pd.DataFrame(columns=["consensus","mec_count","role","elapsed_s","files","aggregation"])

    ts = pd.concat(rows, ignore_index=True)

    agg = {"file": "nunique"}
    for m in METRIC_COLS:
        agg[m] = ["mean", "std"]

    out = (
        ts.groupby(["consensus", "mec_count", "role", "elapsed_s"], as_index=False)
          .agg(agg)
    )
    out = _flatten_columns(out).rename(columns={"file_nunique": "files"})
    out["aggregation"] = "per_run"

    # dtypes
    for col in ("mec_count", "elapsed_s"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")

    sort_cols = [c for c in ["consensus", "mec_count", "role", "elapsed_s"] if c in out.columns]
    if sort_cols:
        out = out.sort_values(sort_cols)

    return out


def _build_low_noise_time_series(files, rolling_window_s: int = ROLLING_WINDOW_S):
    """
    Low-noise variant:
      1) Per file -> per-second mean (as above)
      2) For each node: median across its runs per elapsed_s
      3) Across nodes: median/Q1/Q3 per elapsed_s
      4) Optional rolling median smoothing on the node-median series
    Outputs columns: <metric>_median, <metric>_q1, <metric>_q3, <metric>_median_smooth
    """
    per_file = []

    for f in files:
        consensus, mec_count, node, run = extract_context(f)
        role = role_for_node(node, mec_count)
        if not role:
            continue

        try:
            df = pd.read_csv(f, usecols=["timestamp"] + METRIC_COLS)
        except Exception:
            continue
        if df.empty:
            continue

        df = df.sort_values("timestamp", kind="stable")
        t0s = pd.to_numeric(df["timestamp"], errors="coerce").dropna()
        if t0s.empty:
            continue
        t0 = int(t0s.iloc[0])

        df["elapsed_s"] = ((pd.to_numeric(df["timestamp"], errors="coerce") - t0) / 1000.0).round().astype("Int64")
        df = df.dropna(subset=["elapsed_s"]).copy()
        df["elapsed_s"] = df["elapsed_s"].astype(int)
        for m in METRIC_COLS:
            df[m] = pd.to_numeric(df[m], errors="coerce")

        gb = df.groupby("elapsed_s", as_index=False)[METRIC_COLS].mean()
        gb["consensus"] = consensus
        gb["mec_count"] = int(mec_count) if pd.notna(mec_count) else mec_count
        gb["role"] = role
        gb["node"] = node
        gb["run"] = run
        per_file.append(gb)

    if not per_file:
        return pd.DataFrame(columns=["consensus","mec_count","role","elapsed_s","files","aggregation","nodes"])

    pf = pd.concat(per_file, ignore_index=True)

    # Step 2: per-node median across runs at each second
    per_node = (
        pf.groupby(["consensus","mec_count","role","node","elapsed_s"], as_index=False)[METRIC_COLS]
          .median()
    )

    # Step 3: across nodes at each second -> median/Q1/Q3
    agg = {"node": "nunique"}
    for m in METRIC_COLS:
        agg[m] = ["median", q1, q3]

    across_nodes = (
        per_node.groupby(["consensus","mec_count","role","elapsed_s"])
                .agg(agg)
                .reset_index()
    )
    across_nodes = _flatten_columns(across_nodes)

    # safety: if any grouper accidentally became '<name>_', map it back
    for key in ("consensus","mec_count","role","elapsed_s"):
        alt = f"{key}_"
        if key not in across_nodes.columns and alt in across_nodes.columns:
            across_nodes = across_nodes.rename(columns={alt: key})

    across_nodes = across_nodes.rename(columns={"node_nunique": "nodes"})
    across_nodes["files"] = across_nodes["nodes"]   # keep 'files' meaning “#sources”
    across_nodes["aggregation"] = "per_node_median"

    # Step 4: rolling median smoothing on medians (optional)
    def _smooth(group: pd.DataFrame) -> pd.DataFrame:
        g = group.sort_values("elapsed_s").copy()
        g["rolling_window_s"] = rolling_window_s
        for m in METRIC_COLS:
            med_col = f"{m}_median"
            if med_col in g.columns:
                g[f"{m}_median_smooth"] = (
                    g[med_col].rolling(window=max(1, rolling_window_s),
                                       center=True, min_periods=1).median()
                )
        return g

    out = across_nodes.groupby(["consensus","mec_count","role"], group_keys=False).apply(_smooth)

    # dtypes (safe-cast where present)
    for col in ("mec_count", "elapsed_s", "nodes", "files", "rolling_window_s"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")

    sort_cols = [c for c in ["consensus", "mec_count", "role", "elapsed_s"] if c in out.columns]
    if sort_cols:
        out = out.sort_values(sort_cols)

    return out


def _select_per_run_columns(df: pd.DataFrame) -> pd.DataFrame:
    """For per-run aggregation rows, keep canonical columns and order."""
    base = ["consensus","mec_count","role","samples","runs","nodes","files","aggregation"]
    keep = set(base)
    ordered = list(base)

    for m in METRIC_COLS:
        # legacy/simple stats
        for c in (f"{m}_mean", f"{m}_std", f"{m}_max"):
            if c in df.columns:
                keep.add(c); ordered.append(c)
        # boxplot stats over per-run means
        for c in (f"{m}_mean_median", f"{m}_mean_q1", f"{m}_mean_q3"):
            if c in df.columns:
                keep.add(c); ordered.append(c)

    sub = df[[c for c in ordered if c in df.columns]].copy()
    # sort for readability
    return sub.sort_values(["consensus","mec_count","aggregation"])

def _rename_per_node_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    For per-node aggregation, map:
      <metric>_mean_mean   -> <metric>_mean   (mean across nodes of node-median)
      <metric>_mean_std    -> <metric>_std    (std across nodes)
      <metric>_mean_median -> <metric>_median (median across nodes)
      <metric>_mean_q1     -> <metric>_q1
      <metric>_mean_q3     -> <metric>_q3
    """
    out = df.copy()
    for m in METRIC_COLS:
        out = out.rename(columns={
            f"{m}_mean_mean":   f"{m}_mean",
            f"{m}_mean_std":    f"{m}_std",
            f"{m}_mean_median": f"{m}_median",
            f"{m}_mean_q1":     f"{m}_q1",
            f"{m}_mean_q3":     f"{m}_q3",
        })
    return out

def _select_per_node_columns(df: pd.DataFrame) -> pd.DataFrame:
    """For per-node aggregation rows, keep only the clean, low-noise columns."""
    base = ["consensus","mec_count","role","samples","runs","nodes","files","aggregation"]
    keep = set(base)
    ordered = list(base)
    for m in METRIC_COLS:
        for c in (f"{m}_mean", f"{m}_std", f"{m}_median", f"{m}_q1", f"{m}_q3"):
            if c in df.columns:
                keep.add(c); ordered.append(c)
    sub = df[[c for c in ordered if c in df.columns]].copy()
    return sub.sort_values(["consensus","mec_count","aggregation"])


def parse_args():
    p = argparse.ArgumentParser(description="Summarize docker-logs resource usage.")
    p.add_argument(
        "--agg",
        choices=["per_node", "per_run", "both"],
        default="per_node",
        help="Aggregation to write into the *_overall*.csv and time series. "
             "'per_node' = low-noise (default), 'per_run' = legacy, 'both' = write both."
    )
    p.add_argument(
        "--rolling",
        type=int,
        default=ROLLING_WINDOW_S,
        help=f"Rolling window (seconds) for per-node low-noise time series (default {ROLLING_WINDOW_S})."
    )
    return p.parse_args()

# ---------- main ----------

def main():
    args = parse_args()

    files = sorted(ROOT.glob(GLOB_PATTERN))
    if not files:
        print("No docker-logs CSVs found.")
        return 0

    rows = []
    errors = []

    for f in files:
        consensus, mec_count, node, run = extract_context(f)
        row, err = summarize_file(f)
        if row is None:
            errors.append((str(f), err))
            continue
        row.update({
            "consensus": consensus,
            "mec_count": mec_count,
            "node": node,   # keep as string; may be "validator1"
            "run": run,
            "file": str(f),
        })
        rows.append(row)

    if not rows:
        print("No valid CSVs summarized.")
        for path, err in errors:
            print(f"[skip] {path} -> {err}")
        return 2

    per_run_df = pd.DataFrame(rows)
    # Reorder columns for readability
    order = ["consensus","mec_count","node","run","samples"]
    for m in METRIC_COLS:
        order += [f"{m}_mean", f"{m}_std", f"{m}_max"]
    order += ["file"]
    per_run_df = per_run_df[order].sort_values(["consensus","mec_count","run","node"])

    out_per_run = SUMMARY_DIR / "resource_usage_per_run.csv"
    per_run_df.to_csv(out_per_run, index=False)
    print(f"Wrote {out_per_run} ({len(per_run_df)} rows)")

    # -------- Overall summary per (consensus, mec_count) --------
    # A) per_run aggregation
    agg_map = {
        "samples": "sum",
        "run": "nunique",
        "node": "nunique",
        "file": "count",
    }
    for m in METRIC_COLS:
        agg_map[f"{m}_mean"] = ["mean", "median", q1, q3]
        agg_map[f"{m}_std"]  = ["mean"]
        agg_map[f"{m}_max"]  = ["max"]

    overall_per_run = (
        per_run_df
        .groupby(["consensus","mec_count"], as_index=False)
        .agg(agg_map)
    )
    overall_per_run = _flatten_columns(overall_per_run)
    overall_per_run = overall_per_run.rename(columns={
        "samples_sum": "samples",
        "run_nunique": "runs",
        "node_nunique": "nodes",
        "file_count": "files",
    })
    for m in METRIC_COLS:
        if f"{m}_mean_mean" in overall_per_run: overall_per_run[f"{m}_mean"] = overall_per_run[f"{m}_mean_mean"]
        if f"{m}_std_mean"  in overall_per_run: overall_per_run[f"{m}_std"]  = overall_per_run[f"{m}_std_mean"]
        if f"{m}_max_max"   in overall_per_run: overall_per_run[f"{m}_max"]  = overall_per_run[f"{m}_max_max"]
    overall_per_run["aggregation"] = "per_run"

    # B) per_node_median aggregation (low-noise)
    mean_cols = [c for c in per_run_df.columns if c.endswith("_mean")]
    per_node_means = (
        per_run_df
        .groupby(["consensus","mec_count","node"], as_index=False)[mean_cols]
        .median()
    )
    node_overall = (
        per_node_means
        .groupby(["consensus","mec_count"], as_index=False)[mean_cols]
        .agg(["mean","std","median", q1, q3])
    )
    node_overall = _flatten_columns(node_overall)
    counts = (
        per_run_df.groupby(["consensus","mec_count"], as_index=False)
                  .agg(samples=("samples","sum"),
                       runs=("run","nunique"),
                       nodes=("node","nunique"),
                       files=("file","count"))
    )
    overall_node = counts.merge(node_overall, on=["consensus","mec_count"], how="right")
    overall_node["aggregation"] = "per_node_median"

    # Choose which overall to write
    if args.agg == "per_run":
        overall_to_write = _select_per_run_columns(overall_per_run)
    elif args.agg == "per_node":
        overall_to_write = _select_per_node_columns(_rename_per_node_columns(overall_node))
    else:  # both
        overall_to_write = pd.concat(
            [
                _select_per_run_columns(overall_per_run),
                _select_per_node_columns(_rename_per_node_columns(overall_node)),
            ],
            ignore_index=True,
        )

    out_overall = SUMMARY_DIR / "resource_usage_overall.csv"
    overall_to_write.to_csv(out_overall, index=False)
    print(f"Wrote {out_overall} ({len(overall_to_write)} rows)")

    if errors:
        print(f"Completed with {len(errors)} skipped files. First 10:")
        for p, e in errors[:10]:
            print(f"[skip] {p} -> {e}")

    # -------- Per-role overall summary (consumer vs provider) --------
    per_role_df = per_run_df.copy()
    per_role_df["mec_count"] = per_role_df["mec_count"].astype(int)
    per_role_df["node_idx"] = per_role_df["node"].astype(str).str.extract(r"(\d+)$", expand=False)
    bad = per_role_df["node_idx"].isna().sum()
    if bad:
        print(f"[warn] {bad} rows have non-numeric node names; skipping those for per-role summary.")
        per_role_df = per_role_df.dropna(subset=["node_idx"]).copy()
    per_role_df["node_idx"] = per_role_df["node_idx"].astype(int)
    per_role_df["role"] = per_role_df.apply(
        lambda r: "consumer" if r["node_idx"] <= consumers_for(r["mec_count"]) else "provider",
        axis=1
    )

    # per_run per-role
    agg_map_role = {
        "samples": "sum",
        "run": "nunique",
        "node": "nunique",
        "file": "count",
    }
    for m in METRIC_COLS:
        agg_map_role[f"{m}_mean"] = ["mean", "median", q1, q3]
        agg_map_role[f"{m}_std"]  = ["mean"]
        agg_map_role[f"{m}_max"]  = ["max"]

    overall_role_per_run = (
        per_role_df
        .groupby(["consensus","mec_count","role"], as_index=False)
        .agg(agg_map_role)
    )
    overall_role_per_run = _flatten_columns(overall_role_per_run).rename(columns={
        "samples_sum": "samples",
        "run_nunique": "runs",
        "node_nunique": "nodes",
        "file_count": "files",
    })
    for m in METRIC_COLS:
        if f"{m}_mean_mean" in overall_role_per_run: overall_role_per_run[f"{m}_mean"] = overall_role_per_run[f"{m}_mean_mean"]
        if f"{m}_std_mean"  in overall_role_per_run: overall_role_per_run[f"{m}_std"]  = overall_role_per_run[f"{m}_std_mean"]
        if f"{m}_max_max"   in overall_role_per_run: overall_role_per_run[f"{m}_max"]  = overall_role_per_run[f"{m}_max_max"]
    overall_role_per_run["aggregation"] = "per_run"

    # per_node per-role
    mean_cols_role = [c for c in per_role_df.columns if c.endswith("_mean")]
    per_node_role = (
        per_role_df
        .groupby(["consensus","mec_count","role","node"], as_index=False)[mean_cols_role]
        .median()
    )
    node_overall_role = (
        per_node_role
        .groupby(["consensus","mec_count","role"], as_index=False)[mean_cols_role]
        .agg(["mean","std","median", q1, q3])
    )
    node_overall_role = _flatten_columns(node_overall_role)
    counts_role = (
        per_role_df.groupby(["consensus","mec_count","role"], as_index=False)
                   .agg(samples=("samples","sum"),
                        runs=("run","nunique"),
                        nodes=("node","nunique"),
                        files=("file","count"))
    )
    overall_role_node = counts_role.merge(node_overall_role, on=["consensus","mec_count","role"], how="right")
    overall_role_node["aggregation"] = "per_node_median"

    # Choose which per-role to write
    if args.agg == "per_run":
        per_role_to_write = _select_per_run_columns(overall_role_per_run)
    elif args.agg == "per_node":
        per_role_to_write = _select_per_node_columns(_rename_per_node_columns(overall_role_node))
    else:
        per_role_to_write = pd.concat(
            [
                _select_per_run_columns(overall_role_per_run),
                _select_per_node_columns(_rename_per_node_columns(overall_role_node)),
            ],
            ignore_index=True,
        )

    out_overall_per_role = SUMMARY_DIR / "resource_usage_overall_per_role.csv"
    per_role_to_write.to_csv(out_overall_per_role, index=False)
    print(f"Wrote {out_overall_per_role} ({len(per_role_to_write)} rows)")

    # -------- Role-level time series across all runs --------
    ts_per_run   = _build_per_run_time_series(files)
    ts_low_noise = _build_low_noise_time_series(files, rolling_window_s=args.rolling)

    if args.agg == "per_run":
        ts_out = ts_per_run
    elif args.agg == "per_node":
        ts_out = ts_low_noise
    else:
        ts_out = pd.concat([ts_per_run, ts_low_noise], ignore_index=True)

    out_time = SUMMARY_DIR / "resource_usage_time_by_role.csv"
    ts_out.to_csv(out_time, index=False)
    print(f"Wrote {out_time} ({len(ts_out)} rows)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())