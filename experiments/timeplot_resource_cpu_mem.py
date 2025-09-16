#!/usr/bin/env python3
# timeplot_resource_cpu_mem.py
# 4 panels: Consumer CPU (TL), Provider CPU (TR), Consumer Mem (BL), Provider Mem (BR).
# Each panel shows 6 lines: Clique 10/20/30 and QBFT 10/20/30.
# Legends: upper-left in every panel.
# X label "Time (s)" only on the lower panels.

from pathlib import Path
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np

CSV_PATH = Path("multiple-offers/_summary/resource_usage_time_by_role.csv")

CONSENSUS_ORDER = ["clique", "qbft"]
COUNT_ORDER     = [10, 20, 30]
ROLE_ORDER      = ["consumer", "provider"]

COLOR     = {"clique": "#1f77b4", "qbft": "#ff7f0e"}
LINESTYLE = {10: "-", 20: "--", 30: ":"}

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
        df["ylabel"] = "CPU (vCPUs)"
    else:
        src = _pick_series(df, ["mem_mb_median_smooth", "mem_mb_median", "mem_mb_mean"])
        if src is None:
            raise SystemExit("No Memory columns found (expected *_median_smooth/_median/_mean).")
        df = df.copy()
        df["y"] = pd.to_numeric(src, errors="coerce")
        df["ylabel"] = "Memory (MB)"
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
        t0 = int(g["elapsed_s"].min())
        start_t = 0 if t0 == 0 else t0
        full_idx = pd.RangeIndex(start=start_t, stop=T_end + 1, step=1)
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


def _plot_panel(ax, df_lines: pd.DataFrame, title: str, ylabel: str, show_xlabel: bool):
    # draw each line
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
                label=f"{cons.capitalize()} {n}",
            )

    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Time (s)" if show_xlabel else "")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_color("black")
        ax.spines[side].set_linewidth(1.0)
    if not df_lines.empty:
        ax.set_xlim(int(df_lines["elapsed_s"].min()), int(df_lines["elapsed_s"].max()))

    # legend: upper-left in each panel
    leg = ax.legend(loc="upper left", frameon=True, title=None, ncol=1, fancybox=False)
    leg.get_frame().set_edgecolor("black")
    leg.get_frame().set_linewidth(1.0)


def main():
    df = pd.read_csv(CSV_PATH)
    df = _normalize_columns(df)
    df = _prefer_aggregation(df)

    for key in ("consensus", "mec_count", "role", "elapsed_s"):
        if key not in df.columns:
            raise SystemExit(f"Missing required column: {key}")

    df_cpu = _prepare_metric_df(df, metric="cpu")
    df_mem = _prepare_metric_df(df, metric="mem")

    cpu_consumer = _filter_by_coverage_and_align(df_cpu, role="consumer")
    cpu_provider = _filter_by_coverage_and_align(df_cpu, role="provider")
    mem_consumer = _filter_by_coverage_and_align(df_mem, role="consumer")
    mem_provider = _filter_by_coverage_and_align(df_mem, role="provider")

    sns.set_theme(context="paper", style="whitegrid")
    sns.set_context("paper", font_scale=1.35)

    fig, axes = plt.subplots(2, 2, figsize=(13.0, 8.8),
                             gridspec_kw={"wspace": 0.30, "hspace": 0.36})
    ax_tl, ax_tr = axes[0]
    ax_bl, ax_br = axes[1]

    # Top row: no x-labels
    _plot_panel(ax_tl, cpu_consumer, title="Consumer — CPU",  ylabel="CPU (vCPUs)", show_xlabel=False)
    _plot_panel(ax_tr, cpu_provider, title="Provider — CPU",  ylabel="CPU (vCPUs)", show_xlabel=False)

    # Bottom row: x-label "Time (s)"
    _plot_panel(ax_bl, mem_consumer, title="Consumer — Memory", ylabel="Memory (MB)", show_xlabel=True)
    _plot_panel(ax_br, mem_provider, title="Provider — Memory", ylabel="Memory (MB)", show_xlabel=True)

    plt.show()

    out = Path("plots"); out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "time_by_role_4panels.pdf", dpi=300, bbox_inches="tight")


if __name__ == "__main__":
    main()
