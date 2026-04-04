一键交付打包：从质量审计到生成 Windows 兼容 ZIP 全流程自动化。

## 步骤 1：最终质量审计

使用 bio-result-auditor agent 对照 plan.md 做最终审计：
- 如果存在 P0/P1 问题，**中止打包**并输出问题清单
- 仅 P2/P3 问题时提醒但继续

## 步骤 2：收集交付物

在项目根目录创建 `delivery/` 目录，按中文编号组织：

```
delivery/
├── 01_分析报告/          # Word 报告
├── 02_结果图表/          # figures/ 中的关键图表
├── 03_数据表格/          # 关键结果表格（xlsx/csv）
├── 04_补充材料/          # 补充分析结果
└── 05_分析代码/          # 关键脚本（可选）
```

- 根据 plan.md 和实际结果确定需要交付的文件
- 复制文件到对应目录，保持原始文件名

## 步骤 3：AI 痕迹扫描

对 delivery/ 中所有文件执行 AI 痕迹扫描（等效 /ai-clean）：
- 扫描 .docx/.xlsx/.pptx 元数据中的 AI 相关字段
- 扫描文本内容中的 AI 典型表达
- 发现问题则修复后继续

## 步骤 4：验证 Word 文档

检查 delivery/ 中的 .docx 文件：
- 图片引用路径是否有效
- XML 结构是否完整
- 中文字体设置是否正确

## 步骤 5：生成校验和

```bash
cd delivery && find . -type f ! -name "*.md5" | sort | xargs md5 > ../delivery_md5.txt
```

## 步骤 6：创建 Windows 兼容 ZIP

使用 python3 zipfile 模块打包（保证中文文件名在 Windows 下不乱码）：
- 排除: `.DS_Store`, `__MACOSX`, `.git`, `.Rhistory`, `.RData`, `Thumbs.db`
- ZIP 文件名格式: `项目名_交付_YYYYMMDD.zip`

```python
import zipfile, os, datetime
# 使用 ZIP_DEFLATED 压缩，allowZip64=True
```

## 步骤 7：验证 ZIP

```bash
python3 -c "import zipfile; z=zipfile.ZipFile('xxx.zip'); z.testzip(); print(z.namelist())"
```

## 最终输出

打包检查清单：

```
| 检查项 | 状态 |
|--------|------|
| 质量审计通过 | ✅/❌ |
| 文件收集完成 | ✅ (N 个文件) |
| AI 痕迹清除 | ✅/⚠️ |
| Word 文档验证 | ✅/❌ |
| MD5 校验和生成 | ✅ |
| ZIP 创建并验证 | ✅ |
```

ZIP 文件路径和大小。
