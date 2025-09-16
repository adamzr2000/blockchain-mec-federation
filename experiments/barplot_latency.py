#!/usr/bin/env python3
# barplot_latency_total_meanstd.py
# Single-panel barplot: total federation time (s) as mean ± std
# computed across per-consumer medians (low-noise + consistent with resource bars).

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
from itertools import product

CSV_PATH = Path("multiple-offers/_summary/consumer_summary.csv")

KEEP_COUNTS     = [10, 20, 30]
KEEP_STR        = [str(x) for x in KEEP_COUNTS]
CONSENSUS_ORDER = ["clique", "qbft"]
CONSENSUS_LABEL = {"clique": "Clique", "qbft": "QBFT"}
PALETTE         = ["#1f77b4", "#ff7f0e"]

PREF_AGG        = ["per_consumer_median", "per_service"]  # prefer low-noise layer

def pick_agg(df):
    if "aggregation" not in df.columns:
        return df, None
    for a in PREF_AGG:
        if (df["aggregation"] == a).any():
            return df[df["aggregation"] == a].copy(), a
    return df, None

def prep_grid(df, mean_col, std_col):
    idx = pd.MultiIndex.from_product([KEEP_COUNTS, CONSENSUS_ORDER], names=["mec_count","consensus"])
    out = (
        df.set_index(["mec_count","consensus"])[[mean_col, std_col]]
          .reindex(idx)
          .reset_index()
    )
    out["mec_count_cat"] = pd.Categorical(out["mec_count"].astype(str), categories=KEEP_STR, ordered=True)
    return out

def add_errbars(ax, df_plot, std_col):
    yerrs = []
    for mc, cons in product(KEEP_STR, CONSENSUS_ORDER):
        sel = df_plot[(df_plot["mec_count_cat"] == mc) & (df_plot["consensus"] == cons)]
        yerrs.append(float(sel[std_col].iloc[0]) if not sel.empty else 0.0)
    for patch, yerr in zip(ax.patches, yerrs):
        x = patch.get_x() + patch.get_width() / 2.0
        ax.errorbar(x, patch.get_height(), yerr=yerr,
                    fmt="none", ecolor="black", elinewidth=1.2, capsize=3, zorder=3)

def main():
    df = pd.read_csv(CSV_PATH)

    # choose aggregation (prefer per_consumer_median)
    df, used = pick_agg(df)

    # keep mec counts of interest & order consensus
    df = df[df["mec_count"].isin(KEEP_COUNTS)].copy()
    df["consensus"] = pd.Categorical(df["consensus"], categories=CONSENSUS_ORDER, ordered=True)

    # convert to numeric (CSV has numbers as strings)
    for c in ["total_mean_ms","total_std_ms"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # seconds
    df["total_mean_s"] = df["total_mean_ms"] / 1000.0
    df["total_std_s"]  = df["total_std_ms"]  / 1000.0

    # grid for clean bars
    dplot = prep_grid(df, "total_mean_s", "total_std_s")

    sns.set_theme(context="paper", style="ticks")
    sns.set_context("paper", font_scale=1.5)

    fig, ax = plt.subplots(1, 1, figsize=(6.8, 4.2))

    sns.barplot(
        data=dplot, x="mec_count_cat", y="total_mean_s", hue="consensus",
        hue_order=CONSENSUS_ORDER, palette=PALETTE, errorbar=None, ax=ax
    )
    add_errbars(ax, dplot, "total_std_s")

    ax.set_xlabel("Number of validator nodes (MECs)")
    ax.set_ylabel("Total federation time (s)")
    ax.grid(True, axis="y", linestyle="--", color="grey", alpha=0.5)
    for side in ("top","right","bottom","left"):
        ax.spines[side].set_color("black")
        ax.spines[side].set_linewidth(1.1)
    ax.set_ylim(0, None)

    handles, labels = ax.get_legend_handles_labels()
    labels = [CONSENSUS_LABEL.get(x, x) for x in labels]
    leg = ax.legend(handles, labels, title=None, frameon=True, loc="upper left", fancybox=False)
    leg.get_frame().set_edgecolor("black"); leg.get_frame().set_linewidth(1.1)

    # small footer note in the console about what we plotted
    print(f"[info] aggregation used: {used or 'unknown'}")
    if used == "per_consumer_median":
        print("[info] bars = mean across consumers of each consumer’s median total time;")
        print("       error bars = std across those consumer-level medians.")
    elif used == "per_service":
        print("[info] bars = mean across services; error bars = std across services.")

    plt.show()
    out = Path("plots"); out.mkdir(exist_ok=True, parents=True)
    fig.savefig(out / "latency_total_barplot_meanstd.pdf", dpi=300, bbox_inches="tight")

if __name__ == "__main__":
    main()
