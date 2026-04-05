#!/bin/bash
set -euo pipefail
# 查看项目级 V4 skill 隔离状态，并在可用时调用 doctor.py
# 用法: bash .claude/skill_switch.sh

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLAUDE_DIR="$PROJECT_DIR/.claude"
GLOBAL_SETTINGS="$HOME/.claude/settings.json"
VENV_PY="$CLAUDE_DIR/.venv/bin/python"
DOCTOR="$CLAUDE_DIR/scripts/doctor.py"

echo "=== V4 Skill 隔离环境状态 ==="
echo ""

echo "🧭 Runtime profile:"
if [ -f "$CLAUDE_DIR/runtime_profile.yaml" ]; then
  if [ -x "$VENV_PY" ] && "$VENV_PY" - <<'PY' 2>/dev/null
import sys
from pathlib import Path
sys.path.insert(0, str(Path(".claude/scripts").resolve()))
from runtime_profile import load_runtime_profile
p = load_runtime_profile(cwd=".")
print(f"  ✅ {p['name']} — {p.get('description','')}")
PY
  then
    :
  else
    echo "  ⚠️  runtime_profile.yaml 存在，但当前无法读取（先运行 bootstrap_env.sh）"
  fi
else
  echo "  ❌ runtime_profile.yaml 缺失"
fi

echo ""

# 项目级 commands
echo "📁 项目级 commands (.claude/commands/):"
for f in ppt.md sci-fig.md audit-fix.md bio-report.md validate.md; do
  if [ -f "$CLAUDE_DIR/commands/$f" ]; then
    if grep -q "CONSTRAINT" "$CLAUDE_DIR/commands/$f" 2>/dev/null; then
      echo "  ✅ $f (V4 嵌套信号)"
    else
      echo "  ✅ $f"
    fi
  else
    echo "  ❌ $f (缺失)"
  fi
done

echo ""

# 项目级 skills
echo "📁 项目级 skills (.claude/skills/):"
if [ -f "$CLAUDE_DIR/skills/deliver-v4/SKILL.md" ]; then
  echo "  ✅ deliver-v4 (双 Facet + V4)"
  ls "$CLAUDE_DIR/skills/deliver-v4/scripts/"*.py 2>/dev/null | while read f; do
    echo "     └─ $(basename $f)"
  done
else
  echo "  ❌ deliver-v4 (缺失)"
fi

echo ""

# Trigger + Validator
echo "📁 工具链:"
[ -f "$CLAUDE_DIR/skill_triggers.yaml" ] && echo "  ✅ skill_triggers.yaml" || echo "  ❌ skill_triggers.yaml"
[ -f "$CLAUDE_DIR/skill_triggers.yaml" ] && echo "     └─ experimental compatibility fallback" || true
[ -f "$CLAUDE_DIR/hooks/skill_router.py" ] && echo "  ✅ skill_router.py" || echo "  ❌ skill_router.py"
[ -f "$CLAUDE_DIR/scripts/constraint_validator/cli.py" ] && echo "  ✅ constraint_validator" || echo "  ❌ constraint_validator"
[ -f "$CLAUDE_DIR/install_local.sh" ] && echo "  ✅ install_local.sh" || echo "  ❌ install_local.sh"
[ -f "$CLAUDE_DIR/bootstrap_env.sh" ] && echo "  ✅ bootstrap_env.sh" || echo "  ❌ bootstrap_env.sh"
[ -f "$DOCTOR" ] && echo "  ✅ doctor.py" || echo "  ❌ doctor.py"

echo ""

# 全局污染检查（只读）
echo "🔒 全局 ~/.claude/ 污染检查（只读）:"
if python3 -c "
import json
with open('$GLOBAL_SETTINGS') as f: s = json.load(f)
exit(0 if 'UserPromptSubmit' in s.get('hooks', {}) else 1)
" 2>/dev/null; then
  echo "  ⚠️  全局 settings.json 有 UserPromptSubmit hook（已污染）"
else
  echo "  ✅ 全局 settings.json 无 V4 hook（干净）"
fi

if grep -q "CONSTRAINT" "$HOME/.claude/commands/ppt.md" 2>/dev/null; then
  echo "  ⚠️  全局 ppt.md 是 V4 版本（已污染）"
else
  echo "  ✅ 全局 commands 是 V0 原版（干净）"
fi

echo ""
echo "💡 提示:"
echo "  - 在 skill_change/ 目录启动 Claude Code 时，项目级 V4 commands 会覆盖同名全局 V0"
echo "  - 离开此目录后恢复全局 V0 行为"
echo "  - 先运行: bash .claude/bootstrap_env.sh"
echo "  - 再运行: bash .claude/install_local.sh"
echo "  - 默认 profile 是 core；如需启用实验性启发式校验，使用: --profile full"
echo "  - 最后检查: .claude/.venv/bin/python .claude/scripts/doctor.py"
echo "  - 此脚本不会修改任何全局文件"

if [ -x "$VENV_PY" ] && [ -f "$DOCTOR" ]; then
  echo ""
  echo "=== Runtime doctor ==="
  "$VENV_PY" "$DOCTOR" || true
fi
