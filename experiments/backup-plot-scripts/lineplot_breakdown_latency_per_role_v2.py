#!/usr/bin/env python3
# lineplot_latency_from_durations.py
# Two-panel cumulative step lines (Consumer & Provider), with non-overlapping value labels.

import argparse
import math
from pathlib import Path
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# Paths to timeline summaries
C_TIMELINE = Path("multiple-offers/_summary/consumer_timeline_summary.csv")
P_TIMELINE = Path("multiple-offers/_summary/provider_timeline_summary.csv")
OUT        = Path("plots/federation_cumulative_steps_from_durations.pdf")

KEEP_COUNTS     = [4, 10, 20, 30]
CONSENSUS_ORDER = ["clique", "qbft"]
SERIES = [(c, n) for c in CONSENSUS_ORDER for n in KEEP_COUNTS]

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
C_FIRST3 = [
    ("dur_bid_collection",          "Bid Collection"),
    ("dur_winner_selection",        "Winner Selection"),
    ("dur_provider_deploy_confirm", "Provider Deploy Confirm"),
]
C_LABELS = [
    "Service\nAnnounced",
    "Bid(s)\nReceived",
    "Provider\nChosen",
    "Deployment\nConfirmation\nReceived",
    "Federation\nCompleted",  # (VXLAN Setup + Post-check)
]

# ----------------------------- PROVIDER ----------------------------
P_DURS = [
    ("dur_winners_received",   "Winners Received"),
    ("dur_confirm_deployment", "Confirm Deployment"),
]
P_LABELS = [
    "All Bids\nOffered",
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
    base0 = 0.0
    incs = [
        _get_ms(row, "dur_bid_collection", "median_ms"),
        _get_ms(row, "dur_winner_selection", "median_ms"),
        _get_ms(row, "dur_provider_deploy_confirm", "median_ms"),
    ]
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
        sds = [
            _get_ms(row, "dur_bid_collection", "std_ms"),
            _get_ms(row, "dur_winner_selection", "std_ms"),
            _get_ms(row, "dur_provider_deploy_confirm", "std_ms"),
        ]
        vx_sd  = _get_ms(row, "dur_vxlan_setup", "std_ms")
        fed_sd = _get_ms(row, "dur_federation_completed", "std_ms")
        sds.append(math.sqrt(vx_sd**2 + fed_sd**2) if (not np.isnan(vx_sd) and not np.isnan(fed_sd)) else np.nan)

        sigmas2 = []
        out = [0.0]
        for sd_ms in sds:
            sigma = (sd_ms/1000.0) if (not np.isnan(sd_ms)) else 0.0
            sigmas2.append(sigma**2)
            out.append(math.sqrt(sum(sigmas2)))
        ystd = np.array(out, dtype=float)

    return y, y25, y75, ystd

def _cumulative_from_durations(row: pd.Series, base0: float, keys: list, suffix="median_ms"):
    y = [base0]
    for k in keys:
        val_ms = row.get(f"{k}_{suffix}", np.nan)
        inc = float(val_ms) / 1000.0 if pd.notna(val_ms) else np.nan
        y.append(y[-1] + inc if (not np.isnan(y[-1]) and not np.isnan(inc)) else np.nan)
    return np.array(y, dtype=float)

def _cumulative_ribbon(row: pd.Series, base0: float, keys: list, lo_suf="p25_ms", hi_suf="p75_ms"):
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
    sigmas2 = []
    out = []
    for k in keys:
        s = row.get(f"{k}_{std_suf}", np.nan)
        sigma = float(s)/1000.0 if pd.notna(s) else 0.0
        sigmas2.append(sigma**2)
        out.append(math.sqrt(sum(sigmas2)))
    return np.array([0.0] + out, dtype=float)

# ---------- label helpers (non-overlapping) ----------
def _fmt_s(v):
    return f"{v:.1f}s" if np.isfinite(v) else ""

def _annotate_axis_no_overlap(ax, series_list, mode="last",
                              position="top",
                              min_gap_frac=0.045,  # spacing between stacked labels
                              offset_frac=0.02):   # small offset away from point
    """
    Place labels after plotting, stacking them so they don't overlap.
    - series_list: list of dicts {x: np.array, y: np.array, color: str}
    - mode: 'none' | 'last' | 'all'
    - position: 'top' | 'bottom' | 'left' | 'right'
    - min_gap_frac: minimal separation between labels as fraction of axis span
    - offset_frac: small gap between point and label as fraction of axis span
    """
    if mode == "none" or not series_list:
        return

    ymin, ymax = ax.get_ylim()
    xmin, xmax = ax.get_xlim()
    yr = max(1e-9, ymax - ymin)
    xr = max(1e-9, xmax - xmin)
    vgap = yr * float(min_gap_frac)
    hgap = xr * float(min_gap_frac)
    voff = yr * float(offset_frac)
    hoff = xr * float(offset_frac)

    n_steps = len(series_list[0]["x"])
    step_idxs = [n_steps-1] if mode == "last" else range(n_steps)

    for j in step_idxs:
        # gather points at this step
        pts = []
        for s in series_list:
            xj, yj = float(s["x"][j]), float(s["y"][j])
            if np.isfinite(yj):
                pts.append({"x": xj, "y": yj, "c": s["color"]})
        if not pts:
            continue

        if position in ("top", "bottom"):
            # vertical stacking at fixed x
            asc = (position == "top")
            pts.sort(key=lambda d: d["y"], reverse=not asc)
            cur = (-np.inf if asc else np.inf)
            for p in pts:
                y0 = p["y"]
                if asc:
                    ylab = max(y0 + voff, cur + vgap)
                    ax.plot([p["x"], p["x"]], [y0, ylab], color=p["c"], lw=0.8, alpha=0.7, zorder=3)
                    ax.text(p["x"], ylab, _fmt_s(y0), ha="center", va="bottom",
                            fontsize=9, color=p["c"],
                            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=p["c"], lw=0.8, alpha=0.9),
                            zorder=4)
                    cur = ylab
                else:
                    ylab = min(y0 - voff, cur - vgap)
                    ax.plot([p["x"], p["x"]], [ylab, y0], color=p["c"], lw=0.8, alpha=0.7, zorder=3)
                    ax.text(p["x"], ylab, _fmt_s(y0), ha="center", va="top",
                            fontsize=9, color=p["c"],
                            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=p["c"], lw=0.8, alpha=0.9),
                            zorder=4)
                    cur = ylab
        else:
            # horizontal stacking at fixed y
            pts.sort(key=lambda d: d["y"])  # helps minimize connector crossings
            if position == "right":
                cur = -np.inf
                for p in pts:
                    xlab = max(p["x"] + hoff, cur + hgap)
                    ax.plot([p["x"], xlab], [p["y"], p["y"]], color=p["c"], lw=0.8, alpha=0.7, zorder=3)
                    ax.text(xlab, p["y"], _fmt_s(p["y"]), ha="left", va="center",
                            fontsize=9, color=p["c"],
                            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=p["c"], lw=0.8, alpha=0.9),
                            zorder=4)
                    cur = xlab
            else:  # left
                cur = np.inf
                for p in pts:
                    xlab = min(p["x"] - hoff, cur - hgap)
                    ax.plot([xlab, p["x"]], [p["y"], p["y"]], color=p["c"], lw=0.8, alpha=0.7, zorder=3)
                    ax.text(xlab, p["y"], _fmt_s(p["y"]), ha="right", va="center",
                            fontsize=9, color=p["c"],
                            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=p["c"], lw=0.8, alpha=0.9),
                            zorder=4)
                    cur = xlab


def _alt_bands(ax, n_steps):
    ymin, ymax = ax.get_ylim()
    for k in range(n_steps):
        if k % 2 == 0:
            ax.axvspan(k+0.5, k+1.5, color="0.92", lw=0, zorder=0)

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ci", choices=["none", "iqr", "std"], default="none",
                    help="Show variability: 'iqr' (p25–p75 ribbon) or 'std' (±STD error bars).")
    ap.add_argument("--labels", choices=["none","last","all"], default="last",
                    help="Annotate values: none, last point, or all points (non-overlapping).")
    # parse_args()
    ap.add_argument("--label-pos", choices=["top","bottom","left","right"],
                    default="top",
                    help="Where to place value labels relative to points.") 
    ap.add_argument("--bands", action="store_true",
                    help="Draw alternating vertical step bands.")
    return ap.parse_args()

def main():
    args = parse_args()
    if not C_TIMELINE.exists() or not P_TIMELINE.exists():
        raise SystemExit("Expected timeline CSVs not found under multiple-offers/_summary/.")

    cons = pd.read_csv(C_TIMELINE)
    prov = pd.read_csv(P_TIMELINE)

    cons, cons_layer = _pick_layer(cons, "per_consumer_median")
    prov, prov_layer = _pick_layer(prov, "per_provider_median")

    cons = cons[cons["mec_count"].isin(KEEP_COUNTS) & cons["consensus"].isin(CONSENSUS_ORDER)].copy()
    prov = prov[prov["mec_count"].isin(KEEP_COUNTS) & prov["consensus"].isin(CONSENSUS_ORDER)].copy()

    c_need = [f"{k}_median_ms" for k,_ in C_FIRST3] + ["dur_vxlan_setup_median_ms", "dur_federation_completed_median_ms"]
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

    sns.set_theme(context="paper", style="ticks")
    sns.set_context("paper", font_scale=1.5)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig, (axc, axp) = plt.subplots(1, 2, figsize=(15, 10))

    # ------------------------- Consumer plot -------------------------
    x_c = np.arange(len(C_LABELS)) + 1
    handles_c, labels_c = [], []
    cons_series = []  # collect for non-overlap labeling
    for (cns, mec) in SERIES:
        row = cons[(cons["consensus"] == cns) & (cons["mec_count"] == mec)]
        if row.empty:
            continue
        r = row.iloc[0]
        y, y25, y75, ystd = _cum_from_consumer_durations(r, args.ci)
        color = PALETTE[(cns, mec)]
        line, = axc.plot(x_c, y, marker="o", linewidth=2.4, markersize=6.5,
                         markeredgecolor="white", markeredgewidth=1.4,
                         color=color, label=f"{cns.capitalize()} – {mec} MECs")
        if args.ci == "iqr" and y25 is not None and y75 is not None:
            axc.fill_between(x_c, y25, y75, color=color, alpha=0.18, linewidth=0)
        elif args.ci == "std" and ystd is not None:
            axc.errorbar(x_c, y, yerr=ystd, fmt="none", ecolor=color, elinewidth=1.3, capsize=3)

        handles_c.append(line); labels_c.append(line.get_label())
        cons_series.append({"x": x_c, "y": y, "color": color})

    axc.set_xticks(x_c, C_LABELS)
    axc.set_xlabel("Federation Procedures — Consumer")
    axc.set_ylabel("Time (s)")
    axc.grid(True, which="both", axis="both", linestyle="--", color="grey", alpha=0.5)
    fig.canvas.draw_idle()
    if args.bands: _alt_bands(axc, len(C_LABELS))

    
    ymin, ymax = axc.get_ylim()
    xmin, xmax = axc.get_xlim()
    yr, xr = ymax - ymin, xmax - xmin

    if args.label_pos == "top":
        axc.set_ylim(ymin, ymax + 0.10*yr)
    elif args.label_pos == "bottom":
        axc.set_ylim(ymin - 0.10*yr, ymax)
    elif args.label_pos == "right":
        axc.set_xlim(xmin, xmax + 0.18*xr)
    elif args.label_pos == "left":
        axc.set_xlim(xmin - 0.18*xr, xmax)

    _annotate_axis_no_overlap(axc, cons_series,
                            mode=args.labels,
                            position=args.label_pos,
                            min_gap_frac=0.045)

    legc = axc.legend(handles_c, labels_c, ncols=2, loc="lower right", frameon=True, fontsize=9)
    legc.get_frame().set_edgecolor("black"); legc.get_frame().set_linewidth(1.1)

    # ------------------------- Provider plot -------------------------
    x_p = np.arange(len(P_LABELS)) + 1
    handles_p, labels_p = [], []
    prov_series = []
    for (cns, mec) in SERIES:
        row = prov[(prov["consensus"] == cns) & (prov["mec_count"] == mec)]
        if row.empty:
            continue
        r = row.iloc[0]
        y = _cumulative_from_durations(r, 0.0, [k for k,_ in P_DURS])
        color = PALETTE[(cns, mec)]
        line, = axp.plot(x_p, y, marker="o", linewidth=2.4, markersize=6.5,
                         markeredgecolor="white", markeredgewidth=1.4,
                         color=color, label=f"{cns.capitalize()} – {mec} MECs")
        if args.ci == "iqr":
            y25, y75 = _cumulative_ribbon(r, 0.0, [k for k,_ in P_DURS])
            axp.fill_between(x_p, y25, y75, color=color, alpha=0.18, linewidth=0)
        elif args.ci == "std":
            s = _cumulative_std(r, [k for k,_ in P_DURS])
            axp.errorbar(x_p, y, yerr=s, fmt="none", ecolor=color, elinewidth=1.3, capsize=3)

        handles_p.append(line); labels_p.append(line.get_label())
        prov_series.append({"x": x_p, "y": y, "color": color})

    axp.set_xticks(x_p, P_LABELS)
    axp.set_xlabel("Federation Procedures — Provider")
    axp.grid(True, which="both", axis="both", linestyle="--", color="grey", alpha=0.5)
    fig.canvas.draw_idle()
    if args.bands:
        _alt_bands(axp, len(P_LABELS))
    ymin, ymax = axc.get_ylim()
    xmin, xmax = axc.get_xlim()
    yr, xr = ymax - ymin, xmax - xmin

    if args.label_pos == "top":
        axc.set_ylim(ymin, ymax + 0.10*yr)
    elif args.label_pos == "bottom":
        axc.set_ylim(ymin - 0.10*yr, ymax)
    elif args.label_pos == "right":
        axc.set_xlim(xmin, xmax + 0.18*xr)
    elif args.label_pos == "left":
        axc.set_xlim(xmin - 0.18*xr, xmax)

    _annotate_axis_no_overlap(axp, prov_series,
                            mode=args.labels,
                            position=args.label_pos,
                            min_gap_frac=0.045)

    legp = axp.legend(handles_p, labels_p, ncols=2, loc="lower right", frameon=True, fontsize=9)
    legp.get_frame().set_edgecolor("black"); legp.get_frame().set_linewidth(1.1)

    plt.subplots_adjust(bottom=0.28, wspace=0.18)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight", dpi=300)
    print(f"Saved {OUT}")
    print(f"[layers] consumer={cons_layer or 'unknown'} | provider={prov_layer or 'unknown'} | CI={args.ci} | labels={args.labels} | bands={args.bands}")

    plt.show()

if __name__ == "__main__":
    main()
