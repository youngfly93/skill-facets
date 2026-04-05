# 编译器使用指南

## 概念

skill-facets 的核心理念是 **skills.yaml 是唯一编写源，Markdown 是编译产物**。

```
skills.yaml (你维护这个)
    │
    ├─ skill_compile.py → commands/*.md / skills/*/SKILL.md  (给 Claude Code 读)
    ├─ mcp_bridge.py    → mcp/*_server.py                    (给 MCP agent 读)
    └─ validator        → 约束检查                            (机器验证)
```

## skill_compile.py

### 列出可编译的 skill

```bash
python3 .claude/scripts/skill_compile.py --list
```

输出：
```
可编译的 skill（有 contract）：
  ✅ ppt                       → commands/ppt.md
  ✅ sci-fig                   → commands/sci-fig.md
  ✅ deliver-v4                → skills/deliver-v4/SKILL.md +tools
  ○ transfer                  → (no source)
```

`✅` 表示有 contract，可编译出完整的嵌套信号 Markdown。`○` 表示只有 trigger，编译结果只有描述行。

### 预览编译结果

```bash
python3 .claude/scripts/skill_compile.py sci-fig
```

输出编译后的 Markdown 到 stdout，不写文件。

### 写入文件

```bash
# 单个
python3 .claude/scripts/skill_compile.py sci-fig --write

# 全部
python3 .claude/scripts/skill_compile.py --all --write
```

### 检查差异

```bash
python3 .claude/scripts/skill_compile.py sci-fig --write --diff
```

输出 `≡ unchanged` 或 `Δ changed`，只在有变化时才写入。

### 输出到其他目录

```bash
python3 .claude/scripts/skill_compile.py --all --write --out-dir ./dist
```

### compile 元数据

在 `skills.yaml` 中可以用 `compile` 段控制编译输出的细节：

```yaml
my-skill:
  contract: {...}
  compile:
    lead: "自定义首行文本（替代 description）"
    constraints_render:          # 人类可读版约束（替代 rule 字段）
      - "中文字体：黑体"
      - "背景纯白"
    aspirations_render:          # 人类可读版追求
      - "配色协调"
    freedoms_render:             # 人类可读版自由度
      - "具体配色自选"
    sections:                    # 额外的 Markdown 段落
      - title: "前置准备"
        title_level: 2
        ordered:
          - "读取 plan.md"
          - "扫描 results/ 目录"
      - title: "生成后验证"
        title_level: 2
        code: |
          python3 -c "import zipfile; ..."
        code_lang: bash
```

**为什么需要两套文本**：`rule` 字段是机器语义（如 `background == #FFFFFF`），validator 读这个；`constraints_render` 是人类语义（如"背景纯白"），编译器输出这个。

## mcp_bridge.py

### 列出可暴露为 MCP tool 的 skill

```bash
python3 .claude/scripts/mcp_bridge.py --list
```

### 生成 MCP server 代码

```bash
# 预览
python3 .claude/scripts/mcp_bridge.py --generate deliver-v4

# 写入文件
python3 .claude/scripts/mcp_bridge.py --generate deliver-v4 --write
# → .claude/mcp/deliver-v4_server.py
```

### 启动 MCP server（需要 fastmcp）

```bash
pip install fastmcp
python3 .claude/scripts/mcp_bridge.py --serve deliver-v4
```

生成的 server 暴露 Tool Facet 的每个命令为一个 MCP tool：

```
zip_pack_pack(delivery_dir, project_name) → {zip_path}
zip_pack_verify(zip_path) → {crc_ok, file_count, total_size_mb}
zip_pack_checksum(delivery_dir) → {checksum_path}
ai_trace_scan_scan(directory) → [{file, type, match}]
ai_trace_scan_clean(directory) → [{file, cleaned_count}]
```
