#!/usr/bin/env python3
"""
UserPromptSubmit hook: 确定性 skill 路由辅助 (vNext)。
从 skills.yaml 加载 trigger 定义，匹配用户输入，输出推荐。
"""
import sys
import os
import json
import hashlib
import glob as glob_mod

# 设置 import 路径
_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_CLAUDE_DIR = os.path.dirname(_HOOK_DIR)
sys.path.insert(0, os.path.join(_CLAUDE_DIR, "scripts"))

from manifest import ManifestLoadError, get_all_triggers, load_manifest
from logger import log_event
from runtime_profile import RuntimeProfileError, load_runtime_profile


def match_skill(name, defn, prompt, cwd):
    prompt_lower = prompt.lower()

    for nk in defn.get('negative_keywords', []):
        if nk.lower() in prompt_lower:
            return None

    score = 0
    dims = []

    hits = [kw for kw in defn.get('keywords', []) if kw.lower() in prompt_lower]
    if hits:
        score += len(hits) * 10
        dims.append(f"keywords({len(hits)})")

    for fp in defn.get('file_patterns', []):
        check = os.path.join(cwd, fp.rstrip('/'))
        found = (os.path.isdir(check) if fp.endswith('/') else
                 bool(glob_mod.glob(os.path.join(cwd, fp))) if '*' in fp else
                 os.path.exists(check))
        if found:
            score += 5
            dims.append(f"file:{fp}")

    for req in defn.get('requires_files', []):
        if not os.path.exists(os.path.join(cwd, req)):
            score -= 15
            dims.append(f"missing:{req}")

    if not hits:
        return None
    if score <= 0:
        return None

    return {
        "name": name,
        "score": score,
        "priority": defn.get('priority', 50),
        "dims": dims,
        "hint": defn.get('hint', ''),
    }


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    prompt = data.get("prompt", "")
    if not prompt or len(prompt) < 3:
        return
    if prompt.strip().startswith('/'):
        return

    cwd = data.get("cwd", os.getcwd())
    try:
        profile = load_runtime_profile(cwd=cwd)
        allow_legacy = profile.get("allow_legacy_trigger_manifest", False)
        triggers = get_all_triggers(cwd=cwd, search_paths=[cwd], allow_legacy=allow_legacy)
        manifest_meta = load_manifest(cwd=cwd, search_paths=[cwd], allow_legacy=allow_legacy)
    except (ManifestLoadError, RuntimeProfileError) as exc:
        log_event({
            "type": "route_error",
            "cwd": cwd,
            "error": str(exc),
        })
        return

    if not triggers:
        return
    manifest_source = manifest_meta.get("_format", "unknown")

    matches = []
    for name, defn in triggers.items():
        r = match_skill(name, defn, prompt, cwd)
        if r:
            matches.append(r)

    if not matches:
        log_event({
            "type": "route",
            "prompt_len": len(prompt),
            "prompt_hash": hashlib.md5(prompt.encode()).hexdigest()[:8],
            "cwd": cwd,
            "matches": [],
            "top_pick": None,
            "manifest_source": manifest_source,
            "profile": profile["name"],
        })
        return

    matches.sort(key=lambda m: (-m["score"], m["priority"]))
    top = matches[:2]

    log_event({
        "type": "route",
        "prompt_len": len(prompt),
        "prompt_hash": hashlib.md5(prompt.encode()).hexdigest()[:8],
        "cwd": cwd,
        "matches": [{"name": m["name"], "score": m["score"], "dims": m["dims"]} for m in matches],
        "top_pick": top[0]["name"],
        "manifest_source": manifest_source,
        "profile": profile["name"],
    })

    lines = ["[skill-router] Matched skills:"]
    for m in top:
        lines.append(f"  - {m['hint']}  [{', '.join(m['dims'])}]")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
