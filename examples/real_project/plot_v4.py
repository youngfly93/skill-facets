#!/usr/bin/env python3
"""
Generate three SCI publication-quality figures (v4):
  1. PCA plot (Tumor vs Normal)
  2. Volcano plot (Top 10 genes annotated)
  3. GO enrichment bubble plot

Constraints:
  - Pure white background (#FFFFFF)
  - No gridlines
  - >= 300 DPI
  - Axes labeled with units
  - Color-blind friendly palette
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
import matplotlib.transforms as transforms
from adjustText import adjust_text

# ---------- paths ----------
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(BASE, "results")
FIGURES = os.path.join(BASE, "figures")
os.makedirs(FIGURES, exist_ok=True)

# ---------- global rc ----------
plt.rcParams.update({
    "figure.facecolor": "#FFFFFF",
    "axes.facecolor": "#FFFFFF",
    "savefig.facecolor": "#FFFFFF",
    "savefig.dpi": 300,
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 10,
    "axes.linewidth": 0.8,
    "axes.grid": False,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "xtick.major.width": 0.8,
    "ytick.major.width": 0.8,
    "pdf.fonttype": 42,   # editable text in PDF
    "ps.fonttype": 42,
})

# Color-blind friendly palette (Okabe-Ito derived)
COLOR_TUMOR = "#D55E00"   # vermillion
COLOR_NORMAL = "#0072B2"  # blue
COLOR_UP = "#D55E00"      # vermillion
COLOR_DOWN = "#0072B2"    # blue
COLOR_NS = "#999999"      # grey


# =====================================================================
# 1. PCA PLOT
# =====================================================================
def plot_pca():
    df = pd.read_csv(os.path.join(RESULTS, "PCA_data.csv"))

    fig, ax = plt.subplots(figsize=(5, 4))

    groups = {"Tumor": COLOR_TUMOR, "Normal": COLOR_NORMAL}
    markers = {"Tumor": "o", "Normal": "s"}

    for grp, color in groups.items():
        sub = df[df["group"] == grp]
        ax.scatter(
            sub["PC1"], sub["PC2"],
            c=color, marker=markers[grp],
            s=70, edgecolors="white", linewidths=0.6,
            label=grp, zorder=3,
        )
        # draw 95% confidence ellipse
        _draw_confidence_ellipse(sub["PC1"], sub["PC2"], ax, color, alpha=0.12)

    ax.set_xlabel("PC1", fontsize=12, fontweight="bold")
    ax.set_ylabel("PC2", fontsize=12, fontweight="bold")
    ax.set_title("Principal Component Analysis", fontsize=13, fontweight="bold", pad=10)
    ax.legend(frameon=True, edgecolor="black", fancybox=False,
              fontsize=10, loc="best", framealpha=1.0)
    ax.axhline(0, color="#cccccc", linewidth=0.5, linestyle="--", zorder=1)
    ax.axvline(0, color="#cccccc", linewidth=0.5, linestyle="--", zorder=1)

    _despine(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGURES, "pca_plot_v4.png"), dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("[OK] pca_plot_v4.png")


def _draw_confidence_ellipse(x, y, ax, color, n_std=1.96, alpha=0.15):
    """Draw a 95% confidence ellipse around the data."""
    if len(x) < 3:
        return
    cov = np.cov(x, y)
    mean_x, mean_y = np.mean(x), np.mean(y)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = eigvals.argsort()[::-1]
    eigvals, eigvecs = eigvals[order], eigvecs[:, order]
    angle = np.degrees(np.arctan2(*eigvecs[:, 0][::-1]))
    width, height = 2 * n_std * np.sqrt(eigvals)
    ell = Ellipse(
        (mean_x, mean_y), width, height, angle=angle,
        facecolor=color, alpha=alpha, edgecolor=color,
        linewidth=1.0, linestyle="-", zorder=2,
    )
    ax.add_patch(ell)


# =====================================================================
# 2. VOLCANO PLOT
# =====================================================================
def plot_volcano():
    df = pd.read_csv(os.path.join(RESULTS, "DEG_results.csv"))
    df["-log10(padj)"] = -np.log10(df["padj"].clip(lower=1e-310))

    lfc_cutoff = 1.0
    padj_cutoff = 0.05

    # classify
    conditions = [
        (df["log2FoldChange"] >= lfc_cutoff) & (df["padj"] < padj_cutoff),
        (df["log2FoldChange"] <= -lfc_cutoff) & (df["padj"] < padj_cutoff),
    ]
    choices = ["Up", "Down"]
    df["regulation"] = np.select(conditions, choices, default="NS")

    fig, ax = plt.subplots(figsize=(6, 5))

    # plot NS first, then colored
    for reg, color, label in [
        ("NS", COLOR_NS, "Not Sig."),
        ("Up", COLOR_UP, f"Up (n={int((df['regulation']=='Up').sum())})"),
        ("Down", COLOR_DOWN, f"Down (n={int((df['regulation']=='Down').sum())})"),
    ]:
        sub = df[df["regulation"] == reg]
        ax.scatter(
            sub["log2FoldChange"], sub["-log10(padj)"],
            c=color, s=15, alpha=0.7, edgecolors="none",
            label=label, zorder=2 if reg == "NS" else 3,
        )

    # threshold lines
    ax.axhline(-np.log10(padj_cutoff), color="#aaaaaa", linewidth=0.7,
               linestyle="--", zorder=1)
    ax.axvline(lfc_cutoff, color="#aaaaaa", linewidth=0.7,
               linestyle="--", zorder=1)
    ax.axvline(-lfc_cutoff, color="#aaaaaa", linewidth=0.7,
               linestyle="--", zorder=1)

    # annotate top 10 by adjusted p-value (among significant)
    sig = df[df["regulation"] != "NS"].copy()
    top10 = sig.nsmallest(10, "padj")
    texts = []
    for _, row in top10.iterrows():
        color_t = COLOR_UP if row["regulation"] == "Up" else COLOR_DOWN
        t = ax.text(
            row["log2FoldChange"], row["-log10(padj)"],
            row["symbol"],
            fontsize=8, fontweight="bold", color=color_t,
            ha="center", va="bottom",
        )
        texts.append(t)
    if texts:
        adjust_text(
            texts, ax=ax,
            arrowprops=dict(arrowstyle="-", color="#666666", linewidth=0.5),
            expand=(1.4, 1.6),
            force_text=(0.8, 1.0),
        )

    ax.set_xlabel("log$_2$(Fold Change)", fontsize=12, fontweight="bold")
    ax.set_ylabel("$-$log$_{10}$(adjusted $p$-value)", fontsize=12, fontweight="bold")
    ax.set_title("Differential Expression Analysis", fontsize=13, fontweight="bold", pad=10)
    ax.legend(frameon=True, edgecolor="black", fancybox=False,
              fontsize=9, loc="best", framealpha=1.0,
              markerscale=1.5)

    # add small margin so edge labels are not clipped
    xlim = ax.get_xlim()
    ax.set_xlim(xlim[0] - 0.5, xlim[1] + 1.0)

    _despine(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGURES, "volcano_plot_v4.png"), dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("[OK] volcano_plot_v4.png")


# =====================================================================
# 3. GO ENRICHMENT BUBBLE PLOT
# =====================================================================
def plot_go_enrichment():
    df = pd.read_csv(os.path.join(RESULTS, "GO_enrichment.csv"))
    df["-log10(FDR)"] = -np.log10(df["FDR"])

    # Parse GeneRatio to numeric
    df["GeneRatioNum"] = df["GeneRatio"].apply(
        lambda x: int(x.split("/")[0]) / int(x.split("/")[1])
    )

    # category colors (color-blind safe)
    cat_colors = {"BP": "#0072B2", "CC": "#009E73", "MF": "#E69F00"}

    fig, ax = plt.subplots(figsize=(6.5, 4))

    # bubble size proportional to Count
    size_scale = 12
    for cat, color in cat_colors.items():
        sub = df[df["Category"] == cat]
        ax.scatter(
            sub["GeneRatioNum"], sub["Term"],
            s=sub["Count"] * size_scale,
            c=color, alpha=0.85,
            edgecolors="white", linewidths=0.5,
            label=cat, zorder=3,
        )

    # add count labels inside bubbles
    for _, row in df.iterrows():
        ax.text(
            row["GeneRatioNum"], row["Term"],
            str(row["Count"]),
            fontsize=7, color="white", fontweight="bold",
            ha="center", va="center", zorder=4,
        )

    ax.set_xlabel("Gene Ratio", fontsize=12, fontweight="bold")
    ax.set_title("GO Enrichment Analysis", fontsize=13, fontweight="bold", pad=10)

    # Create size legend
    for sz_val in [30, 60, 120]:
        ax.scatter([], [], s=sz_val * size_scale, c="grey", alpha=0.5,
                   edgecolors="white", label=f"Count = {sz_val}")

    handles, labels = ax.get_legend_handles_labels()
    # Separate category and size legend entries
    cat_handles = handles[:len(cat_colors)]
    cat_labels = labels[:len(cat_colors)]
    size_handles = handles[len(cat_colors):]
    size_labels = labels[len(cat_colors):]

    leg1 = ax.legend(cat_handles, cat_labels, title="Category",
                     loc="lower right", frameon=True, edgecolor="black",
                     fancybox=False, fontsize=9, title_fontsize=10,
                     framealpha=1.0)
    ax.add_artist(leg1)
    ax.legend(size_handles, size_labels, title="Gene Count",
              loc="center right", frameon=True, edgecolor="black",
              fancybox=False, fontsize=8, title_fontsize=9,
              framealpha=1.0, bbox_to_anchor=(1.0, 0.7))

    # Reverse y-axis so top term is on top
    ax.invert_yaxis()

    _despine(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGURES, "go_enrichment_v4.png"), dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("[OK] go_enrichment_v4.png")


# =====================================================================
# Utility
# =====================================================================
def _despine(ax):
    """Remove top and right spines."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


# =====================================================================
if __name__ == "__main__":
    plot_pca()
    plot_volcano()
    plot_go_enrichment()
    print("\nAll v4 figures saved to:", FIGURES)
