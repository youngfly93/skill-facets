#!/usr/bin/env python3
"""
Export vNext skill assets into distributable bundles.

Outputs:
1. Claude runtime bundle:      <out>/.claude/{commands,skills,mcp}
2. Anthropic skills bundle:    <out>/anthropic_skills/skills/<skill>/
3. Export manifest:            <out>/export_manifest.json

Design:
- Author-owned commands/skills are compiled from skills.yaml.
- Tool Facet assets are copied for local skills so generated SKILL.md stays runnable.
- Wrapped proxy skills are excluded by default to avoid shadowing richer external skills.
- MCP servers are generated only for skills with tools definitions.
"""
import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

from manifest import load_manifest, ManifestLoadError
from mcp_bridge import generate_mcp_server, get_tools_skills
from skill_compile import (
    compile_command_md,
    compile_skill_md,
    get_output_path,
    _is_wrapped_proxy_skill,
)


def _copytree_filtered(src: Path, dst: Path):
    def _ignore(_dir, names):
        ignored = []
        for name in names:
            if name == "__pycache__" or name.endswith(".pyc") or name.startswith("._"):
                ignored.append(name)
        return ignored

    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=_ignore)


def _write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _export_claude_bundle(out_root: Path, project_root: Path, skills: dict, include_wrapped_proxies: bool) -> dict:
    bundle_root = out_root / ".claude"
    compiled_commands = 0
    compiled_skills = 0
    skipped_wrapped = []

    for name, defn in skills.items():
        if not defn.get("contract"):
            continue

        if _is_wrapped_proxy_skill(defn) and not include_wrapped_proxies:
            skipped_wrapped.append(name)
            continue

        skill_type = defn.get("type", "command")
        content = compile_command_md(name, defn) if skill_type == "command" else compile_skill_md(name, defn)
        out_path = Path(get_output_path(name, defn, str(bundle_root), str(bundle_root)))
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if skill_type == "skill":
            source = defn.get("source")
            if source:
                src_dir = project_root / ".claude" / Path(source).parent
                if src_dir.exists():
                    _copytree_filtered(src_dir, out_path.parent)
            compiled_skills += 1
        else:
            compiled_commands += 1

        _write_text(out_path, content)

    tools_skills = get_tools_skills({"skills": skills})
    generated_mcp = []
    mcp_dir = bundle_root / "mcp"
    for name, defn in tools_skills.items():
        if _is_wrapped_proxy_skill(defn) and not include_wrapped_proxies:
            continue
        code = generate_mcp_server(name, defn, str(bundle_root))
        server_path = mcp_dir / f"{name}_server.py"
        _write_text(server_path, code)
        generated_mcp.append(name)

    return {
        "bundle_root": str(bundle_root),
        "compiled_commands": compiled_commands,
        "compiled_skills": compiled_skills,
        "generated_mcp": generated_mcp,
        "skipped_wrapped": skipped_wrapped,
    }


def _export_anthropic_skills(out_root: Path, project_root: Path, skills: dict, include_wrapped_proxies: bool) -> dict:
    bundle_root = out_root / "anthropic_skills" / "skills"
    exported = []
    skipped_wrapped = []

    for name, defn in skills.items():
        if defn.get("type", "command") != "skill":
            continue
        if not defn.get("contract"):
            continue
        if _is_wrapped_proxy_skill(defn) and not include_wrapped_proxies:
            skipped_wrapped.append(name)
            continue

        skill_dir = bundle_root / name
        source = defn.get("source")
        if source:
            src_dir = project_root / ".claude" / Path(source).parent
            if src_dir.exists():
                _copytree_filtered(src_dir, skill_dir)

        _write_text(skill_dir / "SKILL.md", compile_skill_md(name, defn))
        exported.append(name)

    return {
        "bundle_root": str(bundle_root),
        "exported_skills": exported,
        "skipped_wrapped": skipped_wrapped,
    }


def _write_manifest(out_root: Path, project_root: Path, include_wrapped_proxies: bool, claude_info: dict, anthropic_info: dict):
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root),
        "include_wrapped_proxies": include_wrapped_proxies,
        "claude_bundle": claude_info,
        "anthropic_bundle": anthropic_info,
    }
    _write_text(out_root / "export_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))


def _write_readme(out_root: Path):
    text = """# Export Bundle

This directory was generated from `skills.yaml`.

Contents:
- `.claude/`: project-local Claude runtime bundle
- `anthropic_skills/skills/`: Anthropic Skills-compatible skill directories
- `export_manifest.json`: export metadata

Notes:
- Wrapped proxy skills are excluded by default unless export was run with `--include-wrapped-proxies`.
- MCP servers live under `.claude/mcp/` so their relative skill paths remain valid.
"""
    _write_text(out_root / "README.md", text)


def main():
    parser = argparse.ArgumentParser(description="Export compiled skill bundles from skills.yaml")
    parser.add_argument("--cwd", default=".", help="project root")
    parser.add_argument("--out-dir", required=True, help="output directory for exported bundles")
    parser.add_argument(
        "--include-wrapped-proxies",
        action="store_true",
        help="also export thin local proxies for skills declared via wraps:",
    )
    args = parser.parse_args()

    try:
        manifest = load_manifest(cwd=args.cwd, search_paths=[args.cwd])
    except ManifestLoadError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    project_root = Path(args.cwd).resolve()
    out_root = Path(args.out_dir).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    skills = manifest.get("skills", {})
    claude_info = _export_claude_bundle(out_root, project_root, skills, args.include_wrapped_proxies)
    anthropic_info = _export_anthropic_skills(out_root, project_root, skills, args.include_wrapped_proxies)
    _write_manifest(out_root, project_root, args.include_wrapped_proxies, claude_info, anthropic_info)
    _write_readme(out_root)

    print(json.dumps({
        "out_dir": str(out_root),
        "claude_bundle": {
            "compiled_commands": claude_info["compiled_commands"],
            "compiled_skills": claude_info["compiled_skills"],
            "generated_mcp_count": len(claude_info["generated_mcp"]),
            "skipped_wrapped_count": len(claude_info["skipped_wrapped"]),
        },
        "anthropic_bundle": {
            "exported_skill_count": len(anthropic_info["exported_skills"]),
            "skipped_wrapped_count": len(anthropic_info["skipped_wrapped"]),
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
