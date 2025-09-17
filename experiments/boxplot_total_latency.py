#!/usr/bin/env python3
# Boxplot of end-to-end federation time (consumer perspective)
# Each observation = one consumer's median total across its services/runs
# Source: _summary/consumer_total_per_consumer.csv (written by your summary script)

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
from textwrap import dedent

CSV_PATH        = Path("multiple-offers/_summary/consumer_total_per_consumer.csv")  # run from experiments/multiple-offers/
KEEP_COUNTS     = [4, 10, 20, 30]
KEEP_STR        = [str(x) for x in KEEP_COUNTS]
CONSENSUS_ORDER = ["clique", "qbft"]
CONSENSUS_LABEL = {"clique": "Clique", "qbft": "QBFT"}
PALETTE         = ["#1f77b4", "#ff7f0e"]  # optional; remove to use seaborn defaults

def main():
    df = pd.read_csv(CSV_PATH)

    # Keep scenarios of interest & make ordered categories
    df = df[df["mec_count"].isin(KEEP_COUNTS)].copy()
    df["consensus"]   = pd.Categorical(df["consensus"], categories=CONSENSUS_ORDER, ordered=True)
    df["mec_count_cat"] = pd.Categorical(df["mec_count"].astype(str), categories=KEEP_STR, ordered=True)

    # Convert ms -> s (plotting)
    df["dur_total_s"] = pd.to_numeric(df["dur_total_ms_median"], errors="coerce") / 1000.0
    df = df.dropna(subset=["dur_total_s"])

    # Style
    sns.set_theme(context="paper", style="ticks")
    sns.set_context("paper", font_scale=1.5)

    fig, ax = plt.subplots(figsize=(6.8, 4.2))

    # Boxplot (IQR whiskers; no outliers drawn)
    sns.boxplot(
        data=df, x="mec_count_cat", y="dur_total_s",
        hue="consensus", hue_order=CONSENSUS_ORDER, palette=PALETTE,
        whis=(25, 75), showfliers=False, width=0.65, ax=ax
    )

    # Overlay the individual per-consumer medians
    sns.stripplot(
        data=df, x="mec_count_cat", y="dur_total_s",
        hue="consensus", hue_order=CONSENSUS_ORDER,
        dodge=True, jitter=0.15, alpha=0.35, size=3, linewidth=0, palette=PALETTE, ax=ax
    )

    # De-duplicate the legend (box + strip both add entries)
    handles, labels = ax.get_legend_handles_labels()
    # Keep first two entries that match consensus labels
    keep = []
    seen = set()
    for h, l in zip(handles, labels):
        if l in CONSENSUS_ORDER and l not in seen:
            keep.append((h, l)); seen.add(l)
        if len(keep) == len(CONSENSUS_ORDER):
            break
    if keep:
        handles, labels = zip(*keep)
        labels = [CONSENSUS_LABEL.get(x, x) for x in labels]
        leg = ax.legend(handles, labels, title=None, frameon=True, loc="upper left")
        leg.get_frame().set_edgecolor("black")
        leg.get_frame().set_linewidth(1.1)
    else:
        ax.legend_.remove()

    # Axes & grid
    ax.set_xlabel("Number of MECs")
    ax.set_ylabel("Total federation time (s)")
    ax.grid(True, which="both", axis="y", linestyle="--", color="grey", alpha=0.5)
    for side in ("top","right","bottom","left"):
        ax.spines[side].set_linewidth(1.1)
    ax.set_ylim(0, None)

    # Helpful console note
    print(dedent("""
        [info] Each point = one consumer's median(total) across that consumer's services/runs.
               Boxes summarize the distribution of those per-consumer medians for each (MECs × consensus).
               This matches your dur_total definition: connection_test_success − service_announced.
    """).strip())

    out = Path("plots"); out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "latency_total_boxplot_per_consumer_median.pdf", dpi=300, bbox_inches="tight")
    plt.show()

if __name__ == "__main__":
    main()
