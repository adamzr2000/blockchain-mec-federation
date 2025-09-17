#!/usr/bin/env python3
# lineplot_latency_from_durations.py
# Two-panel cumulative step lines (Consumer & Provider) built ONLY from durations.
# Uses low-noise medians from the timeline summaries; optional IQR ribbons or ±STD bars.

import argparse
import math
from pathlib import Path
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# Paths to the timeline summaries produced by latency_summary_multiple_offers.py
C_TIMELINE = Path("multiple-offers/_summary/consumer_timeline_summary.csv")
P_TIMELINE = Path("multiple-offers/_summary/provider_timeline_summary.csv")
OUT        = Path("plots/federation_cumulative_steps_from_durations.pdf")

KEEP_COUNTS     = [4, 10, 20, 30]
CONSENSUS_ORDER = ["clique", "qbft"]
SERIES = [(c, n) for c in CONSENSUS_ORDER for n in KEEP_COUNTS]

# color-blind–safe palette per (consensus, mec_count)
PALETTE = {
    ("clique", 4):  "#1f77b4",
    ("clique", 10): "#ff7f0e",
    ("clique", 20): "#2ca02c",
    ("clique", 30): "#d62728",
    ("qbft", 4):    "#9467bd",
    ("qbft", 10):   "#17becf",
    ("qbft", 20):   "#e377c2",
    ("qbft", 30):   "#8c564b",
}

# ----------------------------- CONSUMER -----------------------------
# Keep 4 cumulative phases; the last is (VXLAN Setup + Post-check).
# We’ll compute that last combined duration from the CSV columns on the fly.
C_FIRST3 = [
    ("dur_bid_collection",          "Bid Collection"),
    ("dur_winner_selection",        "Winner Selection"),
    ("dur_provider_deploy_confirm", "Provider Deploy Confirm"),
]
C_LABELS = [
    "Service\nAnnounced",                 # starts at 0
    "Bid(s)\nReceived",
    "Provider\nChosen",
    "Deployment\nConfirmation\nReceived",
    "Federation\nCompleted",              # (VXLAN Setup + Post-check)
]

# ----------------------------- PROVIDER ----------------------------
# - dur_winners_received = all_winners_received − all_bid_offers_sent
# - dur_confirm_deployment = all_confirm_deployment_sent − first(deployment_start_service*)
P_DURS = [
    ("dur_winners_received",      "Winners Received"),
    ("dur_confirm_deployment",    "Confirm Deployment"),
]
P_LABELS = [
    "All Bids\nOffered",        # starts at 0
    "All Winners\nReceived",
    "All Deployment\nConfirmations\nSent",
]

def _pick_layer(df: pd.DataFrame, layer_value: str):
    if "aggregation" in df.columns and (df["aggregation"] == layer_value).any():
        return df[df["aggregation"] == layer_value].copy(), layer_value
    return df.copy(), None

def _to_num(df: pd.DataFrame, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def _get_ms(row: pd.Series, key: str, suf="median_ms"):
    val = row.get(f"{key}_{suf}", np.nan)
    return float(val) if pd.notna(val) else np.nan

def _cum_from_consumer_durations(row: pd.Series, ci: str):
    """
    Build consumer cumulative arrays with VXLAN+Post-check merged into one step.
    Returns (y, y25, y75, ystd) in SECONDS; y25/y75/ystd can be None if not requested.
    """
    base0 = 0.0
    # first three increments (medians):
    incs = [
        _get_ms(row, "dur_bid_collection", "median_ms"),
        _get_ms(row, "dur_winner_selection", "median_ms"),
        _get_ms(row, "dur_provider_deploy_confirm", "median_ms"),
    ]
    # combined last increment (medians)
    vx_m  = _get_ms(row, "dur_vxlan_setup", "median_ms")
    fed_m = _get_ms(row, "dur_federation_completed", "median_ms")
    incs.append((vx_m + fed_m) if (not np.isnan(vx_m) and not np.isnan(fed_m)) else np.nan)

    y = [base0]
    for inc_ms in incs:
        inc_s = inc_ms/1000.0 if not np.isnan(inc_ms) else np.nan
        y.append(y[-1] + inc_s if (not np.isnan(y[-1]) and not np.isnan(inc_s)) else np.nan)
    y = np.array(y, dtype=float)

    y25 = y75 = ystd = None
    if ci == "iqr":
        inc25 = [
            _get_ms(row, "dur_bid_collection", "p25_ms"),
            _get_ms(row, "dur_winner_selection", "p25_ms"),
            _get_ms(row, "dur_provider_deploy_confirm", "p25_ms"),
        ]
        vx25 = _get_ms(row, "dur_vxlan_setup", "p25_ms")
        fed25 = _get_ms(row, "dur_federation_completed", "p25_ms")
        inc25.append((vx25 + fed25) if (not np.isnan(vx25) and not np.isnan(fed25)) else np.nan)

        inc75 = [
            _get_ms(row, "dur_bid_collection", "p75_ms"),
            _get_ms(row, "dur_winner_selection", "p75_ms"),
            _get_ms(row, "dur_provider_deploy_confirm", "p75_ms"),
        ]
        vx75 = _get_ms(row, "dur_vxlan_setup", "p75_ms")
        fed75 = _get_ms(row, "dur_federation_completed", "p75_ms")
        inc75.append((vx75 + fed75) if (not np.isnan(vx75) and not np.isnan(fed75)) else np.nan)

        y25 = [base0]; y75 = [base0]
        for a, b in zip(inc25, inc75):
            a = a/1000.0 if not np.isnan(a) else np.nan
            b = b/1000.0 if not np.isnan(b) else np.nan
            y25.append(y25[-1] + a if (not np.isnan(y25[-1]) and not np.isnan(a)) else np.nan)
            y75.append(y75[-1] + b if (not np.isnan(y75[-1]) and not np.isnan(b)) else np.nan)
        y25 = np.array(y25, dtype=float)
        y75 = np.array(y75, dtype=float)

    if ci == "std":
        # step-by-step stds; last std is quadrature of VXLAN and Post-check stds
        sds = [
            _get_ms(row, "dur_bid_collection", "std_ms"),
            _get_ms(row, "dur_winner_selection", "std_ms"),
            _get_ms(row, "dur_provider_deploy_confirm", "std_ms"),
        ]
        vx_sd  = _get_ms(row, "dur_vxlan_setup", "std_ms")
        fed_sd = _get_ms(row, "dur_federation_completed", "std_ms")
        if not np.isnan(vx_sd) and not np.isnan(fed_sd):
            sds.append(math.sqrt((vx_sd/1000.0)**2 + (fed_sd/1000.0)**2)*1000.0)  # keep ms for now
        else:
            sds.append(np.nan)

        sigmas2 = []
        out = [0.0]
        for sd_ms in sds:
            sigma = (sd_ms/1000.0) if (not np.isnan(sd_ms)) else 0.0
            sigmas2.append(sigma**2)
            out.append(math.sqrt(sum(sigmas2)))
        ystd = np.array(out, dtype=float)

    return y, y25, y75, ystd

def _cumulative_from_durations(row: pd.Series, base0: float, keys: list, suffix="median_ms"):
    """Generic cumulative medians in seconds from a list of duration keys."""
    y = [base0]
    for k in keys:
        val_ms = row.get(f"{k}_{suffix}", np.nan)
        inc = float(val_ms) / 1000.0 if pd.notna(val_ms) else np.nan
        y.append(y[-1] + inc if (not np.isnan(y[-1]) and not np.isnan(inc)) else np.nan)
    return np.array(y, dtype=float)

def _cumulative_ribbon(row: pd.Series, base0: float, keys: list, lo_suf="p25_ms", hi_suf="p75_ms"):
    """Generic cumulative p25/p75 ribbons in seconds by summing per-step p25/p75."""
    y25 = [base0]; y75 = [base0]
    for k in keys:
        v25 = row.get(f"{k}_{lo_suf}", np.nan)
        v75 = row.get(f"{k}_{hi_suf}", np.nan)
        inc25 = float(v25) / 1000.0 if pd.notna(v25) else np.nan
        inc75 = float(v75) / 1000.0 if pd.notna(v75) else np.nan
        y25.append(y25[-1] + inc25 if (not np.isnan(y25[-1]) and not np.isnan(inc25)) else np.nan)
        y75.append(y75[-1] + inc75 if (not np.isnan(y75[-1]) and not np.isnan(inc75)) else np.nan)
    return np.array(y25, dtype=float), np.array(y75, dtype=float)

def _cumulative_std(row: pd.Series, keys: list, std_suf="std_ms"):
    """Generic cumulative ±STD in seconds (quadrature of step stds)."""
    sigmas2 = []
    out = []
    for k in keys:
        s = row.get(f"{k}_{std_suf}", np.nan)
        sigma = float(s)/1000.0 if pd.notna(s) else 0.0
        sigmas2.append(sigma**2)
        out.append(math.sqrt(sum(sigmas2)))
    return np.array([0.0] + out, dtype=float)

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ci", choices=["none", "iqr", "std"], default="none",
                    help="Show variability: 'iqr' (p25–p75 ribbon) or 'std' (±STD error bars). Default: none.")
    return ap.parse_args()

def main():
    args = parse_args()
    if not C_TIMELINE.exists() or not P_TIMELINE.exists():
        raise SystemExit("Expected timeline CSVs not found under multiple-offers/_summary/.")

    cons = pd.read_csv(C_TIMELINE)
    prov = pd.read_csv(P_TIMELINE)

    # prefer low-noise layers
    cons, cons_layer = _pick_layer(cons, "per_consumer_median")
    prov, prov_layer = _pick_layer(prov, "per_provider_median")

    # filter scenarios
    cons = cons[cons["mec_count"].isin(KEEP_COUNTS) & cons["consensus"].isin(CONSENSUS_ORDER)].copy()
    prov = prov[prov["mec_count"].isin(KEEP_COUNTS) & prov["consensus"].isin(CONSENSUS_ORDER)].copy()

    # ensure numeric columns exist for medians (+ IQR / std if requested)
    c_need = [f"{k}_median_ms" for k,_ in C_FIRST3] + [
        "dur_vxlan_setup_median_ms", "dur_federation_completed_median_ms"
    ]
    p_need = [f"{k}_median_ms" for k,_ in P_DURS]
    if args.ci == "iqr":
        c_need += [f"{k}_p25_ms" for k,_ in C_FIRST3] + ["dur_vxlan_setup_p25_ms","dur_federation_completed_p25_ms"]
        c_need += [f"{k}_p75_ms" for k,_ in C_FIRST3] + ["dur_vxlan_setup_p75_ms","dur_federation_completed_p75_ms"]
        p_need += [f"{k}_p25_ms" for k,_ in P_DURS] + [f"{k}_p75_ms" for k,_ in P_DURS]
    if args.ci == "std":
        c_need += [f"{k}_std_ms" for k,_ in C_FIRST3] + ["dur_vxlan_setup_std_ms","dur_federation_completed_std_ms"]
        p_need += [f"{k}_std_ms" for k,_ in P_DURS]
    cons = _to_num(cons, c_need)
    prov = _to_num(prov, p_need)

    # style
    sns.set_theme(context="paper", style="ticks")
    sns.set_context("paper", font_scale=1.5)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig, (axc, axp) = plt.subplots(1, 2, figsize=(15, 10))

    # ------------------------- Consumer plot -------------------------
    x_c = np.arange(len(C_LABELS)) + 1
    handles_c, labels_c = [], []
    for (cns, mec) in SERIES:
        row = cons[(cons["consensus"] == cns) & (cons["mec_count"] == mec)]
        if row.empty:
            continue
        r = row.iloc[0]
        y, y25, y75, ystd = _cum_from_consumer_durations(r, args.ci)
        color = PALETTE[(cns, mec)]
        line, = axc.plot(x_c, y, marker="o", linewidth=2.0, markersize=5, color=color,
                         label=f"{cns.capitalize()} – {mec} MECs")
        if args.ci == "iqr" and y25 is not None and y75 is not None:
            axc.fill_between(x_c, y25, y75, color=color, alpha=0.15, linewidth=0)
        elif args.ci == "std" and ystd is not None:
            axc.errorbar(x_c, y, yerr=ystd, fmt="none", ecolor=color, elinewidth=1.2, capsize=3)

        handles_c.append(line); labels_c.append(line.get_label())

    axc.set_xticks(x_c, C_LABELS)
    axc.set_xlabel("Federation Procedures — Consumer")
    axc.set_ylabel("Time (s)")
    axc.grid(True, which="both", axis="both", linestyle="--", color="grey", alpha=0.5)
    legc = axc.legend(handles_c, labels_c, ncols=2, loc="lower right", frameon=True, fontsize=9)
    legc.get_frame().set_edgecolor("black"); legc.get_frame().set_linewidth(1.1)

    # ------------------------- Provider plot -------------------------
    x_p = np.arange(len(P_LABELS)) + 1
    handles_p, labels_p = [], []
    for (cns, mec) in SERIES:
        row = prov[(prov["consensus"] == cns) & (prov["mec_count"] == mec)]
        if row.empty:
            continue
        r = row.iloc[0]
        y = _cumulative_from_durations(r, 0.0, [k for k,_ in P_DURS])
        color = PALETTE[(cns, mec)]
        line, = axp.plot(x_p, y, marker="o", linewidth=2.0, markersize=5, color=color,
                         label=f"{cns.capitalize()}–{mec}")
        if args.ci == "iqr":
            y25, y75 = _cumulative_ribbon(r, 0.0, [k for k,_ in P_DURS])
            axp.fill_between(x_p, y25, y75, color=color, alpha=0.15, linewidth=0)
        elif args.ci == "std":
            s = _cumulative_std(r, [k for k,_ in P_DURS])
            axp.errorbar(x_p, y, yerr=s, fmt="none", ecolor=color, elinewidth=1.2, capsize=3)

        handles_p.append(line); labels_p.append(line.get_label())

    axp.set_xticks(x_p, P_LABELS)
    axp.set_xlabel("Federation Procedures — Provider")
    axp.grid(True, which="both", axis="both", linestyle="--", color="grey", alpha=0.5)
    legp = axp.legend(handles_p, labels_p, ncols=2, loc="lower right", frameon=True, fontsize=9)
    legp.get_frame().set_edgecolor("black"); legp.get_frame().set_linewidth(1.1)

    plt.subplots_adjust(bottom=0.28, wspace=0.18)
    fig.savefig(OUT, bbox_inches="tight", dpi=300)
    print(f"Saved {OUT}")
    print(f"[layers] consumer={cons_layer or 'unknown'} | provider={prov_layer or 'unknown'} | CI={args.ci}")

    plt.show()

if __name__ == "__main__":
    main()
