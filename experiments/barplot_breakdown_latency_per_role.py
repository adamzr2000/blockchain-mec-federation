#!/usr/bin/env python3
# stackedbars_consumer_provider.py
# Two-panel Federation Procedures using *_timeline_summary.csv (low-noise layer).
# Panel 1: Consumer; Panel 2: Provider.
# Centers: --agg {mean,median}. Error bars: --err {std,none}. Units: seconds.
# Consensus labels (Clique/QBFT) are placed above each bar (no consensus legend).

import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# ---- Inputs (produced by latency_summary_multiple_offers.py) ----
C_PATH = Path("multiple-offers/_summary/consumer_timeline_summary.csv")
P_PATH = Path("multiple-offers/_summary/provider_timeline_summary.csv")

KEEP_COUNTS     = [4, 10, 20, 30]
CONSENSUS_ORDER = ["clique", "qbft"]
CONS_LABEL      = {"clique": "Clique", "qbft": "QBFT"}
HATCH           = {"clique": "", "qbft": ""}

# Phase colors
C_PHASES = [
    ("dur_bid_collection",          "Bid(s) Received"),
    ("dur_winner_selection",        "Provider Selection"),
    ("dur_provider_deploy_confirm", "Deployment Confirmation\nReceived"),
]
C_LAST_LABEL = "Federation Completed"  # = dur_vxlan_setup + dur_federation_completed
C_COLORS = ["#4C78A8", "#F58518", "#54A24B", "#D62728"]

P_PHASES = [
    ("dur_winners_received",   "Winner(s) Received"),
    ("dur_confirm_deployment", "Service Deployment(s)\n& Confirmation(s)"),
]
P_COLORS = ["#9467bd", "#17becf"]

def _to_num(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def parse_args():
    ap = argparse.ArgumentParser(
        description="Two-panel Federation Procedures from *_timeline_summary.csv"
    )
    ap.add_argument("--agg", choices=["mean","median"], default="mean",
                    help="Bar heights: mean-of-medians or median-of-medians (default: mean).")
    ap.add_argument("--err", choices=["std","none"], default="std",
                    help="Error bars: ±STD on each stacked segment (default: std).")
    return ap.parse_args()

def _place_consensus_labels(ax, x_vals, offsets, label_tops, global_max):
    y_max_for_ylim = 0.0
    for xi, _mc in enumerate(KEEP_COUNTS):
        for cons_name, tops, max_stds in label_tops:
            top_val = float(tops[xi])
            pad_std = float(max_stds[xi])
            pad_const = max(0.02 * (top_val + pad_std), 0.05)  # ≥ 0.05s
            y_label = top_val + pad_std + pad_const
            y_max_for_ylim = max(y_max_for_ylim, y_label)
            ax.text(
                x_vals[xi] + offsets[cons_name],
                y_label,
                CONS_LABEL.get(cons_name, cons_name),
                ha="center", va="bottom", fontsize=9, clip_on=False
            )
    return max(global_max, y_max_for_ylim)

def _log_panel(header, grid, phases, suf_center, suf_std, has_std):
    print(f"[log] {header}")
    for cons in CONSENSUS_ORDER:
        sub = grid[grid["consensus"] == cons]
        if sub.empty:
            continue
        for i, mc in enumerate(KEEP_COUNTS):
            row = sub[sub["mec_count"] == mc]
            if row.empty:
                continue
            bottoms = 0.0
            perbar_max_std = 0.0
            print(f"  MEC={mc:>2} | {cons.upper()}")
            for (key, label) in phases:
                c = float(row[f"{key}_{suf_center}"].iloc[0]) if f"{key}_{suf_center}" in row.columns else float("nan")
                s = float(row[f"{key}_{suf_std}"].iloc[0])    if (has_std and f"{key}_{suf_std}" in row.columns) else 0.0
                print(f"    - {label:<40} center={c:7.3f}s  std={s:7.3f}s")
                bottoms += c
                perbar_max_std = max(perbar_max_std, s)
            print(f"    > top={bottoms:7.3f}s   max_segment_std={perbar_max_std:7.3f}s")
    print()

def main():
    args = parse_args()
    if not C_PATH.exists() or not P_PATH.exists():
        raise SystemExit("Expected consumer/provider timeline CSVs under multiple-offers/_summary/.")

    # ---------------------- Load & filter ----------------------
    cons = pd.read_csv(C_PATH)
    prov = pd.read_csv(P_PATH)

    # keep low-noise layer
    cons = cons[cons.get("aggregation", "") == "per_consumer_median"].copy()
    prov = prov[prov.get("aggregation", "") == "per_provider_median"].copy()

    # keep scenarios
    cons = cons[cons["mec_count"].isin(KEEP_COUNTS) & cons["consensus"].isin(CONSENSUS_ORDER)].copy()
    prov = prov[prov["mec_count"].isin(KEEP_COUNTS) & prov["consensus"].isin(CONSENSUS_ORDER)].copy()

    # center suffix
    suf_ms_center = "mean_ms" if args.agg == "mean" else "median_ms"

    # Ensure required cols (consumer centers + stds)
    need_c_centers = [f"{k}_{suf_ms_center}" for k,_ in C_PHASES] + ["dur_vxlan_setup_"+suf_ms_center, "dur_federation_completed_"+suf_ms_center]
    need_c_stds    = [f"{k}_std_ms" for k,_ in C_PHASES] + ["dur_vxlan_setup_std_ms", "dur_federation_completed_std_ms"]
    cons = _to_num(cons, need_c_centers + need_c_stds)

    # Ensure required cols (provider centers + stds)
    need_p_centers = [f"{k}_{suf_ms_center}" for k,_ in P_PHASES]
    need_p_stds    = [f"{k}_std_ms" for k,_ in P_PHASES]
    prov = _to_num(prov, need_p_centers + need_p_stds)

    # order categories
    cons["consensus"] = pd.Categorical(cons["consensus"], categories=CONSENSUS_ORDER, ordered=True)
    prov["consensus"] = pd.Categorical(prov["consensus"], categories=CONSENSUS_ORDER, ordered=True)

    # Build tidy grids indexed by (mec_count, consensus)
    idx = pd.MultiIndex.from_product([KEEP_COUNTS, CONSENSUS_ORDER], names=["mec_count","consensus"])
    cons_grid = (
        cons.set_index(["mec_count","consensus"])
            [[*need_c_centers, *need_c_stds]]
            .reindex(idx)
            .reset_index()
    )
    prov_grid = (
        prov.set_index(["mec_count","consensus"])
            [[*need_p_centers, *need_p_stds]]
            .reindex(idx)
            .reset_index()
    )

    # ----- Convert ms → s; write to *_center_s / *_std_s for clarity -----
    # consumer
    for (key, _) in C_PHASES + [("dur_vxlan_setup",""), ("dur_federation_completed","")]:
        c_ms = f"{key}_{suf_ms_center}"
        s_ms = f"{key}_std_ms"
        if c_ms in cons_grid.columns:
            cons_grid[f"{key}_center_s"] = pd.to_numeric(cons_grid[c_ms], errors="coerce").fillna(0).clip(lower=0) / 1000.0
        if s_ms in cons_grid.columns:
            cons_grid[f"{key}_std_s"]    = pd.to_numeric(cons_grid[s_ms], errors="coerce").fillna(0).clip(lower=0) / 1000.0

    # provider
    for (key, _) in P_PHASES:
        c_ms = f"{key}_{suf_ms_center}"
        s_ms = f"{key}_std_ms"
        if c_ms in prov_grid.columns:
            prov_grid[f"{key}_center_s"] = pd.to_numeric(prov_grid[c_ms], errors="coerce").fillna(0).clip(lower=0) / 1000.0
        if s_ms in prov_grid.columns:
            prov_grid[f"{key}_std_s"]    = pd.to_numeric(prov_grid[s_ms], errors="coerce").fillna(0).clip(lower=0) / 1000.0

    # Consumer combined last phase (vxlan + post-check): centers & stds (quadrature)
    cons_grid["cons_last_center_s"] = cons_grid["dur_vxlan_setup_center_s"].fillna(0) + cons_grid["dur_federation_completed_center_s"].fillna(0)
    cons_grid["cons_last_std_s"]    = np.sqrt(
        cons_grid["dur_vxlan_setup_std_s"].fillna(0)**2 + cons_grid["dur_federation_completed_std_s"].fillna(0)**2
    )

    # ---------------------- Logs ----------------------
    has_std = (args.err == "std")
    print(f"[log] Mode: centers={args.agg}  |  errors={'±STD per segment' if has_std else 'none'}  |  units=seconds")
    _log_panel("CONSUMER segments (center/std per phase)", cons_grid, C_PHASES + [("cons_last","(VXLAN + Completed)")], "center_s", "std_s", has_std)
    _log_panel("PROVIDER segments (center/std per phase)", prov_grid, P_PHASES, "center_s", "std_s", has_std)

    # ---------------------- Plot ----------------------
    sns.set_theme(context="paper", style="ticks")
    sns.set_context("paper", font_scale=1.4)

    fig, (axc, axp) = plt.subplots(1, 2, figsize=(12.8, 5.8), sharey=True)

    # Common x positions: grouped by mec_count, two bars per group (clique left, qbft right)
    x_vals  = np.arange(len(KEEP_COUNTS), dtype=float)
    bar_w   = 0.34
    offsets = {"clique": -bar_w/2, "qbft": +bar_w/2}

    # ------------------ Panel 1: CONSUMER ------------------
    global_max_c = 0.0
    label_tops_cons = []  # (consensus, tops, max_std)

    for cons_name in CONSENSUS_ORDER:
        sub = cons_grid[cons_grid["consensus"] == cons_name]
        bottoms = np.zeros(len(sub), dtype=float)
        perbar_max_std = np.zeros(len(sub), dtype=float)

        # first three stacks
        for (key, label), color in zip(C_PHASES, C_COLORS[:3]):
            heights = sub[f"{key}_center_s"].to_numpy()
            stds    = sub.get(f"{key}_std_s", pd.Series([0.0]*len(sub))).to_numpy()
            axc.bar(
                x_vals + offsets[cons_name], heights, width=bar_w,
                bottom=bottoms, color=color, edgecolor="black", linewidth=0.7,
                hatch=HATCH[cons_name], label=label if cons_name == CONSENSUS_ORDER[0] else None
            )
            if has_std:
                y_top = bottoms + heights
                axc.errorbar(
                    x_vals + offsets[cons_name], y_top, yerr=stds,
                    fmt="none", ecolor="black", elinewidth=1.0, capsize=3, zorder=3
                )
                perbar_max_std = np.maximum(perbar_max_std, np.nan_to_num(stds, nan=0.0))
            bottoms += heights

        # last combined stack
        heights = sub["cons_last_center_s"].to_numpy()
        stds    = sub["cons_last_std_s"].to_numpy()
        axc.bar(
            x_vals + offsets[cons_name], heights, width=bar_w,
            bottom=bottoms, color=C_COLORS[3], edgecolor="black", linewidth=0.7,
            hatch=HATCH[cons_name], label=C_LAST_LABEL if cons_name == CONSENSUS_ORDER[0] else None
        )
        if has_std:
            y_top = bottoms + heights
            axc.errorbar(
                x_vals + offsets[cons_name], y_top, yerr=stds,
                fmt="none", ecolor="black", elinewidth=1.0, capsize=3, zorder=3
            )
            perbar_max_std = np.maximum(perbar_max_std, np.nan_to_num(stds, nan=0.0))

        tops = bottoms + heights
        global_max_c = max(global_max_c, np.max(tops + perbar_max_std))
        label_tops_cons.append((cons_name, tops.copy(), perbar_max_std.copy()))

    # Axis cosmetics (left panel keeps the y label)
    axc.set_xticks(x_vals, [str(mc) for mc in KEEP_COUNTS])
    axc.set_xlabel("Number of MECs")
    axc.set_ylabel("Time (s)")
    axc.set_title("Consumer — Federation Procedures", pad=10)
    leg_c = axc.legend(title=None, frameon=True, loc="upper left")  # phase legend only
    leg_c.get_frame().set_edgecolor("black"); leg_c.get_frame().set_linewidth(1.0)
    axc.grid(True, which="both", axis="both", linestyle="--", color="grey", alpha=0.5)
    for side in ("top","right","bottom","left"):
        axc.spines[side].set_color("black"); axc.spines[side].set_linewidth(1.0)

    # Place consensus labels above bars (no consensus legend)
    ymax_c = _place_consensus_labels(axc, x_vals, offsets, label_tops_cons, global_max_c)

    # ------------------ Panel 2: PROVIDER ------------------
    global_max_p = 0.0
    label_tops_prov = []

    for cons_name in CONSENSUS_ORDER:
        sub = prov_grid[prov_grid["consensus"] == cons_name]
        bottoms = np.zeros(len(sub), dtype=float)
        perbar_max_std = np.zeros(len(sub), dtype=float)

        for (key, label), color in zip(P_PHASES, P_COLORS):
            heights = sub[f"{key}_center_s"].to_numpy()
            stds    = sub.get(f"{key}_std_s", pd.Series([0.0]*len(sub))).to_numpy()
            axp.bar(
                x_vals + offsets[cons_name], heights, width=bar_w,
                bottom=bottoms, color=color, edgecolor="black", linewidth=0.7,
                hatch=HATCH[cons_name], label=label if cons_name == CONSENSUS_ORDER[0] else None
            )
            if has_std:
                y_top = bottoms + heights
                axp.errorbar(
                    x_vals + offsets[cons_name], y_top, yerr=stds,
                    fmt="none", ecolor="black", elinewidth=1.0, capsize=3, zorder=3
                )
                perbar_max_std = np.maximum(perbar_max_std, np.nan_to_num(stds, nan=0.0))
            bottoms += heights

        tops = bottoms
        global_max_p = max(global_max_p, np.max(tops + perbar_max_std))
        label_tops_prov.append((cons_name, tops.copy(), perbar_max_std.copy()))

    # X labels + title (NO y label on the right panel)
    axp.set_xticks(x_vals, [str(mc) for mc in KEEP_COUNTS])
    axp.set_xlabel("Number of MECs")
    axp.set_title("Provider — Federation Procedures", pad=10)
    leg_p = axp.legend(title=None, frameon=True, loc="upper left")  # phase legend only
    leg_p.get_frame().set_edgecolor("black"); leg_p.get_frame().set_linewidth(1.0)
    axp.grid(True, which="both", axis="both", linestyle="--", color="grey", alpha=0.5)
    for side in ("top","right","bottom","left"):
        axp.spines[side].set_color("black"); axp.spines[side].set_linewidth(1.0)

    ymax_p = _place_consensus_labels(axp, x_vals, offsets, label_tops_prov, global_max_p)

    # ---- Single shared ylim so both panels align ----
    overall_ymax = max(ymax_c, ymax_p)
    axc.set_ylim(0, overall_ymax * 1.12)  # sharey=True propagates to axp

    fig.tight_layout()
    outdir = Path("plots"); outdir.mkdir(parents=True, exist_ok=True)
    fname = f"stacked_durations_consumer_provider_{args.agg}_{args.err}.pdf"
    fig.savefig(outdir / fname, dpi=300, bbox_inches="tight")
    print(f"[log] Saved plots/{fname}")
    print(f"[centers] {args.agg} of per-node medians | [errors] {args.err} | shared y-axis | consensus labels above bars")

    plt.show()

if __name__ == "__main__":
    main()
