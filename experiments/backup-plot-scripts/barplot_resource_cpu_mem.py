#!/usr/bin/env python3
# barplot_resource_cpu_mem.py
# Two-panel seaborn figure: CPU (vCPU) and Memory (MB), mean ± std, for mec_count 10/20/30.

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
from itertools import product

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
    # If neither is present, just return as-is (unlikely)
    return df, None

def prep(df, mean_col, std_col):
    """Reindex to full (mec_count, consensus) grid so bars and error bars align."""
    idx = pd.MultiIndex.from_product([KEEP_COUNTS, CONSENSUS_ORDER], names=["mec_count", "consensus"])
    out = (df.set_index(["mec_count", "consensus"])
             [[mean_col, std_col]]
             .reindex(idx)
             .reset_index())
    out["mec_count_cat"] = pd.Categorical(out["mec_count"].astype(str), categories=KEEP_STR, ordered=True)
    return out

def stylize_axes(ax):
    ax.grid(True, which="both", axis="both", linestyle="--", color="grey", alpha=0.5)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_color("black")
        ax.spines[side].set_linewidth(1.1)
    ax.set_ylim(0, None)

def add_errbars(ax, df_plot, mean_col, std_col):
    yerrs = []
    for mc, cons in product(KEEP_STR, CONSENSUS_ORDER):
        sel = df_plot[(df_plot["mec_count_cat"] == mc) & (df_plot["consensus"] == cons)]
        yerrs.append(float(sel[std_col].iloc[0]) if not sel.empty else 0.0)
    for patch, yerr in zip(ax.patches, yerrs):
        x_center = patch.get_x() + patch.get_width() / 2.0
        ax.errorbar(x_center, patch.get_height(), yerr=yerr,
                    fmt="none", ecolor="black", elinewidth=1.2, capsize=3)

def main():
    df = pd.read_csv(CSV_PATH)

    # Normalize any legacy grouper names that may have trailing underscores
    df = df.rename(columns={
        "consensus_": "consensus",
        "mec_count_": "mec_count",
        "role_": "role",
    })

    # Choose which aggregation to plot (prefer low-noise)
    df, agg_used = choose_aggregation(df)

    # Keep 10/20/30 only and set ordering
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

    plt.show()
    out = Path("plots"); out.mkdir(exist_ok=True, parents=True)
    fig.savefig(out / "resource_usage_cpu_mem_barplot.pdf", dpi=300, bbox_inches="tight")

if __name__ == "__main__":
    main()
