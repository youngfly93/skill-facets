# 5 分钟上手 skill-facets

## 这是什么

skill-facets 是一个项目级的 Claude Code skill 增强框架。它不替代 Anthropic Skills 标准，而是在上面叠加三层能力：

1. **触发路由** — 关键词匹配，减少 undertrigger
2. **约束验证** — 执行后自动检查字体/颜色/DPI 等硬约束
3. **双 Facet 分离** — 确定性操作用脚本，行为指导用 Markdown

## 安装（3 步）

```bash
# 1. 克隆到项目目录
git clone https://github.com/youngfly93/skill-facets.git
cd skill-facets

# 2. 安装运行时依赖
bash .claude/bootstrap_env.sh

# 3. 注册项目级 hook
bash .claude/install_local.sh
```

完成后运行 doctor 确认：

```bash
.claude/.venv/bin/python .claude/scripts/doctor.py
```

全部 `[OK]` 即可使用。

## 基本用法

在 `skill-facets/` 目录下启动 Claude Code，项目级 commands 会自动覆盖全局同名 commands：

```
/ppt              → V4 嵌套信号指导 PPT 制作
/sci-fig          → V4 嵌套信号指导 SCI 图表
/audit-fix        → V4 嵌套信号指导审计修复
/bio-report       → V4 嵌套信号指导 Word 报告
```

### 验证约束

执行完 `/sci-fig` 后，检查图表是否满足约束：

```
/validate sci-fig figures/
```

输出示例：

```
## 约束验证报告

Profile: core

| # | ID | 约束 | 严重度 | 状态 |
|---|----|------|--------|------|
| 1 | bg_white | background == #FFFFFF | hard_fail | ✅ |
| 2 | min_dpi | dpi >= 300 | hard_fail | ✅ |
| 3 | output_format | ext in [.png, .pdf] | hard_fail | ✅ |

通过: 3 | 硬失败: 0
```

如果有 `hard_fail`，validator 会给出 `repair_hint`（如 `plt.savefig(path, dpi=300)`），模型可据此自动修复。

### 打包交付

```
/deliver-v4
```

自动执行：质量审计 → 文件收集 → AI 痕迹扫描 → 校验和 → ZIP 打包 → 验证。

## 离开项目目录

离开 `skill-facets/` 后，所有行为恢复到全局 `~/.claude/` 的默认状态。**全局环境零污染**。

## 下一步

- 想写自己的 skill？看 [authoring-guide.md](authoring-guide.md)
- 想了解编译器？看 [compiler-guide.md](compiler-guide.md)
- 想了解架构全貌？看 [architecture.md](architecture.md)
