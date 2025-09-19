#!/usr/bin/env python3
# barplot_resource_cpu_mem.py
# Two-panel seaborn figure: CPU (vCPU) and Memory (MB), mean ± std, for mec_count 4/10/20/30.

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
from itertools import product
import numpy as np

CSV_PATH = Path("multiple-offers/_summary/resource_usage_overall.csv")

KEEP_COUNTS     = [4, 10, 20, 30]
KEEP_STR        = [str(x) for x in KEEP_COUNTS]
CONSENSUS_ORDER = ["clique", "qbft"]
CONSENSUS_LABEL = {"clique": "Clique", "qbft": "QBFT"}
PALETTE         = ["#1f77b4", "#ff7f0e"]

# Prefer the new low-noise aggregation; fall back to legacy if needed
AGG_PREFERENCE  = ["per_node_median", "per_run"]

def pick_first(df, candidates):
    """Return the first column name that exists in df among candidates."""
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"None of the columns found: {candidates}")

def choose_aggregation(df):
    if "aggregation" not in df.columns:
        return df, None
    for a in AGG_PREFERENCE:
        if (df["aggregation"] == a).any():
            return df[df["aggregation"] == a].copy(), a
    return df, None

def prep(df, mean_col, std_col):
    """Reindex to full (mec_count, consensus) grid so bars and error bars align."""
    idx = pd.MultiIndex.from_product([KEEP_COUNTS, CONSENSUS_ORDER], names=["mec_count", "consensus"])
    out = (
        df.set_index(["mec_count", "consensus"])
          [[mean_col, std_col]]
          .reindex(idx)
          .reset_index()
    )
    out["mec_count_cat"] = pd.Categorical(out["mec_count"].astype(str), categories=KEEP_STR, ordered=True)
    return out

def stylize_axes(ax):
    ax.grid(True, which="both", axis="both", linestyle="--", color="grey", alpha=0.5)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_color("black")
        ax.spines[side].set_linewidth(1.1)
    ax.set_ylim(0, None)

def add_errbars(ax, df_plot, mean_col, std_col):
    """
    Draw symmetric ±std error bars using explicit bar positions
    (aligned to mec_count × consensus). Works even if seaborn drops NaN bars.
    """
    H = len(CONSENSUS_ORDER)   # number of hues
    group_width = 0.8
    bar_width   = group_width / H

    # Category tick positions (one per mec group)
    xticks = ax.get_xticks()
    if len(xticks) != len(KEEP_STR):
        xticks = np.arange(len(KEEP_STR))

    for gi, mc in enumerate(KEEP_STR):
        x_center = xticks[gi]
        x0 = x_center - group_width/2 + bar_width/2
        for hj, cons in enumerate(CONSENSUS_ORDER):
            sel = df_plot[(df_plot["mec_count_cat"] == mc) & (df_plot["consensus"] == cons)]
            if sel.empty:
                continue

            mean_y = float(sel[mean_col].iloc[0])
            std_y  = float(sel[std_col].iloc[0])

            if not np.isfinite(mean_y) or not np.isfinite(std_y) or std_y == 0.0:
                continue

            x = x0 + hj * bar_width
            ax.errorbar(
                x, mean_y,
                yerr=std_y,
                fmt="none",
                ecolor="black",
                elinewidth=1.2,
                capsize=3,
                zorder=3,
            )

def log_stats_block(title, df_plot, mean_col, std_col, units):
    """Print a tidy block of mean ± std by mec_count × consensus."""
    print(f"[log] {title}")
    for mc in KEEP_STR:
        for cons in CONSENSUS_ORDER:
            row = df_plot[(df_plot["mec_count_cat"] == mc) & (df_plot["consensus"] == cons)]
            if row.empty:
                continue
            mean_v = float(row[mean_col].iloc[0])
            std_v  = float(row[std_col].iloc[0])
            print(f"  MEC={mc:>2} | {cons.upper():<5}  mean={mean_v:8.3f} {units}  std={std_v:8.3f} {units}")
    print()

def main():
    df = pd.read_csv(CSV_PATH)

    # Normalize any legacy column names
    df = df.rename(columns={
        "consensus_": "consensus",
        "mec_count_": "mec_count",
        "role_": "role",
    })

    # Choose aggregation to plot (prefer low-noise)
    df, agg_used = choose_aggregation(df)
    print(f"[log] Using aggregation: {agg_used or 'N/A (not present)'}")

    # Keep desired mec_counts and set ordering
    df = df[df["mec_count"].isin(KEEP_COUNTS)].copy()
    df["consensus"] = pd.Categorical(df["consensus"], categories=CONSENSUS_ORDER, ordered=True)

    # Pick the right columns (works with both old and new schemas)
    cpu_mean_col = pick_first(df, ["cpu_percent_mean", "cpu_percent_mean_mean"])
    cpu_std_col  = pick_first(df, ["cpu_percent_std",  "cpu_percent_std_mean"])
    mem_mean_col = pick_first(df, ["mem_mb_mean",     "mem_mb_mean_mean"])
    mem_std_col  = pick_first(df, ["mem_mb_std",      "mem_mb_std_mean"])

    # Derived display columns
    df["cpu_mean_vcpu"] = df[cpu_mean_col] / 100.0
    df["cpu_std_vcpu"]  = df[cpu_std_col]  / 100.0
    df["mem_mean_mb"]   = df[mem_mean_col]
    df["mem_std_mb"]    = df[mem_std_col]

    sns.set_theme(context="paper", style="ticks")
    sns.set_context("paper", font_scale=1.5)

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8), gridspec_kw={"wspace": 0.3})

    # ---- CPU panel ----
    ax0 = axes[0]
    d_cpu = prep(df, "cpu_mean_vcpu", "cpu_std_vcpu")

    # Logs for CPU
    log_stats_block("CPU mean ± std (vCPU)", d_cpu, "cpu_mean_vcpu", "cpu_std_vcpu", "vCPU")

    sns.barplot(
        data=d_cpu, x="mec_count_cat", y="cpu_mean_vcpu", hue="consensus",
        hue_order=CONSENSUS_ORDER, palette=PALETTE,
        errorbar=None, ax=ax0
    )
    add_errbars(ax0, d_cpu, "cpu_mean_vcpu", "cpu_std_vcpu")
    ax0.set_xlabel("Number of MECs")
    ax0.set_ylabel("CPU usage (vCPUs)")
    stylize_axes(ax0)
    h0, l0 = ax0.get_legend_handles_labels()
    l0 = [CONSENSUS_LABEL.get(x, x) for x in l0]
    leg0 = ax0.legend(h0, l0, title=None, frameon=True, loc="upper left", fancybox=True)
    leg0.get_frame().set_edgecolor("black"); leg0.get_frame().set_linewidth(1.1)

    # ---- Memory panel ----
    ax1 = axes[1]
    d_mem = prep(df, "mem_mean_mb", "mem_std_mb")

    # Logs for Memory
    log_stats_block("MEM mean ± std (MB)", d_mem, "mem_mean_mb", "mem_std_mb", "MB")

    sns.barplot(
        data=d_mem, x="mec_count_cat", y="mem_mean_mb", hue="consensus",
        hue_order=CONSENSUS_ORDER, palette=PALETTE,
        errorbar=None, ax=ax1
    )
    add_errbars(ax1, d_mem, "mem_mean_mb", "mem_std_mb")
    ax1.set_xlabel("Number of MECs")
    ax1.set_ylabel("Memory usage (MB)")
    stylize_axes(ax1)
    h1, l1 = ax1.get_legend_handles_labels()
    l1 = [CONSENSUS_LABEL.get(x, x) for x in l1]
    leg1 = ax1.legend(h1, l1, title=None, frameon=True, loc="upper left", fancybox=True)
    leg1.get_frame().set_edgecolor("black"); leg1.get_frame().set_linewidth(1.1)

    # Save & show
    out = Path("plots"); out.mkdir(exist_ok=True, parents=True)
    fig.savefig(out / "resource_usage_cpu_mem_barplot.pdf", dpi=300, bbox_inches="tight")
    print(f"[log] Saved: {out / 'resource_usage_cpu_mem_barplot.pdf'}")
    plt.show()

if __name__ == "__main__":
    main()
