#!/usr/bin/env python3
# barplot_registration.py
# Single-panel barplot of registration time (ms).
# Default: center = mean_ms, error = ±std_ms (matches your other plots).
# Fallback: if mean/std missing, uses median (p50_ms) with IQR (p25..p75).
# Includes position-aware error bars (no reliance on ax.patches) and logs.

import argparse
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
from itertools import product

CSV_PATH = Path("registration/_summary/summary_all.csv")

# x-axis categories
KEEP_COUNTS = [4, 10, 20, 30]
KEEP_STR    = [str(x) for x in KEEP_COUNTS]

# hues
CONSENSUS_ORDER = ["clique", "qbft", "soa"]
CONSENSUS_LABEL = {"clique": "Clique", "qbft": "QBFT", "soa": "SOA"}
PALETTE         = ["#1f77b4", "#ff7f0e", "#2ca02c"]

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--center", choices=["mean", "median"], default="mean",
                    help="Bar height: mean_ms or median (p50_ms). Default: mean.")
    ap.add_argument("--err", choices=["auto", "std", "iqr"], default="auto",
                    help="Error bars: auto (std for mean, iqr for median), or force std/iqr.")
    ap.add_argument("--annot", action="store_true",
                    help="Annotate bars with their numeric values (ms).")
    ap.add_argument("--out", default="plots/registration_time_barplot.pdf",
                    help="Output PDF path.")
    return ap.parse_args()

def prep_grid(df, cols_needed):
    idx = pd.MultiIndex.from_product([KEEP_COUNTS, CONSENSUS_ORDER],
                                     names=["mec_count", "consensus"])
    df = df.set_index(["mec_count", "consensus"]).reindex(idx).reset_index()
    for c in cols_needed:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["mec_count_cat"] = pd.Categorical(
        df["mec_count"].astype(str), categories=KEEP_STR, ordered=True
    )
    return df

def compute_err_arrays(df_plot, center_col, mode):
    """Return centers and (lo, hi) arrays in product(KEEP_STR, CONSENSUS_ORDER) order."""
    centers, err_low, err_high = [], [], []
    for mc, cons in product(KEEP_STR, CONSENSUS_ORDER):
        sel = df_plot[(df_plot["mec_count_cat"] == mc) & (df_plot["consensus"] == cons)]
        if sel.empty:
            centers.append(np.nan); err_low.append(0.0); err_high.append(0.0); continue

        c = float(sel[center_col].iloc[0]) if center_col in sel.columns else np.nan
        centers.append(c)

        if mode == "std":
            s = float(sel.get("std_ms", pd.Series([np.nan])).iloc[0])
            s = 0.0 if np.isnan(s) else s
            err_low.append(s); err_high.append(s)
        elif mode == "iqr":
            p25 = float(sel.get("p25_ms", pd.Series([np.nan])).iloc[0])
            p75 = float(sel.get("p75_ms", pd.Series([np.nan])).iloc[0])
            lo = 0.0 if (np.isnan(p25) or np.isnan(c)) else max(0.0, c - p25)
            hi = 0.0 if (np.isnan(p75) or np.isnan(c)) else max(0.0, p75 - c)
            err_low.append(lo); err_high.append(hi)
        else:
            err_low.append(0.0); err_high.append(0.0)
    return np.array(centers), np.array(err_low), np.array(err_high)

# --- position-aware error bars (don’t rely on ax.patches order) ---
def add_errbars(ax, centers, err_low, err_high):
    """
    Draw y-error bars at exact bar x-positions using seaborn's dodge geometry.
    Arrays must be in product(KEEP_STR, CONSENSUS_ORDER) order.
    """
    H = len(CONSENSUS_ORDER)
    group_width = 0.8
    bar_width   = group_width / H

    xticks = ax.get_xticks()
    if len(xticks) != len(KEEP_STR):
        xticks = np.arange(len(KEEP_STR))

    i = 0
    for gi, _mc in enumerate(KEEP_STR):
        x_center = xticks[gi]
        x0 = x_center - group_width/2 + bar_width/2
        for hj, _cons in enumerate(CONSENSUS_ORDER):
            c  = centers[i]
            lo = err_low[i]
            hi = err_high[i]
            i += 1
            if np.isnan(c) or (lo == 0 and hi == 0):
                continue
            x = x0 + hj * bar_width
            ax.errorbar(x, c, yerr=[[lo],[hi]], fmt="none",
                        ecolor="black", elinewidth=1.2, capsize=3, zorder=3)

def annotate_bars(ax, centers, err_high, fmt="{:.0f} ms", dy_frac=0.02):
    # Use same geometry as add_errbars
    ymin, ymax = ax.get_ylim()
    dy = (ymax - ymin) * dy_frac

    H = len(CONSENSUS_ORDER)
    group_width = 0.8
    bar_width   = group_width / H
    xticks = ax.get_xticks()
    if len(xticks) != len(KEEP_STR):
        xticks = np.arange(len(KEEP_STR))

    i = 0
    for gi, _mc in enumerate(KEEP_STR):
        x_center = xticks[gi]
        x0 = x_center - group_width/2 + bar_width/2
        for hj, _cons in enumerate(CONSENSUS_ORDER):
            c  = centers[i]
            hi = err_high[i]
            i += 1
            if np.isnan(c):
                continue
            x = x0 + hj * bar_width
            y = c + (hi if np.isfinite(hi) else 0.0) + dy
            ax.text(x, y, fmt.format(c), ha="center", va="bottom", fontsize=9)

def main():
    args = parse_args()
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(CSV_PATH)

    # Mixed aggregations in file:
    # - clique/qbft → per_mec_median
    # - soa         → per_consumer_median
    want = (
        (df["consensus"].isin(["clique", "qbft"]) & (df["aggregation"] == "per_mec_median")) |
        (df["consensus"].isin(["soa"])            & (df["aggregation"] == "per_consumer_median"))
    )
    before = len(df)
    df = df[want & df["mec_count"].isin(KEEP_COUNTS)].copy()
    after = len(df)

    df["consensus"] = pd.Categorical(df["consensus"], categories=CONSENSUS_ORDER, ordered=True)

    have_meanstd = {"mean_ms", "std_ms"}.issubset(df.columns)

    # Resolve center & error modes
    if args.err == "auto":
        err_mode = "std" if args.center == "mean" else "iqr"
    else:
        err_mode = args.err

    # If user wants mean/std but CSV lacks them, fall back to median/IQR
    if (args.center == "mean" and not have_meanstd):
        print("[log][warn] mean_ms/std_ms not found in CSV; falling back to median/IQR.")
        args.center = "median"
        err_mode = "iqr"

    # Columns needed for selected modes
    cols_needed = []
    if args.center == "mean" or err_mode == "std":
        cols_needed += ["mean_ms", "std_ms"]
    if args.center == "median" or err_mode == "iqr":
        cols_needed += ["p25_ms", "p50_ms", "p75_ms"]

    df = prep_grid(df, cols_needed)

    # Pick center column
    center_col = "mean_ms" if args.center == "mean" else "p50_ms"

    centers, err_low, err_high = compute_err_arrays(df, center_col, err_mode)

    # ---------------- LOGS ----------------
    print("[log] Registration time barplot")
    print(f"[log] Filtered rows: {before} → {after}; grid size (after reindex): {df.shape[0]}")
    mode_desc = ("mean" if args.center == "mean" else "median") + " with " + \
                ("±STD" if err_mode == "std" else "IQR (p25..p75)")
    print(f"[log] Mode: {mode_desc}")
    for mc in KEEP_STR:
        for cons in CONSENSUS_ORDER:
            sel = df[(df["mec_count_cat"] == mc) & (df["consensus"] == cons)]
            if sel.empty:
                continue
            if args.center == "mean":
                c = float(sel.get("mean_ms", pd.Series([np.nan])).iloc[0])
            else:
                c = float(sel.get("p50_ms", pd.Series([np.nan])).iloc[0])

            if err_mode == "std":
                s = float(sel.get("std_ms", pd.Series([np.nan])).iloc[0])
                print(f"  MEC={mc:>2} | {cons.upper():<5}  mean={c:8.0f} ms  ±STD={s:7.0f} ms")
            else:
                p25 = float(sel.get("p25_ms", pd.Series([np.nan])).iloc[0])
                p75 = float(sel.get("p75_ms", pd.Series([np.nan])).iloc[0])
                lo  = c - p25 if np.isfinite(c) and np.isfinite(p25) else np.nan
                hi  = p75 - c if np.isfinite(c) and np.isfinite(p75) else np.nan
                print(f"  MEC={mc:>2} | {cons.upper():<5}  p25={p25:8.0f}  p50/mean={c:8.0f}  p75={p75:8.0f}   IQR:-{lo:5.0f}/+{hi:5.0f}")
    print()

    # -------- Plot --------
    sns.set_theme(context="paper", style="ticks")
    sns.set_context("paper", font_scale=1.5)

    fig, ax = plt.subplots(1, 1, figsize=(7.6, 4.4))
    sns.barplot(
        data=df, x="mec_count_cat", y=center_col, hue="consensus",
        hue_order=CONSENSUS_ORDER, palette=PALETTE, errorbar=None, ax=ax
    )

    if err_mode in ("std", "iqr"):
        add_errbars(ax, centers, err_low, err_high)

    ax.set_xlabel("Number of MECs")
    ax.set_ylabel("Registration Time (ms)")
    ax.grid(True, which="both", axis="both", linestyle="--", color="grey", alpha=0.5)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_color("black")
        ax.spines[side].set_linewidth(1.1)
    ax.set_ylim(0, None)

    # Legend
    handles, labels = ax.get_legend_handles_labels()
    labels = [CONSENSUS_LABEL.get(x, x) for x in labels]
    leg = ax.legend(handles, labels, title=None, frameon=True, loc="lower left")
    leg.get_frame().set_edgecolor("black"); leg.get_frame().set_linewidth(1.1)

    # Optional annotations
    if args.annot:
        annotate_bars(ax, centers, err_high, fmt="{:.0f} ms", dy_frac=0.02)

    fig.savefig(out, dpi=300, bbox_inches="tight")
    print(f"[log] Saved: {out}")
    plt.show()

if __name__ == "__main__":
    main()
