#!/usr/bin/env python3
"""
Approximate ECDF of end-to-end federation latency (consumer perspective),
built from scenario-level summary quantiles in:
  experiments/multiple-offers/_summary/consumer_timeline_summary.csv

We use the reported quantiles for dur_total_*:
  min, p25, median, p75, p95, max
to construct a smooth, monotone curve via linear interpolation.

Outputs:
  experiments/plots/cdf_latency_multiple_offers_total.pdf
"""

from pathlib import Path
import argparse
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from math import floor

ROOT = Path(__file__).resolve().parent
IN_CSV = ROOT / "multiple-offers" / "_summary" / "consumer_timeline_summary.csv"
OUT_DIR = ROOT / "plots"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PDF = OUT_DIR / "cdf_latency_multiple_offers_total.pdf"

KEEP_COUNTS     = [4, 10, 20, 30]
CONSENSUS_ORDER = ["clique", "qbft"]
CONSENSUS_LABEL = {"clique": "Clique", "qbft": "QBFT"}

# Colors for 4/10/20/30
PALETTE   = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
MEC_LABEL = {4: "4 MECs", 10: "10 MECs", 20: "20 MECs", 30: "30 MECs"}

LOW_LATENCY_TH_S  = 18.0
HIGH_LATENCY_TH_S = 50.0  # log values above this

REQUIRED_COLS = {
    "consensus", "mec_count",
    "dur_total_min_ms","dur_total_p25_ms","dur_total_median_ms",
    "dur_total_p75_ms","dur_total_p95_ms","dur_total_max_ms",
}

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlo", choices=["auto", "zero"], default="zero",
                    help="Lower x-axis bound. 'auto' (near min) or 'zero'. Default: zero.")
    ap.add_argument("--qhi", type=float, default=0.995,
                    help="Upper x-axis quantile (0–1]. Default 0.995.")
    ap.add_argument("--no-show", action="store_true",
                    help="Skip GUI preview; only save the PDF.")
    return ap.parse_args()

def load_summary(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"[error] not found: {path}")

    df = pd.read_csv(path)
    df = df.rename(columns={"consensus_": "consensus", "mec_count_": "mec_count"})
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise SystemExit(f"[error] missing columns in {path.name}: {sorted(missing)}")

    # types
    df["consensus"] = df["consensus"].astype(str).str.lower()
    df["mec_count"] = pd.to_numeric(df["mec_count"], errors="coerce")

    # keep only desired mec counts and valid consensus labels
    df = df[df["mec_count"].isin(KEEP_COUNTS) & df["consensus"].isin(CONSENSUS_ORDER)].copy()

    # to seconds
    for c in list(REQUIRED_COLS - {"consensus","mec_count"}):
        df[c.replace("_ms","_s")] = pd.to_numeric(df[c], errors="coerce") / 1000.0

    return df

def stylize_axes(ax):
    ax.grid(True, which="both", axis="both", linestyle="--", color="grey", alpha=0.5)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_color("black")
        ax.spines[side].set_linewidth(1.1)
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("Cumulative Distribution Function (CDF)")

def make_curve_from_quantiles(row: pd.Series, npts: int = 1000):
    """
    Build an approximate ECDF curve F(x) using the available quantiles.
    We construct the inverse-CDF (quantile function) on these support points:
      p:  0,   .25,  .5,  .75,  .95, 1
      x:  min, p25,  med, p75,  p95, max
    Then interpolate linearly and return (xs, ps).
    """
    qs = np.array([
        row["dur_total_min_s"],
        row["dur_total_p25_s"],
        row["dur_total_median_s"],
        row["dur_total_p75_s"],
        row["dur_total_p95_s"],
        row["dur_total_max_s"],
    ], dtype=float)

    ps = np.array([0.0, 0.25, 0.5, 0.75, 0.95, 1.0], dtype=float)

    # drop NaNs, enforce monotonic non-decreasing x
    mask = np.isfinite(qs)
    qs, ps = qs[mask], ps[mask]
    if qs.size < 2:
        return np.array([]), np.array([])

    qs = np.maximum.accumulate(qs)

    # sample evenly in probability and interpolate quantiles
    p_dense = np.linspace(0.0, 1.0, npts)
    x_dense = np.interp(p_dense, ps, qs)
    return x_dense, p_dense

def compute_xlim(all_x: np.ndarray, qhi: float, xlo_mode: str):
    x_hi = float(np.quantile(all_x, qhi)) if 0 < qhi <= 1.0 else float(np.nanmax(all_x))
    if not np.isfinite(x_hi):
        x_hi = float(np.nanmax(all_x))
    if xlo_mode == "zero":
        x_lo = 0.0
    else:
        vmin = float(np.nanmin(all_x))
        span = max(1.0, x_hi - vmin)
        margin = 0.02 * span
        x_lo = max(0.0, floor((vmin - margin)))
    return x_lo, x_hi

def log_low_high(summary_df: pd.DataFrame, low_th: float, high_th: float):
    for (conc, mc), grp in summary_df.groupby(["consensus", "mec_count"]):
        p25 = grp["dur_total_p25_s"].iloc[0]
        med = grp["dur_total_median_s"].iloc[0]
        p75 = grp["dur_total_p75_s"].iloc[0]
        p95 = grp["dur_total_p95_s"].iloc[0]
        mn  = grp["dur_total_min_s"].iloc[0]
        mx  = grp["dur_total_max_s"].iloc[0]
        if np.isfinite(mn) and mn < low_th:
            print(f"[low-latency][{conc}][{mc} mecs] min={mn:.3f}s (< {low_th:.1f}s)")
        if np.isfinite(p25) and p25 < low_th:
            print(f"[low-latency][{conc}][{mc} mecs] p25={p25:.3f}s (< {low_th:.1f}s)")
        if np.isfinite(mx) and mx > high_th:
            print(f"[high-latency][{conc}][{mc} mecs] max={mx:.3f}s (> {high_th:.1f}s)")
        if np.isfinite(p95) and p95 > high_th:
            print(f"[high-latency][{conc}][{mc} mecs] p95={p95:.3f}s (> {high_th:.1f}s)")

def main():
    args = parse_args()
    df = load_summary(IN_CSV)
    if df.empty:
        raise SystemExit("[error] no data to plot")

    # Build curves and collect all x values to compute global x-limits
    curves = {}  # (consensus,mec_count) -> (xs, ps)
    all_xs = []
    for _, row in df.iterrows():
        key = (row["consensus"], int(row["mec_count"]))
        xs, ps = make_curve_from_quantiles(row)
        curves[key] = (xs, ps)
        if xs.size:
            all_xs.append(xs)

    if not all_xs:
        raise SystemExit("[error] no valid quantile curves to plot")

    all_x_concat = np.concatenate(all_xs)
    x_lo, x_hi = compute_xlim(all_x_concat, qhi=args.qhi, xlo_mode=args.xlo)

    # Logs
    log_low_high(df, LOW_LATENCY_TH_S, HIGH_LATENCY_TH_S)

    # seaborn/mpl style
    sns.set_theme(context="paper", style="ticks")
    sns.set_context("paper", font_scale=1.5)

    fig, axes = plt.subplots(
        1, 2, figsize=(9.5, 4.6),
        gridspec_kw={"wspace": 0.05},
        sharey=True, sharex=True
    )

    color_map = {m: c for m, c in zip(KEEP_COUNTS, PALETTE)}

    for ax, conc in zip(axes, CONSENSUS_ORDER):
        handles, labels = [], []
        ax.set_title(CONSENSUS_LABEL.get(conc, conc.capitalize()))
        for mec in KEEP_COUNTS:
            key = (conc, mec)
            xs, ps = curves.get(key, (np.array([]), np.array([])))
            if xs.size == 0:
                continue
            h, = ax.plot(xs, ps, linewidth=2.2, color=color_map[mec])
            handles.append(h)
            labels.append(f"{MEC_LABEL[mec]}")
        ax.set_xlabel("Latency (s)")
        stylize_axes(ax)
        ax.set_xlim(x_lo, x_hi)
        leg = ax.legend(handles, labels, title=None, frameon=True, loc="lower right", fancybox=True)
        if leg:
            leg.get_frame().set_edgecolor("black"); leg.get_frame().set_linewidth(1.1)

    axes[1].set_ylabel("")

    fig.savefig(OUT_PDF, dpi=300, bbox_inches="tight")
    print(f"Wrote {OUT_PDF}")
    if args.no_show:
        plt.close(fig)
    else:
        plt.show()

if __name__ == "__main__":
    main()
