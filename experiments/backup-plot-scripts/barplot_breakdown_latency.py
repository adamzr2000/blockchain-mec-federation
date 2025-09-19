#!/usr/bin/env python3
# barplot_breakdown_latency.py
# Grouped+stacked bars for general federation steps using ONLY
# federation_timeline_summary.csv (low-noise: per_consumer_median layer).
#
# Bars = phase center (mean-of-medians or median-of-medians), stacked.
# Error bars = per-phase variability (std or IQR), drawn at the top of each segment.

import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

CSV_PATH = Path("multiple-offers/_summary/federation_timeline_summary.csv")

KEEP_COUNTS     = [4, 10, 20, 30]
CONSENSUS_ORDER = ["clique", "qbft"]
CONSENSUS_LABEL = {"clique": "Clique", "qbft": "QBFT"}

PHASES = [
    ("dur_request_federation",       "Request Federation"),
    ("dur_bid_offered",              "Bid Offered"),
    ("dur_provider_chosen",          "Provider Chosen"),
    ("dur_service_deployed_running", "Service Deployed & Running"),
]

PHASE_COLORS = ["#4C78A8", "#F58518", "#54A24B", "#D62728"]
TO_SECONDS = True  # convert ms → s for plotting

def clamp_nonneg(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    return s.fillna(0).clip(lower=0)

def parse_args():
    ap = argparse.ArgumentParser(
        description="Stacked federation phase barplot with selectable center (mean|median) and CI (std|iqr|none)."
    )
    ap.add_argument("--agg", choices=["mean", "median"], default="mean",
                    help="Bar height per phase: mean-of-medians or median-of-medians. Default: mean.")
    ap.add_argument("--ci", choices=["std", "iqr", "none"], default="std",
                    help="Error bars per phase: std (±), iqr (p25–p75 as asymmetric), or none. Default: std.")
    return ap.parse_args()

def main():
    args = parse_args()

    # Theme
    sns.set_theme(context="paper", style="ticks")
    sns.set_context("paper", font_scale=1.5)

    if not CSV_PATH.exists():
        raise SystemExit(f"Missing CSV: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH)

    # Keep only low-noise layer
    if "aggregation" in df.columns:
        df = df[df["aggregation"] == "per_consumer_median"].copy()

    # Filter & order
    df = df[df["mec_count"].isin(KEEP_COUNTS)].copy()
    if df.empty:
        raise SystemExit("No rows left after filtering by aggregation/mec_count.")
    df["consensus"] = pd.Categorical(df["consensus"], categories=CONSENSUS_ORDER, ordered=True)

    # Build centers/errors based on --agg and --ci
    centers = {}
    err_lo  = {}
    err_up  = {}

    for key, _label in PHASES:
        center_col = f"{key}_{'mean_ms' if args.agg == 'mean' else 'median_ms'}"
        if center_col not in df.columns:
            raise SystemExit(f"Missing column: {center_col}")

        centers[key] = clamp_nonneg(df[center_col])

        if args.ci == "std":
            std_col = f"{key}_std_ms"
            if std_col not in df.columns:
                raise SystemExit(f"Missing column for std: {std_col}")
            e = pd.to_numeric(df[std_col], errors="coerce").fillna(0).clip(lower=0)
            err_lo[key] = e
            err_up[key] = e

        elif args.ci == "iqr":
            p25_col, p75_col = f"{key}_p25_ms", f"{key}_p75_ms"
            missing = [c for c in (p25_col, p75_col) if c not in df.columns]
            if missing:
                raise SystemExit(f"Missing IQR columns: {missing}")
            c   = pd.to_numeric(df[center_col], errors="coerce")
            p25 = pd.to_numeric(df[p25_col], errors="coerce")
            p75 = pd.to_numeric(df[p75_col], errors="coerce")
            lo = (c - p25).clip(lower=0).fillna(0)
            up = (p75 - c).clip(lower=0).fillna(0)
            err_lo[key] = lo
            err_up[key] = up

        else:  # none
            z = pd.Series(0.0, index=df.index)
            err_lo[key] = z
            err_up[key] = z

    # Units: ms → s if requested
    factor = 1/1000.0 if TO_SECONDS else 1.0
    for key, _ in PHASES:
        centers[key] = centers[key] * factor
        err_lo[key]  = err_lo[key]  * factor
        err_up[key]  = err_up[key]  * factor

        # IMPORTANT: actually add to df so selection works
        df[f"{key}_center"] = centers[key]
        df[f"{key}_err_lo"] = err_lo[key]
        df[f"{key}_err_up"] = err_up[key]

    # Build tidy grid indexed by (mec_count, consensus)
    idx = pd.MultiIndex.from_product([KEEP_COUNTS, CONSENSUS_ORDER], names=["mec_count","consensus"])
    use_cols = []
    for key, _ in PHASES:
        use_cols += [f"{key}_center", f"{key}_err_lo", f"{key}_err_up"]

    grid = (
        df.set_index(["mec_count","consensus"])[use_cols]
          .reindex(idx)
          .reset_index()
    )

    # Replace remaining NaNs with zeros for plotting safety
    grid[use_cols] = grid[use_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)

    # X positions (grouped by mec_count; two bars per group)
    x_vals  = np.arange(len(KEEP_COUNTS), dtype=float)
    bar_w   = 0.34
    offsets = {"clique": -bar_w/2, "qbft": +bar_w/2}

    fig, ax = plt.subplots(1, 1, figsize=(7.8, 4.8))

    # Track tops for placing consensus labels / ylim
    label_tops = []
    global_max_for_ylim = 0.0

    # Plot grouped stacks + per-segment error bars
    for cons in CONSENSUS_ORDER:
        sub = grid[grid["consensus"] == cons]
        bottoms = np.zeros(len(sub), dtype=float)
        perbar_max_up = np.zeros(len(sub), dtype=float)

        for (phase_key, label), color in zip(PHASES, PHASE_COLORS):
            heights = sub[f"{phase_key}_center"].to_numpy()
            lo      = sub[f"{phase_key}_err_lo"].to_numpy()
            up      = sub[f"{phase_key}_err_up"].to_numpy()

            # Draw stacked segment
            ax.bar(
                x_vals + offsets[cons],
                heights,
                width=bar_w,
                bottom=bottoms,
                color=color,
                edgecolor="black",
                linewidth=0.7,
                label=label if cons == CONSENSUS_ORDER[0] else None,
            )

            # Error bars at top of segment (supports asymmetric IQR)
            y_top = bottoms + heights
            ax.errorbar(
                x_vals + offsets[cons], y_top, yerr=[lo, up],
                fmt="none", ecolor="black", elinewidth=1.0, capsize=3, zorder=3
            )

            perbar_max_up = np.maximum(perbar_max_up, up)
            bottoms += heights

        label_tops.append((cons, bottoms, perbar_max_up))

    # Axes & labels
    ax.set_xticks(x_vals)
    ax.set_xticklabels([str(mc) for mc in KEEP_COUNTS])
    ax.set_xlabel("Number of MECs")
    ax.set_ylabel("Time (s)" if TO_SECONDS else "Time (ms)")

    # Phase legend
    leg = ax.legend(title=None, frameon=True, loc="upper left")
    leg.get_frame().set_edgecolor("black")
    leg.get_frame().set_linewidth(1.0)

    # Place “Clique / QBFT” above bars with padding
    for xi, mc in enumerate(KEEP_COUNTS):
        for cons, tops, up_err in label_tops:
            top_val = float(tops[xi])
            pad_up  = float(up_err[xi])
            pad_const = max(0.02 * (top_val + pad_up), 0.05)
            y_label = top_val + pad_up + pad_const
            global_max_for_ylim = max(global_max_for_ylim, y_label)

            ax.text(
                x_vals[xi] + offsets[cons],
                y_label,
                CONSENSUS_LABEL.get(cons, cons),
                ha="center", va="bottom", fontsize=9, clip_on=False
            )

    ax.grid(True, which="both", axis="both", linestyle="--", color="grey", alpha=0.5)
    for side in ("top","right","bottom","left"):
        ax.spines[side].set_color("black")
        ax.spines[side].set_linewidth(1.1)

    ax.set_ylim(0, global_max_for_ylim * 1.8)

    outdir = Path("plots"); outdir.mkdir(parents=True, exist_ok=True)
    fname = f"latency_breakdown_stacked_{args.agg}_{args.ci}.pdf"
    fig.savefig(outdir / fname, dpi=300, bbox_inches="tight")

    print(f"[bars] {args.agg}-of-medians per phase; [errors] {args.ci}")
    print(f"Saved plots/{fname}")
    plt.show()

if __name__ == "__main__":
    main()
