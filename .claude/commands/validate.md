验证最近生成的文件是否满足 skill/command 的 CONSTRAINT 约束。

用法：`/validate <skill或command名> [目标目录]`

## 执行

```bash
python3 .claude/scripts/constraint_validator/cli.py $ARGUMENTS
```

读取 JSON 输出，按以下格式展示：

```
## 约束验证报告

来源: [skills.yaml 或 约束文件路径]
目标: [检查目录]

| # | ID | 约束 | 严重度 | 状态 | 修复提示 |
|---|----|------|--------|------|----------|
| 1 | bg_white | background == #FFFFFF | hard_fail | ✅/❌ | plt.figure(facecolor='white') |
| 2 | no_gridlines | 不使用网格线 | manual_review | ⚠️ | ax.grid(False) |

通过: N | 硬失败: N | 软警告: N | 待人工: N
```

## 闭环修复流程

当 hard_fail > 0 时执行以下循环，最多 3 轮：

1. **识别**: 列出所有 severity=hard_fail 且 passed=false 的约束及其 repair_hint
2. **修复**: 根据 repair_hint 自动修复（重新生成图片、修改文档属性等）
3. **重验证**: 再次运行 cli.py，检查 hard_fail 是否清零
4. **终止条件**: hard_fail == 0 或达到 3 轮上限

soft_warn 项列出但不阻塞。manual_review 项提示用户人工检查。
