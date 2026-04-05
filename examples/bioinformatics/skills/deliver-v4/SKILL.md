---
name: deliver-v4
description: >-
  一键交付打包：质量审计→文件收集→AI痕迹扫描→ZIP打包全流程。
  触发条件：用户说"交付"、"打包"、"deliver"、"发给客户"、"出包"。
  不适用于：仅需部分文件复制、非项目交付场景。
---

# 交付打包

## Tool Facet — 确定性操作

本 skill 提供两个独立工具脚本，位于 `${CLAUDE_SKILL_DIR}/scripts/`：

### zip_pack.py

```bash
# 打包
python3 ${CLAUDE_SKILL_DIR}/scripts/zip_pack.py pack <delivery_dir> [项目名]
# → {"zip_path": "..."}

# 验证
python3 ${CLAUDE_SKILL_DIR}/scripts/zip_pack.py verify <zip_path>
# → {"crc_ok": true, "file_count": N, "total_size_mb": N, "files": [...]}

# 校验和
python3 ${CLAUDE_SKILL_DIR}/scripts/zip_pack.py checksum <delivery_dir>
# → {"checksum_path": "..."}
```

### ai_trace_scan.py

```bash
# 扫描
python3 ${CLAUDE_SKILL_DIR}/scripts/ai_trace_scan.py scan <directory>
# → JSON 数组，每项 {"file": "...", "type": "metadata|content", "match": "..."}
# 退出码: 0=无痕迹, 1=发现痕迹

# 清除
python3 ${CLAUDE_SKILL_DIR}/scripts/ai_trace_scan.py clean <directory>
# → JSON 数组，每项 {"file": "...", "cleaned_count": N}
```

---

## Prompt Facet — 流程决策指导

### 边界（CONSTRAINT）

- 步骤 1→7 顺序执行，不可跳步
- 步骤 1 有 P0/P1 问题 → 中止打包，建议 `/audit-fix`
- ZIP 打包和 AI 扫描必须调用上方 Tool Facet 脚本，不可内联重写
- 排除文件：.DS_Store, __MACOSX, .git, .Rhistory, .RData, Thumbs.db
- 必须有 plan.md 才能启动（无则停止，提醒先建立）
- ZIP 文件名格式：`项目名_交付_YYYYMMDD.zip`

  #### 在此边界内追求（ASPIRATION）

  以下所有追求不得违反上方边界。

  - AI 痕迹彻底清除（宁多扫不遗漏）
  - Windows 兼容性（中文文件名不乱码）
  - 交付物结构规范：`01_分析报告/` ... `05_分析代码/`，目录编号清晰
  - Word 文档完整性经过验证（图片引用、XML 结构、中文字体）

    ##### 可自主决定（FREEDOM）

    以下选择空间在上方边界和追求方向内自主发挥。

    - 已有 delivery/ 时覆盖还是增量（询问用户）
    - P2/P3 问题的处理方式（警告继续 vs 先修复）
    - `05_分析代码/` 是否包含（根据项目判断）

### 步骤

**Step 1 — 质量审计（门控）**
用 bio-result-auditor agent 对照 plan.md 审计。

**Step 2 — 收集交付物**
按 plan.md 确定文件，复制到 `delivery/` 子目录。不复制中间文件（.RData, .rds）和原始数据（fastq, bam）。

**Step 3 — AI 痕迹扫描与清除**
先 `ai_trace_scan.py scan delivery/` 扫描；有痕迹则 `ai_trace_scan.py clean delivery/` 清除；再 `scan` 确认清零。

**Step 4 — Word 文档验证**
检查 .docx 图片引用、XML 完整性、中文字体。

**Step 5 — 校验和**
调用 `zip_pack.py checksum delivery/`

**Step 6 — 打包**
调用 `zip_pack.py pack delivery/ 项目名`

**Step 7 — 验证**
调用 `zip_pack.py verify <zip_path>`

### 最终输出

```
| 步骤 | 状态 | 详情 |
|------|------|------|
| 1. 质量审计 | ✅/❌ | P0:0 P1:0 P2:N P3:N |
| 2. 文件收集 | ✅ | N 个文件, XX MB |
| 3. AI痕迹 | ✅/⚠️ | 清除 N 处 |
| 4. Word验证 | ✅/❌ | N 个文档通过 |
| 5. 校验和 | ✅ | delivery_md5.txt |
| 6. ZIP打包 | ✅ | 文件名 |
| 7. ZIP验证 | ✅ | CRC通过, N 文件 |

ZIP路径: xxx
ZIP大小: xx MB
```
