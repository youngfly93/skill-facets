#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SETTINGS_FILE="$SCRIPT_DIR/settings.local.json"
VENV_PY="$SCRIPT_DIR/.venv/bin/python"
HOOK_COMMAND='$CLAUDE_PROJECT_DIR/.claude/.venv/bin/python $CLAUDE_PROJECT_DIR/.claude/hooks/skill_router.py'

echo "=== skill-facets local hook installer ==="
echo "Project .claude: $SCRIPT_DIR"

if [ ! -x "$VENV_PY" ]; then
  echo "ERROR: missing project Python: $VENV_PY" >&2
  echo "Run: bash .claude/bootstrap_env.sh" >&2
  exit 2
fi

export SETTINGS_FILE HOOK_COMMAND

"$VENV_PY" - <<'PY'
import json
import os
from pathlib import Path

settings_path = Path(os.environ["SETTINGS_FILE"])
hook_command = os.environ["HOOK_COMMAND"]

if settings_path.exists():
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {settings_path}: {exc}")
    action = "updated"
else:
    data = {}
    action = "created"

hooks = data.setdefault("hooks", {})
submit = hooks.setdefault("UserPromptSubmit", [])

found = False
for entry in submit:
    if not isinstance(entry, dict):
        continue
    entry.setdefault("matcher", "")
    hook_list = entry.setdefault("hooks", [])
    if not isinstance(hook_list, list):
        continue
    for hook in hook_list:
        if not isinstance(hook, dict):
            continue
        cmd = hook.get("command", "")
        if "skill_router.py" in cmd:
            hook["type"] = "command"
            hook["command"] = hook_command
            hook["timeout"] = 3
            found = True

if not found:
    submit.append(
        {
            "matcher": "",
            "hooks": [
                {
                    "type": "command",
                    "command": hook_command,
                    "timeout": 3,
                }
            ],
        }
    )
    if action != "created":
        action = "updated"

settings_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{action}:{settings_path}")
PY

echo
echo "Hook registration complete."
echo "Settings file: $SETTINGS_FILE"
echo "Next step:"
echo "  $VENV_PY $SCRIPT_DIR/scripts/doctor.py"
