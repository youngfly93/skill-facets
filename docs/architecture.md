# 架构概览

## 设计动机

Anthropic Skills 标准用 Markdown + YAML frontmatter 定义 skill，通过 description 语义匹配触发。这套方案简洁但有三个结构性缺陷：

1. **触发不确定** — 250 字符 description 的语义匹配是概率性的
2. **约束不可验证** — CONSTRAINT 只是 Markdown 标题，模型"读到了"但没有运行时约束力
3. **工具/知识混淆** — 确定性脚本操作和柔性行为指导用同一个 SKILL.md 承载

skill-facets 通过四层架构解决这些问题，同时保持与 Anthropic Skills 标准的兼容。

## 四层架构

```
┌─────────────────────────────────────────────┐
│ Layer 1: Trigger Router                     │
│ skill_router.py + skills.yaml trigger 段     │
│ 关键词 + 文件模式 + 负向排除 → 确定性预筛选  │
├─────────────────────────────────────────────┤
│ Layer 2: V4 Nested Signals                  │
│ commands/*.md / SKILL.md                     │
│ CONSTRAINT > ASPIRATION > FREEDOM 嵌套       │
├─────────────────────────────────────────────┤
│ Layer 3: Constraint Validator               │
│ cli.py + checkers/ + skills.yaml contract   │
│ machine / heuristic / human 三级验证         │
├─────────────────────────────────────────────┤
│ Layer 4: Runtime Runner                     │
│ runner.py + skills.yaml workflow/tools       │
│ 状态机 gate + Tool Facet 脚本                │
└─────────────────────────────────────────────┘
```

## 核心文件

### skills.yaml — 单一事实源

所有 skill 的 trigger、contract、tools、workflow 定义集中在一个文件中。当前 32 个 skill，其中：
- 9 个有完整 contract（constraints + aspirations + freedoms）
- 21 个是官方 skill wrapper（只有 trigger + 基础 contract）
- 1 个有 Tool Facet + workflow（deliver-v4）

### manifest.py — 加载层

统一的 skills.yaml 读取 API。被 router、validator、compiler 共同导入。

关键特性：
- 从当前目录向上遍历查找 `.claude/skills.yaml`
- 显式要求 PyYAML（不做不可靠的手写 fallback）
- 带缓存，同一进程内不重复解析
- `get_contract()`、`get_trigger()`、`get_all_triggers()` 公开 API

### runtime_profile.yaml — 运行时配置

区分 core（稳定）和 full（实验）两个 profile：

| Profile | 包含的约束类型 | 用途 |
|---------|--------------|------|
| core | machine + runtime_enforced | 生产使用，结果确定性 |
| full | machine + heuristic + human | 开发调试，含实验性检查 |

## 数据流

### 触发链路

```
用户输入 "帮我画个火山图"
    ↓
UserPromptSubmit hook
    ↓
skill_router.py
  ├─ manifest.py → skills.yaml
  ├─ match_skill(): 关键词匹配 + 文件模式 + 评分
  ├─ logger.py → logs/skill_events.jsonl
  └─ stdout: "[skill-router] 建议使用 /sci-fig"
    ↓
模型读取推荐，调用 /sci-fig
```

### 验证链路

```
/validate sci-fig figures/
    ↓
cli.py
  ├─ manifest.py → skills.yaml → sci-fig.contract
  ├─ runtime_profile.py → core profile
  ├─ 遍历 contract.constraints
  │   ├─ stability=core + enforcement=machine → 执行 checker
  │   └─ stability=experimental → 跳过（core profile）
  ├─ checkers/color_checker.py → 检查背景色
  ├─ checkers/dpi_checker.py → 检查分辨率
  ├─ checkers/format_checker.py → 检查文件格式
  ├─ logger.py → logs/skill_events.jsonl
  └─ stdout: JSON 报告
```

### 编译链路

```
skills.yaml
    ↓
skill_compile.py
  ├─ contract.constraints → CONSTRAINT 段
  │   └─ compile.constraints_render（人类可读版）优先于 rule
  ├─ contract.aspirations → ASPIRATION 段
  ├─ contract.freedoms → FREEDOM 段
  ├─ compile.sections → 额外 Markdown 段落
  ├─ tools → Tool Facet 段（仅 skill 类型）
  └─ workflow → 步骤段（仅 skill 类型）
    ↓
commands/*.md 或 skills/*/SKILL.md
```

## 约束分类体系

每条约束有四个维度：

| 维度 | 值 | 含义 |
|------|-----|------|
| **severity** | hard_fail / soft_warn / manual_review | 违反时的严重程度 |
| **enforcement** | machine / heuristic / human | 验证方式 |
| **stability** | core / experimental | 是否属于稳定 API |
| **enforced_by** | checker / runtime / human | 谁来执行验证 |

## 与 Anthropic Skills 的关系

```
Anthropic Skills 标准（基座）
├─ SKILL.md 格式
├─ description 语义触发
├─ 渐进式披露（Catalog → Instructions → Resources）
├─ 24 个官方 skill（pptx, docx, pdf, xlsx...）
│
skill-facets（增强层）
├─ skills.yaml manifest（统一事实源）
├─ 触发路由（确定性预筛选）
├─ 约束验证（machine-checkable）
├─ 运行时执行（workflow gate）
├─ 编译器（skills.yaml → SKILL.md）
└─ MCP 桥接（Tool Facet → MCP server）
```

skill-facets **不替代** Anthropic Skills，而是让它更可控、可验证、可追溯。

## 测试

```bash
# 运行全部 54 个测试
python3 -m pytest tests/ -v

# 检查 manifest 定义合法性
python3 .claude/scripts/lint_manifest.py --cwd .

# 检查运行环境
python3 .claude/scripts/doctor.py
```
