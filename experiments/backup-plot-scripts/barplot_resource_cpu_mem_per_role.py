#!/usr/bin/env python3
# barplot_resource_cpu_mem_per_role.py
# 4 panels: Clique/QBFT × CPU/Memory, bars = Consumer vs Provider, with mean ± std.

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path

CSV_PATH = Path("multiple-offers/_summary/resource_usage_overall_per_role.csv")

KEEP_COUNTS     = [4, 10, 20, 30]
CONSENSUS_ORDER = ["clique", "qbft"]
ROLE_ORDER      = ["consumer", "provider"]
ROLE_LABEL      = {"consumer": "Consumer", "provider": "Provider"}
CONS_LABEL      = {"clique": "Clique", "qbft": "QBFT"}
ROLE_PALETTE    = {"consumer": "#1f77b4", "provider": "#ff7f0e"}

AGG_PREFERENCE  = ["per_node_median", "per_run"]  # prefer low-noise

def pick_first(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"None of the columns found: {candidates}")

def choose_aggregation(df):
    if "aggregation" not in df.columns:
        return df, None
    for a in AGG_PREFERENCE:
        if (df["aggregation"] == a).any():
            return df[df["aggregation"] == a].copy(), a
    return df, None

def stylize(ax):
    # ax.grid(axis="y", linestyle="--", color="grey", alpha=0.45)
    ax.grid(True, which="both", axis="both", linestyle="--", color="grey", alpha=0.5)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_color("black")
        ax.spines[side].set_linewidth(1.1)
    ax.set_ylim(0, None)

def add_errbars(ax, df_plot, std_col):
    # Bars are drawn for x in KEEP_COUNTS and hue in ROLE_ORDER (in that order).
    yerrs = []
    for mc in KEEP_COUNTS:
        for role in ROLE_ORDER:
            sel = df_plot[(df_plot["mec_count"] == mc) & (df_plot["role"] == role)]
            if sel.empty or std_col not in sel:
                yerrs.append(0.0)
            else:
                val = float(sel[std_col].iloc[0])
                yerrs.append(0.0 if pd.isna(val) else val)

    for patch, yerr in zip(ax.patches, yerrs):
        x_center = patch.get_x() + patch.get_width() / 2.0
        ax.errorbar(x_center, patch.get_height(), yerr=yerr,
                    fmt="none", ecolor="black", elinewidth=1.2, capsize=3)

def plot_panel(ax, df_sub, mean_col, std_col, y_label, title):
    d = df_sub[df_sub["mec_count"].isin(KEEP_COUNTS)].copy().sort_values(["mec_count","role"])
    sns.barplot(
        data=d,
        x="mec_count",
        y=mean_col,
        hue="role",
        order=KEEP_COUNTS,
        hue_order=ROLE_ORDER,
        palette=[ROLE_PALETTE[r] for r in ROLE_ORDER],
        errorbar=None,
        ax=ax,
    )
    add_errbars(ax, d, std_col)
    ax.set_xlabel("Number of validator nodes (MECs)")
    ax.set_ylabel(y_label)
    ax.set_title(title, fontsize=14)
    stylize(ax)
    handles, labels = ax.get_legend_handles_labels()
    labels = [ROLE_LABEL.get(lbl, lbl) for lbl in labels]
    leg = ax.legend(handles, labels, title=None, frameon=True, loc="upper left", fancybox=False)
    leg.get_frame().set_edgecolor("black"); leg.get_frame().set_linewidth(1.1)

def main():
    df = pd.read_csv(CSV_PATH)

    # Normalize any trailing-underscore groupers
    df = df.rename(columns={
        "consensus_": "consensus",
        "mec_count_": "mec_count",
        "role_": "role",
    })
    if "role" not in df.columns:
        raise RuntimeError(
            "Column 'role' not found in CSV. Ensure your summarizer keeps 'role' "
            "in resource_usage_overall_per_role.csv."
        )

    # Prefer low-noise aggregation (median across runs per node, then across nodes)
    df, agg_used = choose_aggregation(df)

    # Filter and order
    df = df[df["mec_count"].isin(KEEP_COUNTS)].copy()
    df["mec_count"] = df["mec_count"].astype(int)
    df["consensus"] = pd.Categorical(df["consensus"], categories=CONSENSUS_ORDER, ordered=True)
    df["role"]      = pd.Categorical(df["role"],      categories=ROLE_ORDER,      ordered=True)

    # Metric columns (support both new and legacy names)
    cpu_mean_col = pick_first(df, ["cpu_percent_mean", "cpu_percent_mean_mean"])
    cpu_std_col  = pick_first(df, ["cpu_percent_std",  "cpu_percent_std_mean"])
    mem_mean_col = pick_first(df, ["mem_mb_mean",      "mem_mb_mean_mean"])
    mem_std_col  = pick_first(df, ["mem_mb_std",       "mem_mb_std_mean"])

    # Derived for plotting
    df["cpu_mean_vcpu"] = df[cpu_mean_col] / 100.0
    df["cpu_std_vcpu"]  = df[cpu_std_col]  / 100.0
    df["mem_mean_mb"]   = df[mem_mean_col]
    df["mem_std_mb"]    = df[mem_std_col]

    sns.set_theme(context="paper", style="ticks")
    sns.set_context("paper", font_scale=1.35)

    fig, axes = plt.subplots(
        2, 2, figsize=(13.2, 9.6),
        gridspec_kw={"wspace": 0.30, "hspace": 0.36},
        sharex=True
    )

    # [0,0] Clique – CPU
    plot_panel(
        axes[0, 0],
        df[df["consensus"] == "clique"],
        mean_col="cpu_mean_vcpu",
        std_col="cpu_std_vcpu",
        y_label="CPU usage (vCPUs)",
        title=f"{CONS_LABEL['clique']}",
    )

    # [1,0] Clique – Memory
    plot_panel(
        axes[1, 0],
        df[df["consensus"] == "clique"],
        mean_col="mem_mean_mb",
        std_col="mem_std_mb",
        y_label="Memory usage (MB)",
        title=f"{CONS_LABEL['clique']}",
    )

    # [0,1] QBFT – CPU
    plot_panel(
        axes[0, 1],
        df[df["consensus"] == "qbft"],
        mean_col="cpu_mean_vcpu",
        std_col="cpu_std_vcpu",
        y_label="CPU usage (vCPUs)",
        title=f"{CONS_LABEL['qbft']}",
    )

    # [1,1] QBFT – Memory
    plot_panel(
        axes[1, 1],
        df[df["consensus"] == "qbft"],
        mean_col="mem_mean_mb",
        std_col="mem_std_mb",
        y_label="Memory usage (MB)",
        title=f"{CONS_LABEL['qbft']}",
    )

    for ax in axes[0, :]:
        ax.tick_params(axis="x", labelbottom=True)

    plt.show()
    out = Path("plots"); out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "resource_usage_cpu_mem_per_role.pdf", dpi=300, bbox_inches="tight")

if __name__ == "__main__":
    main()
