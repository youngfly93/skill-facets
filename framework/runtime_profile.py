#!/usr/bin/env python3
"""Load the runtime profile that separates vNext core from experimental extensions."""

from __future__ import annotations

import os


class RuntimeProfileError(RuntimeError):
    """Raised when runtime profile configuration is invalid or unreadable."""


_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_CLAUDE_DIR = os.path.dirname(_SCRIPT_DIR)

_DEFAULT_DATA = {
    "schema_version": "1.0",
    "active_profile": "core",
    "profiles": {
        "core": {
            "description": "默认稳定配置：manifest + runner + machine/runtime 约束",
            "allow_legacy_parser": False,
            "allow_legacy_trigger_manifest": False,
            "include_stabilities": ["core"],
            "include_enforcements": ["machine"],
            "include_runtime_enforced": True,
        },
        "full": {
            "description": "实验配置：在 core 之上启用 heuristic/human review 与 legacy parser",
            "allow_legacy_parser": True,
            "allow_legacy_trigger_manifest": True,
            "include_stabilities": ["core", "experimental"],
            "include_enforcements": ["machine", "heuristic", "human"],
            "include_runtime_enforced": True,
        },
    },
}


def _walk_parent_dirs(start):
    if not start:
        return
    cur = os.path.abspath(start)
    if os.path.isfile(cur):
        cur = os.path.dirname(cur)
    while True:
        yield cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent


def find_runtime_profile_path(cwd=None):
    seen = set()
    starts = []

    env_project = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_project:
        starts.append(env_project)
    if cwd:
        starts.append(cwd)
    starts.append(_CLAUDE_DIR)

    for start in starts:
        for parent in _walk_parent_dirs(start):
            candidate = parent if os.path.basename(parent) == ".claude" else os.path.join(parent, ".claude")
            if candidate in seen:
                continue
            seen.add(candidate)
            profile_path = os.path.join(candidate, "runtime_profile.yaml")
            if os.path.exists(profile_path):
                return profile_path
    return None


def _load_yaml(path):
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeProfileError(
            "读取 .claude/runtime_profile.yaml 需要 PyYAML。请先运行 `bash .claude/bootstrap_env.sh`。"
        ) from exc

    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise RuntimeProfileError(f"runtime_profile.yaml 格式错误: {path}")
    return data


def load_runtime_profile(cwd=None, override=None):
    path = find_runtime_profile_path(cwd=cwd)
    data = dict(_DEFAULT_DATA)
    data["profiles"] = {name: dict(cfg) for name, cfg in _DEFAULT_DATA["profiles"].items()}

    if path:
        loaded = _load_yaml(path)
        data.update({k: v for k, v in loaded.items() if k != "profiles"})
        for name, cfg in loaded.get("profiles", {}).items():
            base = dict(data["profiles"].get(name, {}))
            base.update(cfg or {})
            data["profiles"][name] = base

    profile_name = override or os.environ.get("SKILL_FACETS_PROFILE") or data.get("active_profile", "core")
    profiles = data.get("profiles", {})
    if profile_name not in profiles:
        raise RuntimeProfileError(f"未知 runtime profile: {profile_name}")

    profile = dict(profiles[profile_name])
    profile["name"] = profile_name
    profile["path"] = path or os.path.join(_CLAUDE_DIR, "runtime_profile.yaml")
    profile["schema_version"] = data.get("schema_version", "1.0")
    profile["include_stabilities"] = list(profile.get("include_stabilities", ["core"]))
    profile["include_enforcements"] = list(profile.get("include_enforcements", ["machine"]))
    profile["include_runtime_enforced"] = bool(profile.get("include_runtime_enforced", True))
    profile["allow_legacy_parser"] = bool(profile.get("allow_legacy_parser", False))
    profile["allow_legacy_trigger_manifest"] = bool(profile.get("allow_legacy_trigger_manifest", False))
    return profile
