#!/usr/bin/env python3
# lineplot_latency.py
# Two-panel cumulative step lines (Consumer & Provider), with per-panel legends.
# - Consumer starts at "Service Announced" = 0 s.
# - Provider includes "Deploy Containers & VXLAN Setup" then "Confirm Deployment"
#   (both end at the same time given available summary granularity).
# - Panels use independent y-axes; no value annotations inside panels.
# Run from: experiments/

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# --- locations (relative to this script being in experiments/) ---
C_SUM = Path("multiple-offers/_summary/consumer_summary.csv")
P_SUM = Path("multiple-offers/_summary/provider_summary.csv")
OUT   = Path("plots/federation_cumulative_steps.pdf")

KEEP_COUNTS     = [4, 10, 20, 30]
CONSENSUS_ORDER = ["clique", "qbft"]
SERIES = [(c, n) for c in CONSENSUS_ORDER for n in KEEP_COUNTS]

# color-blind–safe palette per (consensus, mec_count)
PALETTE = {
    ("clique", 4):  "#0072B2",
    ("clique", 10): "#009E73",
    ("clique", 20): "#56B4E9",
    ("clique", 30): "#CC79A7",
    ("qbft", 4):    "#D55E00",
    ("qbft", 10):   "#E69F00",
    ("qbft", 20):   "#F0E442",
    ("qbft", 30):   "#000000",
}

def _num(x):
    try:
        return float(x)
    except Exception:
        return float("nan")

def _pick_layer(df: pd.DataFrame, pref: str):
    if "aggregation" in df.columns and (df["aggregation"] == pref).any():
        return df[df["aggregation"] == pref].copy(), pref
    return df.copy(), None

def _ensure_numeric(df: pd.DataFrame, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def main():
    if not C_SUM.exists() or not P_SUM.exists():
        raise SystemExit("Expected summary CSVs not found under multiple-offers/_summary/.")

    cons = pd.read_csv(C_SUM)
    prov = pd.read_csv(P_SUM)

    # prefer low-noise aggregations
    cons, cons_layer = _pick_layer(cons, "per_consumer_median")
    prov, prov_layer = _pick_layer(prov, "per_provider_median")

    # keep settings of interest
    cons = cons[cons["mec_count"].isin(KEEP_COUNTS) & cons["consensus"].isin(CONSENSUS_ORDER)].copy()
    prov = prov[prov["mec_count"].isin(KEEP_COUNTS) & prov["consensus"].isin(CONSENSUS_ORDER)].copy()

    # numeric conversions (ms columns)
    cons_cols = [
        "bid_collection_median_ms","winner_selection_median_ms","provider_deploy_median_ms",
        "vxlan_setup_median_ms","total_median_ms"
    ]
    prov_cols = [
        "bid_sending_median_ms","winner_wait_median_ms","confirm_all_median_ms"
    ]
    cons = _ensure_numeric(cons, cons_cols)
    prov = _ensure_numeric(prov, prov_cols)

    # x ticks & labels
    # Consumer: include time-zero anchor
    c_steps = [
        ("Service Announced",   None),  # 0 s anchor
        ("Bids Collected",      "bid_collection_median_ms"),
        ("Provider Selected",     "winner_selection_median_ms"),
        ("Provider Confirmed",  "provider_deploy_median_ms"),
        ("VXLAN Configured",    "vxlan_setup_median_ms"),
        ("Federation Completed", "total_median_ms"),  # final anchor uses total directly
    ]
    c_labels = [s[0] for s in c_steps]
    c_x = list(range(1, len(c_labels)+1))

    # Provider: start at Bids Offered; show Deploy+VXLAN then Confirm (same cumulative time)
    p_steps = [
        ("Bids Offered",                    "bid_sending_median_ms"),
        ("Winners Received",                "winner_wait_median_ms"),
        (f"Deploy Containers \n& VXLAN Setup", "confirm_all_median_ms"),  # cumulative to here
        ("Confirm Deployment",              None),                     # same endpoint (no extra data to split)
    ]
    p_labels = [s[0] for s in p_steps]
    p_x = list(range(1, len(p_labels)+1))

    def series_consumer(cns, mec):
        row = cons[(cons["consensus"] == cns) & (cons["mec_count"] == mec)]
        if row.empty:
            return None
        r = row.iloc[0]
        s0 = 0.0
        s1 = _num(r["bid_collection_median_ms"]) / 1000.0
        s2 = s1 + _num(r["winner_selection_median_ms"]) / 1000.0
        s3 = s2 + _num(r["provider_deploy_median_ms"]) / 1000.0
        s4 = s3 + _num(r["vxlan_setup_median_ms"]) / 1000.0
        s5 = _num(r["total_median_ms"]) / 1000.0  # anchor from total
        return [s0, s1, s2, s3, s4, s5]

    def series_provider(cns, mec):
        row = prov[(prov["consensus"] == cns) & (prov["mec_count"] == mec)]
        if row.empty:
            return None
        r = row.iloc[0]
        s1 = _num(r["bid_sending_median_ms"]) / 1000.0
        s2 = s1 + _num(r["winner_wait_median_ms"]) / 1000.0
        s3 = s2 + _num(r["confirm_all_median_ms"]) / 1000.0  # includes deploy+vxlan+confirm
        s4 = s3  # no separate metric to extend beyond s3
        return [s1, s2, s3, s4]

    # --- plotting ---
    OUT.parent.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"figure.dpi": 120})

    # Taller, slightly narrower; independent y-axes (no sharey)
    fig, (axc, axp) = plt.subplots(1, 2, figsize=(9.0, 8.0))

    # Consumer panel
    handles_c = []
    labels_c = []
    for (cns, mec) in SERIES:
        y = series_consumer(cns, mec)
        if y is None:
            continue
        line, = axc.plot(
            c_x, y, marker="o", linewidth=2.0, markersize=5,
            color=PALETTE[(cns, mec)], label=f"{cns.capitalize()}–{mec}"
        )
        handles_c.append(line); labels_c.append(line.get_label())

    axc.set_xticks(c_x, c_labels, rotation=90, ha="center")
    axc.set_xlabel("Consumer Federation Procedure")
    axc.set_ylabel("Time (s)")
    # axc.set_title("Consumer — Cumulative Median per Step")
    axc.grid(True, which="both", axis="both", linestyle="--", color="grey", alpha=0.5)
    legc = axc.legend(handles_c, labels_c, ncols=2, loc="upper left", frameon=True, fontsize=9)
    legc.get_frame().set_alpha(1.0)

    # Provider panel
    handles_p = []
    labels_p = []
    for (cns, mec) in SERIES:
        y = series_provider(cns, mec)
        if y is None:
            continue
        line, = axp.plot(
            p_x, y, marker="o", linewidth=2.0, markersize=5,
            color=PALETTE[(cns, mec)], label=f"{cns.capitalize()}–{mec}"
        )
        handles_p.append(line); labels_p.append(line.get_label())

    axp.set_xticks(p_x, p_labels, rotation=90, ha="center")
    axp.set_xlabel("Provider Federation Procedure")
    # axp.set_title("Provider — Cumulative Median per Step")
    axp.grid(True, which="both", axis="both", linestyle="--", color="grey", alpha=0.5)
    legp = axp.legend(handles_p, labels_p, ncols=2, loc="upper left", frameon=True, fontsize=9)
    legp.get_frame().set_alpha(1.0)

    # space for vertical labels
    plt.subplots_adjust(bottom=0.28, wspace=0.18)
    fig.savefig(OUT, bbox_inches="tight")
    print(f"Saved {OUT}")
    print(f"[layers] consumer={cons_layer or 'unknown'} | provider={prov_layer or 'unknown'}")

    # GUI preview
    plt.show()

if __name__ == "__main__":
    main()
