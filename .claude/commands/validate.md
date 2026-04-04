验证最近生成的文件是否满足 skill/command 的 CONSTRAINT 约束。

用法：`/validate <skill或command名> [目标目录]`

## 执行

```bash
python3 .claude/scripts/constraint_validator/cli.py $ARGUMENTS
```

读取 JSON 输出，按以下格式展示：

```
## 约束验证报告

来源: [约束文件路径]
目标: [检查目录]

| # | 约束 | 状态 | 详情 |
|---|------|------|------|
| 1 | xxx  | ✅/❌/⚠️ | ... |

通过: N | 失败: N | 待人工确认: N
```

如果有 failed > 0，列出违规项并**立即修复**可自动修复的问题，修复后重新验证。
