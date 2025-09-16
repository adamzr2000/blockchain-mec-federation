#!/usr/bin/env python3
"""
Smoothed ECDF (quantile-based) of end-to-end federation latency
(consumer 'c_total_ms'), two panels: Clique (left) and QBFT (right).

- seaborn style: 'ticks'
- dashed grid on both axes
- shared x-axis across panels; lower bound 'zero' by default
- logs if any plotted/raw values are below 18 s or above 50 s

Input:
  experiments/multiple-offers/_summary/consumer_per_service.csv

Output:
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
IN_CSV = ROOT / "multiple-offers" / "_summary" / "consumer_per_service.csv"
OUT_DIR = ROOT / "plots"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PDF = OUT_DIR / "cdf_latency_multiple_offers_total.pdf"

KEEP_COUNTS     = [10, 20, 30]
CONSENSUS_ORDER = ["clique", "qbft"]
CONSENSUS_LABEL = {"clique": "Clique", "qbft": "QBFT"}

# Colors for 10/20/30 (consistent with your palette)
PALETTE   = ["#1f77b4", "#2ca02c", "#ff7f0e"]
MEC_LABEL = {10: "10 MECs", 20: "20 MECs", 30: "30 MECs"}

VALUE_COL = "c_total_ms"
LOW_LATENCY_TH_S  = 18.0
HIGH_LATENCY_TH_S = 50.0  # new: log values above this

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agg", choices=["per_consumer_median", "per_service"],
                    default="per_consumer_median",
                    help="ECDF input aggregation. Default: per_consumer_median (lower noise).")
    ap.add_argument("--xlo", choices=["auto", "zero"], default="zero",
                    help="Lower x-axis bound. 'auto' (near min) or 'zero'. Default: zero.")
    ap.add_argument("--qhi", type=float, default=0.995,
                    help="Upper x-axis quantile (0–1]. Default 0.995.")
    ap.add_argument("--no-show", action="store_true",
                    help="Skip GUI preview; only save the PDF.")
    return ap.parse_args()

def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(columns={"consensus_": "consensus", "mec_count_": "mec_count"})
    needed = {"consensus", "mec_count", "consumer_id", "has_success", VALUE_COL}
    missing = needed - set(df.columns)
    if missing:
        raise SystemExit(f"[error] missing columns: {sorted(missing)}")

    df["consensus"] = df["consensus"].astype(str).str.lower()
    df["mec_count"] = pd.to_numeric(df["mec_count"], errors="coerce")
    df["consumer_id"] = pd.to_numeric(df["consumer_id"], errors="coerce")
    df[VALUE_COL] = pd.to_numeric(df[VALUE_COL], errors="coerce")

    # Keep successes and 10/20/30 only
    df = df[(df["has_success"] == 1) & (df["mec_count"].isin(KEEP_COUNTS))].copy()
    return df.dropna(subset=[VALUE_COL, "consensus", "mec_count", "consumer_id"])

def prep_series(df: pd.DataFrame, agg: str) -> pd.DataFrame:
    if agg == "per_service":
        out = df[["consensus", "mec_count", VALUE_COL]].copy()
    else:  # per_consumer_median (default)
        out = (
            df.groupby(["consensus", "mec_count", "consumer_id"], as_index=False)[VALUE_COL]
              .median()
        )
    out["value_s"] = out[VALUE_COL] / 1000.0
    return out[["consensus", "mec_count", "value_s"]]

def stylize_axes(ax):
    ax.grid(True, which="both", axis="both", linestyle="--", color="grey", alpha=0.5)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_color("black")
        ax.spines[side].set_linewidth(1.1)
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("Cumulative Distribution Function (CDF)")

def smooth_ecdf_line(values: np.ndarray, npts: int = 800):
    """Monotone ECDF via dense quantiles (smooth, no step boxes)."""
    if values.size == 0:
        return np.array([]), np.array([])
    p = np.linspace(0.0, 1.0, npts)
    x = np.quantile(values, p)
    return x, p

def compute_xlim(values: np.ndarray, qhi: float, xlo_mode: str):
    # Upper bound: high quantile (robust to long tails)
    x_hi = float(np.quantile(values, qhi)) if 0 < qhi <= 1.0 else float(np.nanmax(values))
    if not np.isfinite(x_hi):
        x_hi = float(np.nanmax(values))

    if xlo_mode == "zero":
        x_lo = 0.0
    else:
        # Lower bound: just below the global minimum, rounded down to a nice 1s step
        vmin = float(np.nanmin(values))
        span = max(1.0, x_hi - vmin)
        margin = 0.02 * span  # 2% padding
        x_lo = max(0.0, floor((vmin - margin)))
    return x_lo, x_hi

def log_low_latencies(tidy: pd.DataFrame, raw: pd.DataFrame, threshold_s: float = LOW_LATENCY_TH_S):
    print(f"[info] checking plotted values < {threshold_s:.1f}s ...")
    for (conc, mc), grp in tidy.groupby(["consensus", "mec_count"]):
        arr = grp["value_s"].to_numpy()
        if arr.size == 0:
            continue
        below = arr < threshold_s
        if below.any():
            print(f"[low-latency][PLOTTED][{conc}][{mc} mecs] "
                  f"{below.sum()}/{arr.size} < {threshold_s:.1f}s; min={arr.min():.3f}s")

    print(f"[info] checking RAW per-service values < {threshold_s:.1f}s ...")
    raw2 = raw.copy()
    raw2["value_s"] = raw2[VALUE_COL] / 1000.0
    for (conc, mc), grp in raw2.groupby(["consensus", "mec_count"]):
        vals = grp["value_s"].dropna().to_numpy()
        if vals.size == 0:
            continue
        below = vals < threshold_s
        if below.any():
            examples = []
            if "service_id" in grp.columns:
                examples = grp.loc[grp["value_s"] < threshold_s, "service_id"].astype(str).head(5).tolist()
            suffix = f"; examples service_id={examples}" if examples else ""
            print(f"[low-latency][RAW][{conc}][{mc} mecs] "
                  f"{below.sum()}/{vals.size} < {threshold_s:.1f}s; min={vals.min():.3f}s{suffix}")

def log_high_latencies(tidy: pd.DataFrame, raw: pd.DataFrame, threshold_s: float = HIGH_LATENCY_TH_S):
    print(f"[info] checking plotted values > {threshold_s:.1f}s ...")
    for (conc, mc), grp in tidy.groupby(["consensus", "mec_count"]):
        arr = grp["value_s"].to_numpy()
        if arr.size == 0:
            continue
        above = arr > threshold_s
        if above.any():
            print(f"[high-latency][PLOTTED][{conc}][{mc} mecs] "
                  f"{above.sum()}/{arr.size} > {threshold_s:.1f}s; max={arr.max():.3f}s")

    print(f"[info] checking RAW per-service values > {threshold_s:.1f}s ...")
    raw2 = raw.copy()
    raw2["value_s"] = raw2[VALUE_COL] / 1000.0
    for (conc, mc), grp in raw2.groupby(["consensus", "mec_count"]):
        vals = grp["value_s"].dropna().to_numpy()
        if vals.size == 0:
            continue
        above = vals > threshold_s
        if above.any():
            examples = []
            if "service_id" in grp.columns:
                examples = grp.loc[grp["value_s"] > threshold_s, "service_id"].astype(str).head(5).tolist()
            suffix = f"; examples service_id={examples}" if examples else ""
            print(f"[high-latency][RAW][{conc}][{mc} mecs] "
                  f"{above.sum()}/{vals.size} > {threshold_s:.1f}s; max={vals.max():.3f}s{suffix}")

def main():
    args = parse_args()
    if not IN_CSV.exists():
        raise SystemExit(f"[error] not found: {IN_CSV}")

    raw_df = load_data(IN_CSV)
    tidy = prep_series(raw_df, args.agg)

    # Logs for low/high latency checks
    log_low_latencies(tidy, raw_df, threshold_s=LOW_LATENCY_TH_S)
    log_high_latencies(tidy, raw_df, threshold_s=HIGH_LATENCY_TH_S)

    # Global x-axis range shared across both panels
    all_vals = tidy["value_s"].to_numpy()
    if all_vals.size == 0:
        raise SystemExit("[error] no data to plot")
    x_lo, x_hi = compute_xlim(all_vals, qhi=args.qhi, xlo_mode=args.xlo)

    # seaborn/mpl style
    sns.set_theme(context="paper", style="ticks")
    sns.set_context("paper", font_scale=1.5)

    # Narrow panels + small gap; share axes
    fig, axes = plt.subplots(
        1, 2, figsize=(9.5, 4.6),
        gridspec_kw={"wspace": 0.05},
        sharey=True, sharex=True
    )

    color_map = {m: c for m, c in zip(KEEP_COUNTS, PALETTE)}

    for ax, conc in zip(axes, CONSENSUS_ORDER):
        sub = tidy[tidy["consensus"] == conc]
        handles, labels = [], []

        for mec in KEEP_COUNTS:
            vals = sub.loc[sub["mec_count"] == mec, "value_s"].to_numpy()
            if vals.size == 0:
                continue
            xs, ys = smooth_ecdf_line(vals, npts=1000)
            h, = ax.plot(xs, ys, linewidth=2.2, color=color_map[mec])
            handles.append(h)
            labels.append(f"{MEC_LABEL[mec]}")

        ax.set_title(CONSENSUS_LABEL.get(conc, conc.capitalize()))
        ax.set_xlabel("Latency (s)")
        stylize_axes(ax)
        ax.set_xlim(x_lo, x_hi)

        leg = ax.legend(handles, labels, title=None, frameon=True, loc="lower right", fancybox=False)
        leg.get_frame().set_edgecolor("black"); leg.get_frame().set_linewidth(1.1)

    # remove y-axis title on the right panel only
    axes[1].set_ylabel("")

    # Preview + export
    plt.show(block=False)
    fig.savefig(OUT_PDF, dpi=300, bbox_inches="tight")
    print(f"Wrote {OUT_PDF}")
    if args.no_show:
        plt.close(fig)
    else:
        plt.show()

if __name__ == "__main__":
    main()
