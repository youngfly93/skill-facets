# 如何写一个新 Skill

## 最小流程

1. 在 `skills.yaml` 中加一个条目
2. （可选）写一个 `commands/xxx.md` 作为人类可读文档
3. （可选）用编译器从 `skills.yaml` 自动生成 `.md`

## 第一步：在 skills.yaml 中定义

### 纯触发型（最简单，5 行）

只想让 router 能识别你的 skill：

```yaml
my-skill:
  version: "1.0"
  type: command
  description: "一句话描述"
  trigger:
    keywords: [关键词1, 关键词2]
    priority: 20
    hint: "使用 /my-skill 做什么"
```

### 带约束型（推荐，完整）

想让 `/validate` 也能检查输出：

```yaml
my-skill:
  version: "1.0"
  type: command
  source: commands/my-skill.md
  description: "一句话描述"
  trigger:
    keywords: [关键词1, 关键词2]
    negative_keywords: [排除词]
    file_patterns: ["*.xxx"]
    priority: 20
    hint: "使用 /my-skill 做什么"
  contract:
    constraints:
      - id: my_constraint
        type: format               # font/color/dpi/format/content/visual/layout/workflow
        rule: "人类可读的规则描述"
        severity: hard_fail         # hard_fail / soft_warn / manual_review
        enforcement: machine        # machine / heuristic / human
        stability: core             # core / experimental
        checker: format_checker     # 对应 checkers/ 下的模块名
        params: {allowed: [".png"]} # 传给 checker 的参数
        repair_hint: "修复建议"     # 可选
    aspirations:
      - "追求目标1"
      - "追求目标2"
    freedoms:
      - "可自主决定的事项1"
```

### 包装官方 Skill（不改原版）

给已有的 Anthropic 官方 skill 加 trigger + contract：

```yaml
some-official-skill:
  version: "1.0"
  type: skill
  wraps: "~/.claude/skills/xxx/SKILL.md"   # 指向全局原版
  description: "描述"
  trigger:
    keywords: [...]
    hint: "使用 xxx skill"
  contract:
    constraints:
      - id: valid_output
        type: format
        rule: "输出格式正确"
        severity: hard_fail
        enforcement: machine
        checker: format_checker
        params: {allowed: [".xxx"]}
```

## 第二步：写 commands/xxx.md（可选）

如果你的 skill 是 command 类型，写一个 `.md` 文件：

```markdown
一行描述。

## 边界（CONSTRAINT）

- 硬约束1
- 硬约束2

  ### 在此边界内追求（ASPIRATION）

  以下所有追求不得违反上方边界。

  - 追求1
  - 追求2

    #### 可自主决定（FREEDOM）

    以下选择空间在上方边界和追求方向内自主发挥。

    - 自由项1
```

或者用编译器自动生成：

```bash
python3 .claude/scripts/skill_compile.py my-skill --write
```

## 第三步：添加 checker（可选）

如果你定义了 `checker: xxx_checker`，需要在 `checkers/` 下创建对应的 Python 模块：

```python
# .claude/scripts/constraint_validator/checkers/xxx_checker.py

def check(check_type, params, files):
    violations = []
    # 你的检查逻辑
    return {
        "passed": len(violations) == 0,
        "check_type": check_type,
        "details": "检查描述",
        "violations": violations,
    }
```

然后在 `cli.py` 的 `REGISTRY` 中注册：

```python
from checkers import xxx_checker
REGISTRY["my_check_type"] = xxx_checker.check
```

## 约束设计原则

### 三信号嵌套

```
CONSTRAINT（外层边界）    → 不可违反的硬性要求
  └─ ASPIRATION（中间方向）→ 在边界内积极追求的目标
       └─ FREEDOM（内层自主）→ 在方向内可自行决定的选择
```

**关键**：FREEDOM 不能和 CONSTRAINT 冲突。嵌套关系让这一点在文档结构上显式表达。

### severity 选择

| severity | 何时用 | 验证行为 |
|----------|--------|---------|
| `hard_fail` | 必须满足，违反则阻塞 | validator 报错，触发修复循环 |
| `soft_warn` | 建议满足，违反则提醒 | validator 警告但不阻塞 |
| `manual_review` | 需要人工判断 | validator 标记为待确认 |

### enforcement 选择

| enforcement | 含义 | 何时用 |
|-------------|------|--------|
| `machine` | 有 checker 可自动验证 | 字体、颜色、DPI、格式等 |
| `heuristic` | 部分可自动化但不完全可靠 | 网格线检测、布局检查 |
| `human` | 只能人工判断 | 逻辑清晰度、美感、内容质量 |

## 双 Facet Skill（进阶）

当 skill 包含确定性脚本操作时，用双 Facet 架构：

```yaml
my-hybrid-skill:
  type: skill
  source: skills/my-skill/SKILL.md
  contract: {...}
  tools:
    - name: my_tool
      script: scripts/my_tool.py
      commands:
        run:
          inputs: {input_dir: path}
          outputs: {result: dict}
          exit_codes: {0: success, 1: error}
  workflow:
    states: [init, process, validate, done]
    transitions:
      init: {next: process, condition: "input exists"}
      process: {next: validate}
      validate: {next: done, condition: "all checks pass"}
```

脚本放在 `skills/my-skill/scripts/` 下，必须返回 JSON。
