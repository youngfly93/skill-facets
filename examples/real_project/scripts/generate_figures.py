#!/usr/bin/env python3
"""
V4 sci-fig 约束下生成 SCI 图表。
CONSTRAINT: 白底、无网格线、>=300DPI、坐标轴有标签、.png 格式
ASPIRATION: 色盲友好、文字可读、图例完整
"""
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os

COLORS = {
    'up': '#E69F00', 'down': '#0072B2', 'ns': '#999999',
    'tumor': '#D55E00', 'normal': '#0072B2',
    'BP': '#009E73', 'CC': '#56B4E9', 'MF': '#E69F00',
}

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, 'figures')
DATA = os.path.join(BASE, 'results')
os.makedirs(OUT, exist_ok=True)

def style_ax(ax):
    ax.set_facecolor('white')
    ax.grid(False)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

# === 1. PCA ===
pca = pd.read_csv(f'{DATA}/PCA_data.csv')
fig, ax = plt.subplots(figsize=(6, 5), facecolor='white')
style_ax(ax)
from matplotlib.patches import Ellipse
for grp, c, m in [('Tumor', COLORS['tumor'], 'o'), ('Normal', COLORS['normal'], 's')]:
    sub = pca[pca['group'] == grp]
    ax.scatter(sub['PC1'], sub['PC2'], c=c, marker=m, s=80,
               edgecolors='black', linewidths=0.5, label=grp, zorder=3)
    cov = np.cov(sub['PC1'], sub['PC2'])
    vals, vecs = np.linalg.eigh(cov)
    angle = np.degrees(np.arctan2(vecs[1,1], vecs[0,1]))
    w, h = 2 * np.sqrt(vals * 5.991)
    ell = Ellipse((sub['PC1'].mean(), sub['PC2'].mean()), w, h, angle=angle,
                  facecolor=c, alpha=0.15, edgecolor=c, linestyle='--', linewidth=1)
    ax.add_patch(ell)
ax.set_xlabel('PC1', fontsize=12, fontweight='bold')
ax.set_ylabel('PC2', fontsize=12, fontweight='bold')
ax.set_title('Principal Component Analysis', fontsize=14, fontweight='bold')
ax.legend(frameon=False, fontsize=11)
fig.tight_layout()
fig.savefig(f'{OUT}/pca_plot.png', dpi=300, facecolor='white', bbox_inches='tight')
plt.close()
print('pca_plot.png')

# === 2. Volcano ===
deg = pd.read_csv(f'{DATA}/DEG_results.csv')
deg['-log10padj'] = -np.log10(deg['padj'].astype(float))
fig, ax = plt.subplots(figsize=(7, 5.5), facecolor='white')
style_ax(ax)
sig_up = (deg['log2FoldChange'] > 1) & (deg['padj'] < 0.05)
sig_down = (deg['log2FoldChange'] < -1) & (deg['padj'] < 0.05)
ns = ~(sig_up | sig_down)
ax.scatter(deg.loc[ns, 'log2FoldChange'], deg.loc[ns, '-log10padj'], c=COLORS['ns'], s=15, alpha=0.6, label=f'NS ({ns.sum()})')
ax.scatter(deg.loc[sig_up, 'log2FoldChange'], deg.loc[sig_up, '-log10padj'], c=COLORS['up'], s=20, alpha=0.8, label=f'Up ({sig_up.sum()})')
ax.scatter(deg.loc[sig_down, 'log2FoldChange'], deg.loc[sig_down, '-log10padj'], c=COLORS['down'], s=20, alpha=0.8, label=f'Down ({sig_down.sum()})')
ax.axhline(-np.log10(0.05), color='grey', linestyle='--', linewidth=0.8, alpha=0.6)
ax.axvline(1, color='grey', linestyle='--', linewidth=0.8, alpha=0.6)
ax.axvline(-1, color='grey', linestyle='--', linewidth=0.8, alpha=0.6)
top = pd.concat([deg[sig_up].nsmallest(5, 'padj'), deg[sig_down].nsmallest(5, 'padj')])
for _, r in top.iterrows():
    c = COLORS['up'] if r['log2FoldChange'] > 0 else COLORS['down']
    ax.annotate(r['symbol'], (r['log2FoldChange'], r['-log10padj']),
                fontsize=8, color=c, fontweight='bold', xytext=(5, 5), textcoords='offset points')
ax.set_xlabel('log₂(Fold Change)', fontsize=12, fontweight='bold')
ax.set_ylabel('-log₁₀(adjusted p-value)', fontsize=12, fontweight='bold')
ax.set_title('Differential Expression Analysis', fontsize=14, fontweight='bold')
ax.legend(frameon=False, fontsize=10, loc='upper right')
fig.tight_layout()
fig.savefig(f'{OUT}/volcano_plot.png', dpi=300, facecolor='white', bbox_inches='tight')
plt.close()
print('volcano_plot.png')

# === 3. GO Enrichment ===
go = pd.read_csv(f'{DATA}/GO_enrichment.csv')
go['GR'] = go['GeneRatio'].apply(lambda x: int(x.split('/')[0]) / int(x.split('/')[1]))
fig, ax = plt.subplots(figsize=(8, 5), facecolor='white')
style_ax(ax)
for cat in ['BP', 'CC', 'MF']:
    sub = go[go['Category'] == cat]
    ax.scatter(sub['GR'], sub['Term'], s=sub['Count'] * 8, c=COLORS[cat],
               alpha=0.75, edgecolors='black', linewidths=0.5, label=cat, zorder=3)
    for _, r in sub.iterrows():
        ax.annotate(str(r['Count']), (r['GR'], r['Term']),
                    ha='center', va='center', fontsize=8, fontweight='bold', color='white')
ax.set_xlabel('Gene Ratio', fontsize=12, fontweight='bold')
ax.set_title('GO Enrichment Analysis', fontsize=14, fontweight='bold')
ax.legend(title='Category', frameon=False, fontsize=10)
fig.tight_layout()
fig.savefig(f'{OUT}/go_enrichment.png', dpi=300, facecolor='white', bbox_inches='tight')
plt.close()
print('go_enrichment.png')

# === 4. KEGG ===
kegg = pd.read_csv(f'{DATA}/KEGG_enrichment.csv')
kegg['-log10FDR'] = -np.log10(kegg['FDR'].astype(float))
kegg = kegg.sort_values('-log10FDR')
fig, ax = plt.subplots(figsize=(7, 4), facecolor='white')
style_ax(ax)
bars = ax.barh(kegg['Pathway'], kegg['-log10FDR'], color=COLORS['up'],
               edgecolor='black', linewidth=0.5, height=0.6)
for bar, cnt in zip(bars, kegg['Count']):
    ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height()/2, f'n={cnt}', va='center', fontsize=9)
ax.set_xlabel('-log₁₀(FDR)', fontsize=12, fontweight='bold')
ax.set_title('KEGG Pathway Enrichment', fontsize=14, fontweight='bold')
ax.axvline(-np.log10(0.05), color='grey', linestyle='--', linewidth=0.8, alpha=0.6, label='FDR=0.05')
ax.legend(frameon=False, fontsize=9)
fig.tight_layout()
fig.savefig(f'{OUT}/kegg_enrichment.png', dpi=300, facecolor='white', bbox_inches='tight')
plt.close()
print('kegg_enrichment.png')

print('\nAll figures generated.')
