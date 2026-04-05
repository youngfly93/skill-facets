验证最近生成的文件是否满足 skill/command 的 CONSTRAINT 约束。

用法：
- `/validate <skill或command名> [目标目录]`：默认 `core profile`，强制走 `skills.yaml` contract
- `/validate --profile full <skill或command名> [目标目录]`：启用实验性 heuristic / human review 扩展
- `/validate --profile full --file <source.md> [目标目录]`：显式走 legacy Markdown parser

## 执行

```bash
python3 .claude/scripts/constraint_validator/cli.py $ARGUMENTS
```

说明：
- 命名 skill 时，不再静默回退到 `parser.py`
- 默认 `core profile` 只验证 `machine` 和 `runtime_enforced` 约束
- profile 先看约束的 `stability: core|experimental`，再决定是否评估
- `heuristic` / `human` / `legacy parser` 属于 `full profile` 的实验扩展
- 如果找不到 `skills.yaml`、找不到对应 contract，或缺少 PyYAML，会直接报错
- 只有 `--profile full --file ...` 才使用旧版 Markdown 正则提取路径

读取 JSON 输出，按以下格式展示：

```
## 约束验证报告

Profile: [core 或 full]
来源: [skills.yaml 或 约束文件路径]
目标: [检查目录]

| # | ID | 约束 | 严重度 | 状态 | 修复提示 |
|---|----|------|--------|------|----------|
| 1 | bg_white | background == #FFFFFF | hard_fail | ✅/❌ | plt.figure(facecolor='white') |
| 2 | no_gridlines | 不使用网格线 | soft_warn | ⚠️ | ax.grid(False) |

可用约束: N | 已评估: N | 跳过: N
通过: N | 硬失败: N | 软警告: N | 待人工: N | 运行时强制: N
```

## 闭环修复流程

当 hard_fail > 0 时执行以下循环，最多 3 轮：

1. **识别**: 列出所有 severity=hard_fail 且 passed=false 的约束及其 repair_hint
2. **修复**: 根据 repair_hint 自动修复（重新生成图片、修改文档属性等）
3. **重验证**: 再次运行 cli.py，检查 hard_fail 是否清零
4. **终止条件**: hard_fail == 0 或达到 3 轮上限

soft_warn 项列出但不阻塞。manual_review 项提示用户人工检查。runtime_enforced 项表示约束由 runner 或工具链在执行期强制，不由 validate CLI 重放。
