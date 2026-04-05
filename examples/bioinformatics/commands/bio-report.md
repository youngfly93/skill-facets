配合 document-skills:docx 生成中文生信分析 Word 交付报告。

## 边界（CONSTRAINT）

- 中文正文：宋体（SimSun），小四号（12pt）
- 英文/数字：Times New Roman，12pt
- 一级标题：黑体（SimHei），三号（16pt），加粗
- 二级标题：黑体，四号（14pt），加粗
- 三级标题：黑体，小四号（12pt），加粗
- 行距：1.5 倍
- 页边距：上下 2.54cm，左右 3.18cm
- 图表编号连续（图 1, 图 2... 表 1, 表 2...），与正文引用一致
- 嵌入图片前必须验证路径存在（`ls -la "$img_path"`）
- 避免 AI 套话（参考 /ai-clean 关键词列表）
- 不得有 Markdown 标记残留（`**`, `##`, `` ` ``, `- [ ]`）

  ### 在此边界内追求（ASPIRATION）

  以下所有追求不得违反上方边界。

  - 图表与数据严格对应：每张图/表的数值来自结果文件，可追溯
  - XML 完整性：生成后解压验证所有 .xml 可读
  - 图片完整性：word/media/ 中的图片数量与文档引用数量一致
  - 表格使用三线表风格
  - 报告结构从 plan.md 的分析步骤自然组织章节
  - 图表居中显示，标题格式统一（`图 X. 描述` / `表 X. 描述`）

    #### 可自主决定（FREEDOM）

    以下选择空间在上方边界和追求方向内自主发挥。

    - 章节划分方式（跟随 plan.md 还是按逻辑重组）
    - 讨论部分的深度和角度
    - 补充内容的取舍（附录中放什么）
    - PDF 转图片时 _page1/_page2 的选择策略
    - 图片格式优先级（.png/.jpg/.tiff）

## 前置准备

1. 读取 plan.md 了解项目背景、分析内容和要求
2. 扫描 results/figures 目录收集所有可用的图表和结果
3. 确定报告结构

## 报告结构参考

```
1. 项目概述（背景、目标、数据概况）
2. 分析方法（质控、流程、软件与参数）
3. 分析结果（按 plan.md 步骤组织，每步配图表）
4. 结论与讨论
附录（软件版本、参数配置）
```

## 生成后验证

```bash
python3 -c "
import zipfile
z = zipfile.ZipFile('report.docx')
for f in z.namelist():
    if f.endswith('.xml'):
        z.read(f)
print('XML check passed')
"
```
