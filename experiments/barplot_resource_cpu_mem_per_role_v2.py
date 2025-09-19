#!/usr/bin/env python3
# barplot_resource_cpu_mem_per_role_v2.py
# 4 panels (aligned axes per row, tighter spacing):
#   TL: Consumer (CPU)
#   TR: Provider (CPU)
#   BL: Consumer (Memory)
#   BR: Provider (Memory)

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np

CSV_PATH = Path("multiple-offers/_summary/resource_usage_overall_per_role.csv")

KEEP_COUNTS     = [4, 10, 20, 30]
KEEP_STR        = [str(x) for x in KEEP_COUNTS]
CONSENSUS_ORDER = ["clique", "qbft"]
CONSENSUS_LABEL = {"clique": "Clique", "qbft": "QBFT"}
ROLE_ORDER      = ["consumer", "provider"]
ROLE_LABEL      = {"consumer": "Consumer", "provider": "Provider"}
PALETTE_MAP     = {"clique": "#1f77b4", "qbft": "#ff7f0e"}  # fixed colors
AGG_PREFERENCE  = ["per_node_median", "per_run"]            # prefer low-noise
HEADROOM        = 1.10  # 10% headroom above max(mean+std)

def pick_series(df: pd.DataFrame, candidates):
    for name in candidates:
        if name in df.columns:
            return df.loc[:, [name]].iloc[:, 0]
    raise KeyError(f"None of the candidate columns found: {candidates}")

def choose_aggregation(df: pd.DataFrame):
    if "aggregation" not in df.columns:
        return df
    for a in AGG_PREFERENCE:
        if (df["aggregation"] == a).any():
            return df[df["aggregation"] == a].copy()
    return df

def load_and_prepare(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    # Normalize id columns only
    df = df.rename(columns={
        "consensus_": "consensus",
        "mec_count_": "mec_count",
        "role_": "role",
    })
    if "role" not in df.columns:
        raise RuntimeError("Column 'role' not found in CSV.")

    # Prefer low-noise aggregation
    df = choose_aggregation(df)

    # Filter + order
    df = df[df["mec_count"].isin(KEEP_COUNTS)].copy()
    df["mec_count"] = df["mec_count"].astype(int)
    df["consensus"] = pd.Categorical(df["consensus"], categories=CONSENSUS_ORDER, ordered=True)
    df["role"]      = pd.Categorical(df["role"],      categories=ROLE_ORDER,      ordered=True)

    # Robust metric columns (support new & legacy names)
    cpu_mean_pct = pick_series(df, ["cpu_percent_mean", "cpu_percent_mean_mean"])
    cpu_std_pct  = pick_series(df, ["cpu_percent_std",  "cpu_percent_std_mean"])
    mem_mean_mb  = pick_series(df, ["mem_mb_mean",      "mem_mb_mean_mean"])
    mem_std_mb   = pick_series(df, ["mem_mb_std",       "mem_mb_std_mean"])

    # Derived for plotting
    df["cpu_mean_vcpu"] = pd.to_numeric(cpu_mean_pct, errors="coerce") / 100.0
    df["cpu_std_vcpu"]  = pd.to_numeric(cpu_std_pct,  errors="coerce") / 100.0
    df["mem_mean_mb"]   = pd.to_numeric(mem_mean_mb,  errors="coerce")
    df["mem_std_mb"]    = pd.to_numeric(mem_std_mb,   errors="coerce")

    df["mec_count_cat"] = pd.Categorical(
        df["mec_count"].astype(str), categories=KEEP_STR, ordered=True
    )
    return df

def stylize_axes(ax, ymax=None):
    ax.grid(True, which="both", axis="both", linestyle="--", color="grey", alpha=0.5)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_color("black")
        ax.spines[side].set_linewidth(1.1)
    if ymax is None:
        ax.set_ylim(0, None)
    else:
        ax.set_ylim(0, ymax)

# --- FIXED: position-aware error bars (do not rely on ax.patches order) ---
def add_errbars(ax, data_for_panel: pd.DataFrame, mean_col: str, std_col: str):
    """
    Draw symmetric ±std error bars using explicit bar positions
    (aligned to mec_count × consensus). Works even if seaborn drops NaN bars.
    """
    H = len(CONSENSUS_ORDER)   # number of hues
    group_width = 0.8
    bar_width   = group_width / H

    # Category tick positions (one per mec group)
    xticks = ax.get_xticks()
    if len(xticks) != len(KEEP_STR):
        xticks = np.arange(len(KEEP_STR))

    for gi, mc in enumerate(KEEP_STR):
        x_center = xticks[gi]
        x0 = x_center - group_width/2 + bar_width/2
        for hj, cons in enumerate(CONSENSUS_ORDER):
            sel = data_for_panel[
                (data_for_panel["mec_count_cat"] == mc) & (data_for_panel["consensus"] == cons)
            ]
            if sel.empty:
                continue

            mean_y = float(sel[mean_col].iloc[0]) if mean_col in sel.columns else np.nan
            std_y  = float(sel[std_col].iloc[0])  if std_col  in sel.columns else 0.0

            if not np.isfinite(mean_y) or not np.isfinite(std_y) or std_y == 0.0:
                continue

            x = x0 + hj * bar_width
            ax.errorbar(
                x, mean_y,
                yerr=std_y,
                fmt="none",
                ecolor="black",
                elinewidth=1.2,
                capsize=3,
                zorder=3,
            )

def plot_panel(ax, df_role, y_col, std_col, title=None, ylabel=None, xlabel=None, ymax=None, show_legend=True):
    d = df_role.sort_values(["mec_count", "consensus"]).copy()

    sns.barplot(
        data=d,
        x="mec_count_cat",
        y=y_col,
        hue="consensus",
        hue_order=CONSENSUS_ORDER,
        palette=[PALETTE_MAP[c] for c in CONSENSUS_ORDER],
        errorbar=None,
        ax=ax,
    )

    # position-aware error bars
    add_errbars(ax, d, y_col, std_col)

    # Titles/labels
    ax.set_title("" if title is None else title, fontsize=14)
    ax.set_ylabel("" if ylabel is None else ylabel)
    ax.set_xlabel("" if xlabel is None else xlabel)

    stylize_axes(ax, ymax=ymax)

    if show_legend:
        handles, labels = ax.get_legend_handles_labels()
        labels = [CONSENSUS_LABEL.get(l, l) for l in labels]
        leg = ax.legend(handles, labels, title=None, frameon=True, loc="upper left", fancybox=True)
        leg.get_frame().set_edgecolor("black")
        leg.get_frame().set_linewidth(1.1)
    else:
        if ax.get_legend():
            ax.get_legend().remove()

def log_panel_stats(df, role_name: str):
    """Log mean ± std for CPU (vCPU) and Memory (MB) per mec × consensus for a role."""
    print(f"[log] {ROLE_LABEL.get(role_name, role_name)} STATS")
    sub = df[df["role"] == role_name]
    # CPU
    for mc in KEEP_STR:
        for cons in CONSENSUS_ORDER:
            row = sub[(sub["mec_count_cat"] == mc) & (sub["consensus"] == cons)]
            if not row.empty:
                cpu_mean = float(row["cpu_mean_vcpu"].iloc[0])
                cpu_std  = float(row["cpu_std_vcpu"].iloc[0])
                print(f"  CPU  | MEC={mc:>2} | {cons.upper():<5}  mean={cpu_mean:6.3f} vCPU  std={cpu_std:6.3f} vCPU")
    # MEM
    for mc in KEEP_STR:
        for cons in CONSENSUS_ORDER:
            row = sub[(sub["mec_count_cat"] == mc) & (sub["consensus"] == cons)]
            if not row.empty:
                mem_mean = float(row["mem_mean_mb"].iloc[0])
                mem_std  = float(row["mem_std_mb"].iloc[0])
                print(f"  MEM  | MEC={mc:>2} | {cons.UPPER():<5}  mean={mem_mean:7.1f} MB    std={mem_std:7.1f} MB")  # UPPER? -> fixed below

def log_panel_stats(df, role_name: str):
    """Log mean ± std for CPU (vCPU) and Memory (MB) per mec × consensus for a role."""
    print(f"[log] {ROLE_LABEL.get(role_name, role_name)} STATS")
    sub = df[df["role"] == role_name]
    # CPU
    for mc in KEEP_STR:
        for cons in CONSENSUS_ORDER:
            row = sub[(sub["mec_count_cat"] == mc) & (sub["consensus"] == cons)]
            if not row.empty:
                cpu_mean = float(row["cpu_mean_vcpu"].iloc[0])
                cpu_std  = float(row["cpu_std_vcpu"].iloc[0])
                print(f"  CPU  | MEC={mc:>2} | {cons.upper():<5}  mean={cpu_mean:6.3f} vCPU  std={cpu_std:6.3f} vCPU")
    # MEM
    for mc in KEEP_STR:
        for cons in CONSENSUS_ORDER:
            row = sub[(sub["mec_count_cat"] == mc) & (sub["consensus"] == cons)]
            if not row.empty:
                mem_mean = float(row["mem_mean_mb"].iloc[0])
                mem_std  = float(row["mem_std_mb"].iloc[0])
                print(f"  MEM  | MEC={mc:>2} | {cons.upper():<5}  mean={mem_mean:7.1f} MB    std={mem_std:7.1f} MB")
    print()

def main():
    df = load_and_prepare(CSV_PATH)

    # Logs (so you can quickly verify numbers plotted)
    log_panel_stats(df, "consumer")
    log_panel_stats(df, "provider")

    sns.set_theme(context="paper", style="ticks")
    sns.set_context("paper", font_scale=1.35)

    # unified y-limits per row (mean + std + headroom)
    cpu_max = np.nanmax((df["cpu_mean_vcpu"] + df["cpu_std_vcpu"]).values)
    mem_max = np.nanmax((df["mem_mean_mb"]   + df["mem_std_mb"]).values)
    cpu_ylim = float(cpu_max * HEADROOM) if np.isfinite(cpu_max) else None
    mem_ylim = float(mem_max * HEADROOM) if np.isfinite(mem_max) else None

    fig, axes = plt.subplots(
        2, 2, figsize=(12.2, 8.8),
        sharey="row", sharex="col",
        gridspec_kw={"wspace": 0.1, "hspace": 0.15}
    )

    # --- TOP ROW (CPU) ---
    # TL: Consumer – CPU
    plot_panel(
        axes[0, 0],
        df[(df["role"] == "consumer")],
        y_col="cpu_mean_vcpu",
        std_col="cpu_std_vcpu",
        title="Consumer",
        ylabel="CPU usage (vCPUs)",
        xlabel=None,            # remove x-axis label on top
        ymax=cpu_ylim,
        show_legend=True,
    )

    # TR: Provider – CPU
    plot_panel(
        axes[0, 1],
        df[(df["role"] == "provider")],
        y_col="cpu_mean_vcpu",
        std_col="cpu_std_vcpu",
        title="Provider",
        ylabel="",
        xlabel=None,            # remove x-axis label on top
        ymax=cpu_ylim,
        show_legend=True,
    )

    # --- BOTTOM ROW (MEMORY) ---
    # BL: Consumer – Memory
    plot_panel(
        axes[1, 0],
        df[(df["role"] == "consumer")],
        y_col="mem_mean_mb",
        std_col="mem_std_mb",
        title="",
        ylabel="Memory usage (MB)",
        xlabel="Number of MECs",
        ymax=mem_ylim,
        show_legend=True,
    )

    # BR: Provider – Memory
    plot_panel(
        axes[1, 1],
        df[(df["role"] == "provider")],
        y_col="mem_mean_mb",
        std_col="mem_std_mb",
        title="",
        ylabel="",
        xlabel="Number of MECs",
        ymax=mem_ylim,
        show_legend=True,
    )

    out = Path("plots"); out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "resource_usage_cpu_mem_per_role_v2.pdf", dpi=300, bbox_inches="tight")
    plt.show()

if __name__ == "__main__":
    main()
