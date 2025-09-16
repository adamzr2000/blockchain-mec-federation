#!/usr/bin/env python3
# barplot_resource_cpu_mem_per_role_v2.py
# 4 panels:
#   TL: Consumer – CPU
#   BL: Provider – CPU
#   TR: Consumer – Memory
#   BR: Provider – Memory

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path

CSV_PATH = Path("multiple-offers/_summary/resource_usage_overall_per_role.csv")

KEEP_COUNTS     = [10, 20, 30]
KEEP_STR        = [str(x) for x in KEEP_COUNTS]
CONSENSUS_ORDER = ["clique", "qbft"]
CONSENSUS_LABEL = {"clique": "Clique", "qbft": "QBFT"}
ROLE_ORDER      = ["consumer", "provider"]
ROLE_LABEL      = {"consumer": "Consumer", "provider": "Provider"}
PALETTE_MAP     = {"clique": "#1f77b4", "qbft": "#ff7f0e"}  # fixed colors
AGG_PREFERENCE  = ["per_node_median", "per_run"]           # prefer low-noise

def pick_series(df: pd.DataFrame, candidates):
    """Return the first matching column as a Series (first occurrence if duplicated)."""
    for name in candidates:
        if name in df.columns:
            return df.loc[:, [name]].iloc[:, 0]
    raise KeyError(f"None of the candidate columns found: {candidates}")

def choose_aggregation(df: pd.DataFrame):
    """Prefer per_node_median if an 'aggregation' column exists."""
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
        raise RuntimeError(
            "Column 'role' not found in CSV. Ensure your summarizer keeps 'role' "
            "in resource_usage_overall_per_role.csv."
        )

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

    # Derived metrics for plotting
    df["cpu_mean_vcpu"] = cpu_mean_pct / 100.0
    df["cpu_std_vcpu"]  = cpu_std_pct  / 100.0
    df["mem_mean_mb"]   = mem_mean_mb
    df["mem_std_mb"]    = mem_std_mb

    # String-categorical x keeps bars centered and ordered
    df["mec_count_cat"] = pd.Categorical(df["mec_count"].astype(str),
                                         categories=KEEP_STR, ordered=True)
    return df

def stylize_axes(ax):
    ax.grid(axis="y", linestyle="--", color="grey", alpha=0.5)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_color("black")
        ax.spines[side].set_linewidth(1.1)
    ax.set_ylim(0, None)

def add_errbars(ax, data_for_panel: pd.DataFrame, std_col: str):
    """
    Add error bars matching seaborn's bar order: for each mec_count in KEEP_COUNTS
    and each hue in CONSENSUS_ORDER, only if that combo exists.
    """
    yerrs = []
    for mc in KEEP_STR:
        for cons in CONSENSUS_ORDER:
            sel = data_for_panel[
                (data_for_panel["mec_count_cat"] == mc) & (data_for_panel["consensus"] == cons)
            ]
            if not sel.empty:
                val = float(sel.iloc[0][std_col]) if std_col in sel.columns else 0.0
                yerrs.append(0.0 if pd.isna(val) else val)

    # bars are drawn in the same (mc, cons) order; attach yerr to each bar
    for patch, yerr in zip(ax.patches, yerrs):
        x_center = patch.get_x() + patch.get_width() / 2.0
        ax.errorbar(x_center, patch.get_height(), yerr=yerr,
                    fmt="none", ecolor="black", elinewidth=1.2, capsize=3)

def plot_panel(ax, df_role, y_col, std_col, title):
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
    add_errbars(ax, d, std_col)
    ax.set_title(title, fontsize=14)
    ax.set_xlabel("Number of validator nodes (MECs)")
    ax.set_ylabel("CPU usage (vCPUs)" if y_col == "cpu_mean_vcpu" else "Memory usage (MB)")
    stylize_axes(ax)

    # Legend inside, no title
    handles, labels = ax.get_legend_handles_labels()
    labels = [CONSENSUS_LABEL.get(l, l) for l in labels]
    leg = ax.legend(handles, labels, title=None, frameon=True, loc="upper left", fancybox=False)
    leg.get_frame().set_edgecolor("black")
    leg.get_frame().set_linewidth(1.1)

def main():
    df = load_and_prepare(CSV_PATH)

    sns.set_theme(context="paper", style="whitegrid")
    sns.set_context("paper", font_scale=1.35)

    fig, axes = plt.subplots(
        2, 2, figsize=(12.8, 9.2),
        gridspec_kw={"wspace": 0.30, "hspace": 0.36}
    )

    # TL
    plot_panel(
        axes[0, 0],
        df[df["role"] == "consumer"],
        y_col="cpu_mean_vcpu",
        std_col="cpu_std_vcpu",
        title=f"{ROLE_LABEL['consumer']} – CPU",
    )

    # TR
    plot_panel(
        axes[0, 1],
        df[df["role"] == "provider"],
        y_col="cpu_mean_vcpu",
        std_col="cpu_std_vcpu",
        title=f"{ROLE_LABEL['provider']} – CPU",
    )

    # BL
    plot_panel(
        axes[1, 0],
        df[df["role"] == "consumer"],
        y_col="mem_mean_mb",
        std_col="mem_std_mb",
        title=f"{ROLE_LABEL['consumer']} – Memory",
    )

    # BR
    plot_panel(
        axes[1, 1],
        df[df["role"] == "provider"],
        y_col="mem_mean_mb",
        std_col="mem_std_mb",
        title=f"{ROLE_LABEL['provider']} – Memory",
    )

    plt.show()
    out = Path("plots"); out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "resource_usage_cpu_mem_per_role_v2.pdf", dpi=300, bbox_inches="tight")

if __name__ == "__main__":
    main()
