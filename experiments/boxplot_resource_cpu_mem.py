#!/usr/bin/env python3
# boxplot_resource_cpu_mem.py
# Two-panel seaborn figure: CPU (vCPU) and Memory (MB), using boxplots.
# Data: multiple-offers/_summary/resource_usage_per_run.csv (per-run granularity).
# Shows the plot interactively; export to PDF is commented out.

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path

CSV_PATH = Path("multiple-offers/_summary/resource_usage_per_run.csv")

KEEP_COUNTS     = [4, 10, 20, 30]
CONSENSUS_ORDER = ["clique", "qbft"]
CONSENSUS_LABEL = {"clique": "Clique", "qbft": "QBFT"}
PALETTE         = ["#1f77b4", "#ff7f0e"]

def stylize_axes(ax, ylabel):
    ax.grid(axis="y", linestyle="--", color="grey", alpha=0.5)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_color("black")
        ax.spines[side].set_linewidth(1.1)
    ax.set_ylim(0, None)
    ax.set_xlabel("Number of MECs")
    ax.set_ylabel(ylabel)

def main():
    df = pd.read_csv(CSV_PATH)
    df = df[df["mec_count"].isin(KEEP_COUNTS)].copy()
    df["consensus"] = pd.Categorical(df["consensus"], categories=CONSENSUS_ORDER, ordered=True)

    # Convert CPU percent → vCPUs
    df["cpu_vcpu"] = df["cpu_percent_mean"] / 100.0
    # Memory already in MB
    df["mem_mb"]   = df["mem_mb_mean"]

    sns.set_theme(context="paper", style="whitegrid")
    sns.set_context("paper", font_scale=1.5)

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8), gridspec_kw={"wspace": 0.3})

    # ---- CPU panel ----
    ax0 = axes[0]
    sns.boxplot(
        data=df,
        x="mec_count", y="cpu_vcpu", hue="consensus",
        hue_order=CONSENSUS_ORDER, palette=PALETTE,
        ax=ax0
    )
    stylize_axes(ax0, "CPU usage (vCPUs)")
    h0, l0 = ax0.get_legend_handles_labels()
    l0 = [CONSENSUS_LABEL.get(x, x) for x in l0]
    leg0 = ax0.legend(h0, l0, title=None, frameon=True, loc="upper left", fancybox=False)
    leg0.get_frame().set_edgecolor("black"); leg0.get_frame().set_linewidth(1.1)

    # ---- Memory panel ----
    ax1 = axes[1]
    sns.boxplot(
        data=df,
        x="mec_count", y="mem_mb", hue="consensus",
        hue_order=CONSENSUS_ORDER, palette=PALETTE,
        ax=ax1
    )
    stylize_axes(ax1, "Memory usage (MB)")
    h1, l1 = ax1.get_legend_handles_labels()
    l1 = [CONSENSUS_LABEL.get(x, x) for x in l1]
    leg1 = ax1.legend(h1, l1, title=None, frameon=True, loc="upper left", fancybox=False)
    leg1.get_frame().set_edgecolor("black"); leg1.get_frame().set_linewidth(1.1)

    plt.show()
    out = Path("plots"); out.mkdir(exist_ok=True, parents=True)
    fig.savefig(out / "resource_usage_cpu_mem_boxplot.pdf", dpi=300, bbox_inches="tight")

if __name__ == "__main__":
    main()
