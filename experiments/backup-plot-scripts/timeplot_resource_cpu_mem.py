#!/usr/bin/env python3
# timeplot_resource_cpu_mem.py
# Layout:
#   Left column  : CPU over time (TL=Consumer, BL=Provider)
#   Right column : Memory over time (TR=Consumer, BR=Provider)
# Each panel shows 6 lines: Clique 10/20/30 and QBFT 10/20/30.
# Shared X across all panels; shared Y per column (CPU column aligned; Memory column aligned).

from pathlib import Path
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np

CSV_PATH = Path("multiple-offers/_summary/resource_usage_time_by_role.csv")

CONSENSUS_ORDER = ["clique", "qbft"]
COUNT_ORDER     = [4, 10, 20, 30]
ROLE_ORDER      = ["consumer", "provider"]

COLOR     = {"clique": "#1f77b4", "qbft": "#ff7f0e"}
LINESTYLE = {4: "-", 10: "--", 20: "-.", 30: ":"}

# ---- noise/coverage controls ----
MIN_COVERAGE_FRAC = 0.80   # keep seconds with >= 80% of max coverage for that line
SMOOTH_WINDOW_S   = 7      # rolling-median window (seconds) after interpolation
INTERPOLATE_GAPS  = True   # fill missing seconds linearly before smoothing

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    for key in ("consensus", "mec_count", "role", "elapsed_s", "files", "aggregation", "nodes"):
        if key not in df.columns and f"{key}_" in df.columns:
            df = df.rename(columns={f"{key}_": key})
    return df

def _pick_series(df: pd.DataFrame, candidates):
    for name in candidates:
        if name in df.columns:
            return df.loc[:, [name]].iloc[:, 0]
    return None

def _prefer_aggregation(df: pd.DataFrame) -> pd.DataFrame:
    if "aggregation" not in df.columns:
        return df
    if (df["aggregation"] == "per_node_median").any():
        return df[df["aggregation"] == "per_node_median"].copy()
    if (df["aggregation"] == "per_run").any():
        return df[df["aggregation"] == "per_run"].copy()
    return df

def _prepare_metric_df(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    if metric == "cpu":
        src = _pick_series(df, ["cpu_percent_median_smooth", "cpu_percent_median", "cpu_percent_mean"])
        if src is None:
            raise SystemExit("No CPU columns found (expected *_median_smooth/_median/_mean).")
        df = df.copy()
        df["y"] = pd.to_numeric(src, errors="coerce") / 100.0  # % -> vCPUs
        df["ylabel"] = "CPU usage (vCPUs)"
    else:
        src = _pick_series(df, ["mem_mb_median_smooth", "mem_mb_median", "mem_mb_mean"])
        if src is None:
            raise SystemExit("No Memory columns found (expected *_median_smooth/_median/_mean).")
        df = df.copy()
        df["y"] = pd.to_numeric(src, errors="coerce")
        df["ylabel"] = "Memory usage (MB)"
    return df

def _coverage_col(df: pd.DataFrame) -> str:
    if "nodes" in df.columns: return "nodes"
    if "files" in df.columns: return "files"
    return ""

def _filter_by_coverage_and_align(df_metric: pd.DataFrame, role: str) -> pd.DataFrame:
    d = df_metric.copy()
    d["consensus"] = d["consensus"].astype(str).str.lower()
    d = d[d["consensus"].isin(CONSENSUS_ORDER)]
    d["mec_count"] = pd.to_numeric(d["mec_count"], errors="coerce").astype("Int64")
    d = d[d["mec_count"].isin(COUNT_ORDER)]
    d["role"] = d["role"].astype(str).str.lower()
    d = d[d["role"] == role].copy()
    d["elapsed_s"] = pd.to_numeric(d["elapsed_s"], errors="coerce").astype("Int64")
    d = d.dropna(subset=["elapsed_s"]).copy()
    d["elapsed_s"] = d["elapsed_s"].astype(int)
    if d.empty:
        return d

    cov_col = _coverage_col(d)
    if cov_col:
        max_cov = (
            d.groupby(["consensus", "mec_count"], as_index=False)[cov_col]
              .max().rename(columns={cov_col: "cov_max"})
        )
        d = d.merge(max_cov, on=["consensus", "mec_count"], how="left")
        d["cov_thresh"] = np.ceil(d["cov_max"] * MIN_COVERAGE_FRAC)
        d = d[d[cov_col] >= d["cov_thresh"]].copy()
        d.drop(columns=["cov_max", "cov_thresh"], inplace=True, errors="ignore")

    per_line_max = (
        d.groupby(["consensus", "mec_count"], as_index=False)["elapsed_s"].max()
         .rename(columns={"elapsed_s": "tmax"})
    )
    if per_line_max.empty:
        return d
    T_end = int(per_line_max["tmax"].min())
    d = d[d["elapsed_s"] <= T_end].copy()

    rows = []
    for (cons, n), g in d.groupby(["consensus", "mec_count"]):
        g = g.sort_values("elapsed_s").copy()
        full_idx = pd.RangeIndex(start=0, stop=T_end + 1, step=1)  # normalized to 0..T_end
        g = g.set_index("elapsed_s")
        y = g["y"].reindex(full_idx)
        if INTERPOLATE_GAPS:
            y = y.interpolate(method="linear", limit_direction="both")
        if SMOOTH_WINDOW_S and SMOOTH_WINDOW_S > 1:
            y = y.rolling(window=SMOOTH_WINDOW_S, center=True, min_periods=1).median()
        rows.append(pd.DataFrame({
            "consensus": cons,
            "mec_count": int(n),
            "role": role,
            "elapsed_s": full_idx.astype(int),
            "y": y.values
        }))
    return pd.concat(rows, ignore_index=True)

def _plot_panel(ax, df_lines: pd.DataFrame, title: str, ylabel: str, show_xlabel: bool, legend_loc: str):
    for cons in CONSENSUS_ORDER:
        for n in COUNT_ORDER:
            line = df_lines[(df_lines["consensus"] == cons) & (df_lines["mec_count"] == n)]
            if line.empty:
                continue
            ax.plot(
                line["elapsed_s"].to_numpy(),
                line["y"].to_numpy(),
                color=COLOR[cons],
                linestyle=LINESTYLE[n],
                linewidth=2.0,
                label=f"{cons.capitalize()} - {n} MECs",
            )
    ax.set_title(title if title else "")
    ax.set_ylabel(ylabel if ylabel else "")
    ax.set_xlabel("Time (s)" if show_xlabel else "")
    ax.grid(True, which="both", axis="both", linestyle="--", color="grey", alpha=0.5)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_color("black")
        ax.spines[side].set_linewidth(1.0)

    leg = ax.legend(loc=legend_loc, frameon=True, title=None, ncol=1, fancybox=True)
    leg.get_frame().set_edgecolor("black")
    leg.get_frame().set_linewidth(1.0)

def main():
    df = pd.read_csv(CSV_PATH)
    df = _normalize_columns(df)
    df = _prefer_aggregation(df)

    for key in ("consensus", "mec_count", "role", "elapsed_s"):
        if key not in df.columns:
            raise SystemExit(f"Missing required column: {key}")

    # Prepare metric frames
    df_cpu = _prepare_metric_df(df, metric="cpu")
    df_mem = _prepare_metric_df(df, metric="mem")

    # Split by role and align/denoise
    cpu_consumer = _filter_by_coverage_and_align(df_cpu, role="consumer")
    cpu_provider = _filter_by_coverage_and_align(df_cpu, role="provider")
    mem_consumer = _filter_by_coverage_and_align(df_mem, role="consumer")
    mem_provider = _filter_by_coverage_and_align(df_mem, role="provider")

    # Global shared X (0 .. min common end across all four)
    ends = []
    for d in (cpu_consumer, cpu_provider, mem_consumer, mem_provider):
        if not d.empty:
            ends.append(int(d["elapsed_s"].max()))
    x_end = min(ends) if ends else 0

    # Column-aligned Y limits (CPU column, Memory column)
    def _ymax(d1, d2):
        vals = []
        for d in (d1, d2):
            if not d.empty:
                vals.append(np.nanmax(d["y"].to_numpy()))
        m = np.nanmax(vals) if len(vals) else np.nan
        return float(m * 1.05) if np.isfinite(m) else None

    cpu_ylim = _ymax(cpu_consumer, cpu_provider)
    mem_ylim = _ymax(mem_consumer, mem_provider)

    sns.set_theme(context="paper", style="ticks")
    sns.set_context("paper", font_scale=1.35)

    fig, axes = plt.subplots(
        2, 2, figsize=(13.0, 8.8),
        sharex=True,
        gridspec_kw={"wspace": 0.2, "hspace": 0.1}
    )

    ax_tl, ax_tr = axes[0]
    ax_bl, ax_br = axes[1]

    # ----- LEFT COLUMN: CPU -----
    _plot_panel(ax_tl, cpu_consumer, title=None, ylabel="Consumer CPU usage (vCPUs)",
                show_xlabel=False, legend_loc="upper right")
    _plot_panel(ax_bl, cpu_provider, title=None, ylabel="Provider CPU usage (vCPUs)",
                show_xlabel=True,  legend_loc="upper right")

    if cpu_ylim is not None:
        ax_tl.set_ylim(0, cpu_ylim)
        ax_bl.set_ylim(0, cpu_ylim)

    # ----- RIGHT COLUMN: MEMORY -----
    _plot_panel(ax_tr, mem_consumer, title=None, ylabel="Consumer memory usage (MB)",
                show_xlabel=False, legend_loc="lower right")
    _plot_panel(ax_br, mem_provider, title=None, ylabel="Provider memory usage (MB)",
                show_xlabel=True,  legend_loc="lower right")

    if mem_ylim is not None:
        ax_tr.set_ylim(0, mem_ylim)
        ax_br.set_ylim(0, mem_ylim)

    for ax in (ax_tl, ax_tr, ax_bl, ax_br):
        ax.set_xlim(0, x_end)

    plt.show()

    out = Path("plots"); out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "time_by_role_4panels.pdf", dpi=300, bbox_inches="tight")

if __name__ == "__main__":
    main()
