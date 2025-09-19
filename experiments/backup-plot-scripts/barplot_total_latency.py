#!/usr/bin/env python3
# barplot_latency_total_meanstd.py
# Single-panel barplot of total federation time (s).
# Center can be mean-of-medians or median-of-medians; errors can be std or IQR.

import argparse
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
from itertools import product

CSV_PATH = Path("multiple-offers/_summary/consumer_timeline_summary.csv")

KEEP_COUNTS     = [4, 10, 20, 30]
KEEP_STR        = [str(x) for x in KEEP_COUNTS]
CONSENSUS_ORDER = ["clique", "qbft"]
CONSENSUS_LABEL = {"clique": "Clique", "qbft": "QBFT"}
PALETTE         = ["#1f77b4", "#ff7f0e"]  # order aligned with CONSENSUS_ORDER

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--center", choices=["mean", "median"], default="mean",
                    help="Bar height: mean-of-medians or median-of-medians (default: mean).")
    ap.add_argument("--err", choices=["auto", "std", "iqr", "none"], default="auto",
                    help="Error bars: auto (std for mean, iqr for median), std, iqr, none.")
    ap.add_argument("--annot", action="store_true",
                    help="Annotate bars with their numeric values (in seconds).")
    ap.add_argument("--out", default="plots/latency_total_barplot.pdf",
                    help="Output PDF path.")
    return ap.parse_args()

def prep_grid(df, cols_needed):
    idx = pd.MultiIndex.from_product([KEEP_COUNTS, CONSENSUS_ORDER], names=["mec_count","consensus"])
    df = df.set_index(["mec_count","consensus"])
    df = df.reindex(idx)
    df = df.reset_index()
    # ensure numeric
    for c in cols_needed:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["mec_count_cat"] = pd.Categorical(df["mec_count"].astype(str), categories=KEEP_STR, ordered=True)
    return df

def compute_err_arrays(df_plot, center_col_s, err_mode, std_col_s=None, p25_col_s=None, p75_col_s=None):
    """Return arrays aligned with seaborn's bar draw order (x grouped by mec, hue by consensus)."""
    centers, err_low, err_high = [], [], []
    for mc, cons in product(KEEP_STR, CONSENSUS_ORDER):
        sel = df_plot[(df_plot["mec_count_cat"] == mc) & (df_plot["consensus"] == cons)]
        if sel.empty:
            centers.append(np.nan); err_low.append(0.0); err_high.append(0.0); continue

        c = float(sel[center_col_s].iloc[0])
        centers.append(c)

        if err_mode == "none":
            err_low.append(0.0); err_high.append(0.0)
        elif err_mode == "std":
            s = float(sel[std_col_s].iloc[0]) if std_col_s in sel.columns else np.nan
            s = 0.0 if np.isnan(s) else s
            err_low.append(s); err_high.append(s)
        elif err_mode == "iqr":
            p25 = float(sel[p25_col_s].iloc[0]) if p25_col_s in sel.columns else np.nan
            p75 = float(sel[p75_col_s].iloc[0]) if p75_col_s in sel.columns else np.nan
            # asymmetric whiskers around the chosen center
            lo = 0.0 if np.isnan(p25) or np.isnan(c) else max(0.0, c - p25)
            hi = 0.0 if np.isnan(p75) or np.isnan(c) else max(0.0, p75 - c)
            err_low.append(lo); err_high.append(hi)
        else:
            err_low.append(0.0); err_high.append(0.0)

    return np.array(centers), np.array(err_low), np.array(err_high)

def add_errbars(ax, err_low, err_high):
    # seaborn draws bars in the same product order; ax.patches aligns with that
    for patch, lo, hi in zip(ax.patches, err_low, err_high):
        x = patch.get_x() + patch.get_width() / 2.0
        y = patch.get_height()
        # matplotlib supports asymmetric yerr via a 2xN array, but we draw one by one:
        ax.errorbar(x, y, yerr=[[lo], [hi]], fmt="none", ecolor="black",
                    elinewidth=1.2, capsize=3, zorder=3)

def annotate_bars(ax, centers, err_high, fmt="{:.1f}s", dy_frac=0.02):
    ymin, ymax = ax.get_ylim()
    dy = (ymax - ymin) * dy_frac
    for patch, c, hi in zip(ax.patches, centers, err_high):
        if np.isnan(c):  # nothing to annotate
            continue
        x = patch.get_x() + patch.get_width() / 2.0
        y = (c if np.isfinite(c) else patch.get_height()) + (hi if np.isfinite(hi) else 0.0) + dy
        ax.text(x, y, fmt.format(c), ha="center", va="bottom", fontsize=9)

def main():
    args = parse_args()
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(CSV_PATH)
    # Use the low-noise layer composed of per-consumer medians
    df = df[(df["aggregation"] == "per_consumer_median") & df["mec_count"].isin(KEEP_COUNTS)].copy()
    df["consensus"] = pd.Categorical(df["consensus"], categories=CONSENSUS_ORDER, ordered=True)

    # columns (ms) we’ll convert to seconds
    cols_needed = [
        "dur_total_mean_ms","dur_total_std_ms",
        "dur_total_median_ms","dur_total_p25_ms","dur_total_p75_ms",
    ]
    df = prep_grid(df, cols_needed)

    # convert to seconds
    for src in cols_needed:
        df[src.replace("_ms","_s")] = df[src] / 1000.0

    # choose center & error mode
    if args.err == "auto":
        err_mode = "std" if args.center == "mean" else "iqr"
    else:
        err_mode = args.err

    if args.center == "mean":
        center_col_s = "dur_total_mean_s"
    else:
        center_col_s = "dur_total_median_s"

    std_col_s = "dur_total_std_s"
    p25_col_s = "dur_total_p25_s"
    p75_col_s = "dur_total_p75_s"

    centers, err_low, err_high = compute_err_arrays(df, center_col_s, err_mode,
                                                    std_col_s=std_col_s,
                                                    p25_col_s=p25_col_s,
                                                    p75_col_s=p75_col_s)

    # Plot
    sns.set_theme(context="paper", style="ticks")
    sns.set_context("paper", font_scale=1.5)

    fig, ax = plt.subplots(1, 1, figsize=(7.2, 4.2))
    sns.barplot(
        data=df, x="mec_count_cat", y=center_col_s, hue="consensus",
        hue_order=CONSENSUS_ORDER, palette=PALETTE, errorbar=None, ax=ax
    )

    # Add error bars after bars are drawn
    if err_mode != "none":
        add_errbars(ax, err_low, err_high)

    # Cosmetics
    ax.set_xlabel("Number of MECs")
    ylabel = "Total Federation Time (s)"
    ax.set_ylabel(ylabel)
    ax.grid(True, which="both", axis="both", linestyle="--", color="grey", alpha=0.5)
    for side in ("top","right","bottom","left"):
        ax.spines[side].set_color("black")
        ax.spines[side].set_linewidth(1.1)
    ax.set_ylim(0, None)

    # Legend
    handles, labels = ax.get_legend_handles_labels()
    labels = [CONSENSUS_LABEL.get(x, x) for x in labels]
    leg = ax.legend(handles, labels, title=None, frameon=True, loc="upper left")
    leg.get_frame().set_edgecolor("black"); leg.get_frame().set_linewidth(1.1)

    # Optional numeric labels on top of bars (after setting ylim)
    if args.annot:
        annotate_bars(ax, centers, err_high, fmt="{:.1f}s", dy_frac=0.02)

    # Info + save
    center_desc = "mean-of-medians" if args.center == "mean" else "median-of-medians"
    if err_mode == "std":
        err_desc = "±STD across per-consumer medians"
    elif err_mode == "iqr":
        err_desc = "IQR whiskers (p25–p75 across per-consumer medians)"
    else:
        err_desc = "no error bars"

    print(f"[center] {center_desc}")
    print(f"[errors] {err_desc}")

    fig.savefig(out, dpi=300, bbox_inches="tight")
    print(f"Saved {out}")
    plt.show()

if __name__ == "__main__":
    main()
