#!/usr/bin/env python3
"""Environment doctor for the project-level skill runtime."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from runtime_profile import load_runtime_profile
SCRIPT_PATH = Path(__file__).resolve()
CLAUDE_DIR = SCRIPT_PATH.parents[1]
PROJECT_DIR = CLAUDE_DIR.parent
SETTINGS_LOCAL = CLAUDE_DIR / "settings.local.json"
REQUIREMENTS = CLAUDE_DIR / "requirements.txt"
RUNTIME_PROFILE = CLAUDE_DIR / "runtime_profile.yaml"
SKILLS_YAML = CLAUDE_DIR / "skills.yaml"
ROUTER = CLAUDE_DIR / "hooks" / "skill_router.py"
VALIDATOR = CLAUDE_DIR / "scripts" / "constraint_validator" / "cli.py"
LINT_MANIFEST = CLAUDE_DIR / "scripts" / "lint_manifest.py"
SCI_FIG = CLAUDE_DIR / "commands" / "sci-fig.md"
SCI_FIG_TARGET = PROJECT_DIR / "examples" / "real_project" / "figures"
VENV_PY = CLAUDE_DIR / ".venv" / "bin" / "python"


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True)


def check(label: str, ok: bool, detail: str, fatal: bool = True) -> dict:
    return {"label": label, "ok": ok, "detail": detail, "fatal": fatal}


def load_settings() -> tuple[bool, dict | None, str]:
    if not SETTINGS_LOCAL.exists():
        return False, None, f"missing {SETTINGS_LOCAL}"
    try:
        data = json.loads(SETTINGS_LOCAL.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, None, f"invalid JSON: {exc}"
    return True, data, str(SETTINGS_LOCAL)


def find_router_hook(settings: dict) -> tuple[bool, str]:
    hooks = settings.get("hooks", {}).get("UserPromptSubmit", [])
    for entry in hooks:
        for hook in entry.get("hooks", []):
            cmd = hook.get("command", "")
            if "skill_router.py" in cmd:
                return True, cmd
    return False, "UserPromptSubmit missing skill_router.py command"


def has_appledouble_files() -> tuple[bool, str]:
    if not VENV_PY.exists():
        return False, "venv missing"
    matches = list(CLAUDE_DIR.joinpath(".venv").rglob("._*"))
    if not matches:
        return True, "clean"
    preview = ", ".join(str(p.relative_to(CLAUDE_DIR)) for p in matches[:3])
    if len(matches) > 3:
        preview += ", ..."
    return False, preview


def main() -> int:
    rows: list[dict] = []

    rows.append(check("project_root", PROJECT_DIR.exists(), str(PROJECT_DIR)))
    rows.append(check("skills_yaml", SKILLS_YAML.exists(), str(SKILLS_YAML)))
    rows.append(check("requirements", REQUIREMENTS.exists(), str(REQUIREMENTS)))
    rows.append(check("runtime_profile", RUNTIME_PROFILE.exists(), str(RUNTIME_PROFILE)))
    rows.append(check("router_script", ROUTER.exists(), str(ROUTER)))
    rows.append(check("validator_cli", VALIDATOR.exists(), str(VALIDATOR)))
    rows.append(check("manifest_lint_script", LINT_MANIFEST.exists(), str(LINT_MANIFEST)))
    rows.append(check("current_python", True, sys.executable))

    if VENV_PY.exists():
        rows.append(check("venv_python", True, str(VENV_PY)))
    else:
        rows.append(check("venv_python", False, f"missing {VENV_PY}; run `bash .claude/bootstrap_env.sh`"))

    apple_ok, apple_detail = has_appledouble_files()
    rows.append(check("venv_metadata_files", apple_ok, apple_detail))

    ok, settings, detail = load_settings()
    rows.append(check("settings_local", ok, detail, fatal=False))
    if settings:
        hook_ok, hook_detail = find_router_hook(settings)
        rows.append(check("router_hook", hook_ok, hook_detail, fatal=False))
        if hook_ok:
            uses_project_venv = ".claude/.venv/bin/python" in hook_detail
            rows.append(check("hook_python", uses_project_venv, hook_detail, fatal=False))

    try:
        profile = load_runtime_profile(cwd=str(PROJECT_DIR))
        rows.append(
            check(
                "active_profile",
                True,
                f"{profile['name']} ({profile.get('description', '')})",
                fatal=False,
            )
        )
    except Exception as exc:
        rows.append(check("active_profile", False, str(exc), fatal=False))

    try:
        import yaml  # type: ignore

        rows.append(check("current_python_pyyaml", True, f"yaml={yaml.__version__}"))
    except Exception as exc:  # pragma: no cover - stdlib fallback path
        rows.append(check("current_python_pyyaml", False, str(exc)))

    if VENV_PY.exists():
        probe = run([str(VENV_PY), "-c", "import yaml, sys; print(sys.executable); print(yaml.__version__)"])
        rows.append(
            check(
                "venv_pyyaml",
                probe.returncode == 0,
                probe.stdout.strip() if probe.returncode == 0 else probe.stderr.strip(),
            )
        )

        manifest_probe = run(
            [
                str(VENV_PY),
                "-c",
                (
                    "import json, sys; "
                    f"sys.path.insert(0, {str((CLAUDE_DIR / 'scripts')).__repr__()}); "
                    "from manifest import load_manifest; "
                    f"m=load_manifest(cwd={str(PROJECT_DIR).__repr__()}); "
                    "print(json.dumps({'format': m.get('_format'), 'skill_count': len(m.get('skills', {}))}))"
                ),
            ]
        )
        rows.append(
            check(
                "manifest_load",
                manifest_probe.returncode == 0,
                manifest_probe.stdout.strip() if manifest_probe.returncode == 0 else manifest_probe.stderr.strip(),
            )
        )

        validator_probe = run([str(VENV_PY), str(VALIDATOR), "--profile", "full", "--file", str(SCI_FIG), str(CLAUDE_DIR)])
        rows.append(
            check(
                "validator_legacy_full_runnable",
                validator_probe.returncode in (0, 1),
                (
                    f"exit={validator_probe.returncode}"
                    if validator_probe.returncode in (0, 1)
                    else validator_probe.stderr.strip()
                ),
            )
        )

        pillow_probe = run([str(VENV_PY), "-c", "from PIL import Image; print(Image.__version__)"])
        rows.append(
            check(
                "venv_pillow",
                pillow_probe.returncode == 0,
                pillow_probe.stdout.strip() if pillow_probe.returncode == 0 else pillow_probe.stderr.strip(),
            )
        )

        named_validator_probe = run([str(VENV_PY), str(VALIDATOR), "sci-fig", str(SCI_FIG_TARGET)])
        rows.append(
            check(
                "validator_named_runnable",
                named_validator_probe.returncode in (0, 1),
                (
                    f"exit={named_validator_probe.returncode}"
                    if named_validator_probe.returncode in (0, 1)
                    else named_validator_probe.stderr.strip()
                ),
            )
        )

        lint_probe = run([str(VENV_PY), str(LINT_MANIFEST), "--json", "--cwd", str(PROJECT_DIR)])
        lint_detail = lint_probe.stdout.strip() if lint_probe.stdout.strip() else lint_probe.stderr.strip()
        rows.append(
            check(
                "manifest_lint",
                lint_probe.returncode == 0,
                lint_detail or f"exit={lint_probe.returncode}",
            )
        )

    print("=== skill-facets doctor ===")
    failed = 0
    for row in rows:
        if row["ok"]:
            icon = "OK"
        elif row["fatal"]:
            icon = "FAIL"
            failed += 1
        else:
            icon = "WARN"
        print(f"[{icon}] {row['label']}: {row['detail']}")

    print()
    if failed:
        print(f"Doctor found {failed} issue(s).")
        return 1

    print("Doctor checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
