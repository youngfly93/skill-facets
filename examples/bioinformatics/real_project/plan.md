# 胃癌 RNA-seq 差异表达分析

## 项目背景

客户提供 6 例胃癌组织和 6 例癌旁正常组织的 RNA-seq 数据，要求进行差异表达分析并交付结果。

## 分析步骤

1. **数据质控** — FastQC + MultiQC
2. **比对与定量** — HISAT2 + featureCounts（参考基因组 GRCh38）
3. **差异表达分析** — DESeq2（|log2FC| > 1, padj < 0.05）
4. **可视化**
   - PCA 图
   - 火山图（Volcano plot）
   - 差异基因热图（Top 50）
5. **功能富集** — GO + KEGG（clusterProfiler）
6. **交付报告** — Word 格式

## 交付物

- 分析报告（Word）
- 差异基因列表（Excel）
- 所有图表（PNG, 300 DPI）
- 分析代码
