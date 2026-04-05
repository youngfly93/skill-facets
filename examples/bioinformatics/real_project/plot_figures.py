#!/usr/bin/env python3
"""
Generate 3 SCI publication-quality figures:
  1. PCA plot (Tumor vs Normal)
  2. Volcano plot (Top 10 genes labeled)
  3. GO enrichment bubble plot

Style: white background, no gridlines, comfortable color palette.
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from adjustText import adjust_text

# ── Paths ────────────────────────────────────────────────────────────
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(BASE, "results")
FIGURES = os.path.join(BASE, "figures")
os.makedirs(FIGURES, exist_ok=True)

# ── Global style ─────────────────────────────────────────────────────
plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.grid": False,
    "axes.edgecolor": "#333333",
    "axes.linewidth": 0.8,
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 11,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "xtick.major.width": 0.8,
    "ytick.major.width": 0.8,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.15,
})

# Color palette
COLOR_TUMOR  = "#E64B35"   # warm red
COLOR_NORMAL = "#4DBBD5"   # teal blue
COLOR_UP     = "#E64B35"
COLOR_DOWN   = "#3C5488"   # steel blue
COLOR_NS     = "#CCCCCC"   # grey for non-significant


# =====================================================================
# 1. PCA PLOT
# =====================================================================
def plot_pca():
    df = pd.read_csv(os.path.join(RESULTS, "PCA_data.csv"))

    fig, ax = plt.subplots(figsize=(5.5, 4.5))

    for grp, color, marker in [("Tumor", COLOR_TUMOR, "o"),
                                ("Normal", COLOR_NORMAL, "s")]:
        sub = df[df["group"] == grp]
        ax.scatter(sub["PC1"], sub["PC2"],
                   c=color, marker=marker, s=80, edgecolors="white",
                   linewidths=0.6, zorder=3, label=grp)

    ax.set_xlabel("PC1", fontsize=12, fontweight="bold")
    ax.set_ylabel("PC2", fontsize=12, fontweight="bold")
    ax.legend(frameon=False, fontsize=10, loc="best")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    out = os.path.join(FIGURES, "pca_plot.png")
    fig.savefig(out)
    plt.close(fig)
    print(f"[OK] {out}")


# =====================================================================
# 2. VOLCANO PLOT
# =====================================================================
def plot_volcano():
    df = pd.read_csv(os.path.join(RESULTS, "DEG_results.csv"))
    df["-log10padj"] = -np.log10(df["padj"].clip(lower=1e-300))

    lfc_thr = 1.0
    padj_thr = 0.05

    conditions = [
        (df["log2FoldChange"] >=  lfc_thr) & (df["padj"] < padj_thr),
        (df["log2FoldChange"] <= -lfc_thr) & (df["padj"] < padj_thr),
    ]
    choices = ["Up", "Down"]
    df["regulation"] = np.select(conditions, choices, default="NS")

    fig, ax = plt.subplots(figsize=(6, 5))

    # Non-significant first (behind)
    ns = df[df["regulation"] == "NS"]
    ax.scatter(ns["log2FoldChange"], ns["-log10padj"],
               c=COLOR_NS, s=12, alpha=0.5, linewidths=0, zorder=1)

    # Up & Down
    up = df[df["regulation"] == "Up"]
    dn = df[df["regulation"] == "Down"]
    ax.scatter(up["log2FoldChange"], up["-log10padj"],
               c=COLOR_UP, s=18, alpha=0.8, linewidths=0, zorder=2)
    ax.scatter(dn["log2FoldChange"], dn["-log10padj"],
               c=COLOR_DOWN, s=18, alpha=0.8, linewidths=0, zorder=2)

    # Threshold lines
    ax.axhline(-np.log10(padj_thr), ls="--", lw=0.7, color="#888888", zorder=0)
    ax.axvline( lfc_thr, ls="--", lw=0.7, color="#888888", zorder=0)
    ax.axvline(-lfc_thr, ls="--", lw=0.7, color="#888888", zorder=0)

    # Label top 10 genes by significance among DEGs
    sig = df[df["regulation"] != "NS"].nsmallest(10, "padj")
    texts = []
    for _, row in sig.iterrows():
        texts.append(
            ax.text(row["log2FoldChange"], row["-log10padj"],
                    row["symbol"], fontsize=8, fontstyle="italic",
                    ha="center", va="bottom")
        )
    adjust_text(texts, ax=ax, arrowprops=dict(arrowstyle="-", color="#555555",
                                               lw=0.5))

    # Counts for legend
    n_up = len(up)
    n_dn = len(dn)
    n_ns = len(ns)
    legend_elements = [
        Patch(facecolor=COLOR_UP,   edgecolor="none", label=f"Up ({n_up})"),
        Patch(facecolor=COLOR_DOWN, edgecolor="none", label=f"Down ({n_dn})"),
        Patch(facecolor=COLOR_NS,   edgecolor="none", label=f"NS ({n_ns})"),
    ]
    ax.legend(handles=legend_elements, frameon=False, fontsize=9, loc="upper right")

    ax.set_xlabel("log$_2$(Fold Change)", fontsize=12, fontweight="bold")
    ax.set_ylabel("$-$log$_{10}$(adjusted p-value)", fontsize=12, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    out = os.path.join(FIGURES, "volcano_plot.png")
    fig.savefig(out)
    plt.close(fig)
    print(f"[OK] {out}")


# =====================================================================
# 3. GO ENRICHMENT BUBBLE PLOT
# =====================================================================
def plot_go():
    df = pd.read_csv(os.path.join(RESULTS, "GO_enrichment.csv"))
    df["-log10FDR"] = -np.log10(df["FDR"].clip(lower=1e-300))

    # Parse GeneRatio to a float
    df["GeneRatioVal"] = df["GeneRatio"].apply(
        lambda x: int(x.split("/")[0]) / int(x.split("/")[1])
    )

    # Category colors
    cat_colors = {"BP": "#E64B35", "CC": "#4DBBD5", "MF": "#00A087"}

    fig, ax = plt.subplots(figsize=(7, 4.5))

    for cat in ["BP", "CC", "MF"]:
        sub = df[df["Category"] == cat]
        ax.scatter(sub["GeneRatioVal"], sub["Term"],
                   s=sub["Count"] * 8, c=cat_colors[cat],
                   edgecolors="white", linewidths=0.5,
                   alpha=0.85, zorder=3, label=cat)

    ax.set_xlabel("Gene Ratio", fontsize=12, fontweight="bold")
    ax.set_ylabel("")

    # Size legend
    sizes_shown = [30, 60, 90, 120]
    size_handles = [
        ax.scatter([], [], s=s * 8, c="#999999", edgecolors="white",
                   linewidths=0.5, label=str(s))
        for s in sizes_shown
    ]

    # Category legend
    cat_handles = [
        Patch(facecolor=cat_colors[c], edgecolor="none", label=c)
        for c in ["BP", "CC", "MF"]
    ]

    leg1 = ax.legend(handles=cat_handles, title="Category",
                     frameon=False, fontsize=9, loc="lower right",
                     title_fontsize=10)
    ax.add_artist(leg1)
    ax.legend(handles=size_handles, title="Count",
              frameon=False, fontsize=9, loc="center right",
              title_fontsize=10, labelspacing=1.2)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    out = os.path.join(FIGURES, "go_enrichment.png")
    fig.savefig(out)
    plt.close(fig)
    print(f"[OK] {out}")


# ── Main ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    plot_pca()
    plot_volcano()
    plot_go()
    print("\nAll figures saved to:", FIGURES)
