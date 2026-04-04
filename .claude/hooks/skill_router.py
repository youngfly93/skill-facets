#!/usr/bin/env python3
"""
UserPromptSubmit hook: 确定性 skill 路由辅助。
读取 skill_triggers.yaml，匹配用户输入，输出推荐注入模型上下文。
"""
import sys
import os
import json
import re
import glob as glob_mod

# 优先读项目级 manifest，回退到全局
_PROJECT_MANIFEST = os.path.join(os.getcwd(), ".claude", "skill_triggers.yaml")
_GLOBAL_MANIFEST = os.path.expanduser("~/.claude/skill_triggers.yaml")
MANIFEST_PATH = _PROJECT_MANIFEST if os.path.exists(_PROJECT_MANIFEST) else _GLOBAL_MANIFEST


def load_manifest(path):
    """加载 YAML，尝试 PyYAML 后回退到简易解析。"""
    try:
        import yaml
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except ImportError:
        return _parse_yaml_simple(path)


def _parse_yaml_simple(path):
    """极简 YAML 解析，仅支持本项目结构。"""
    result = {"skills": {}}
    current = None
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            s = line.rstrip()
            if not s or s.lstrip().startswith('#'):
                continue
            indent = len(line) - len(line.lstrip())
            content = s.strip()

            if indent == 2 and content.endswith(':') and not content.startswith('-'):
                name = content[:-1].strip()
                if name != 'skills':
                    current = name
                    result["skills"][current] = {}
                continue

            if current and indent == 4 and ':' in content and not content.startswith('-'):
                key, _, val = content.partition(':')
                key, val = key.strip(), val.strip()
                if val.startswith('[') and val.endswith(']'):
                    items = [x.strip().strip('"').strip("'")
                             for x in val[1:-1].split(',') if x.strip()]
                    result["skills"][current][key] = items
                elif val.startswith('"') or val.startswith("'"):
                    result["skills"][current][key] = val.strip('"').strip("'")
                elif val.isdigit():
                    result["skills"][current][key] = int(val)
                elif val:
                    result["skills"][current][key] = val
    return result


def match_skill(name, defn, prompt, cwd):
    """多维匹配，返回 (score, result) 或 None。"""
    prompt_lower = prompt.lower()

    # 负向排除
    for nk in defn.get('negative_keywords', []):
        if nk.lower() in prompt_lower:
            return None

    score = 0
    dims = []

    # 关键词匹配
    hits = [kw for kw in defn.get('keywords', []) if kw.lower() in prompt_lower]
    if hits:
        score += len(hits) * 10
        dims.append(f"keywords({len(hits)})")

    # 文件模式
    for fp in defn.get('file_patterns', []):
        check = os.path.join(cwd, fp.rstrip('/'))
        found = (os.path.isdir(check) if fp.endswith('/') else
                 bool(glob_mod.glob(os.path.join(cwd, fp))) if '*' in fp else
                 os.path.exists(check))
        if found:
            score += 5
            dims.append(f"file:{fp}")

    # 必需文件（缺失时降分而非排除）
    for req in defn.get('requires_files', []):
        if not os.path.exists(os.path.join(cwd, req)):
            score -= 15
            dims.append(f"missing:{req}")

    # 必须有至少一个关键词命中才推荐（纯文件匹配不够）
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

    # 如果用户已经用了 / 命令，不再推荐
    if prompt.strip().startswith('/'):
        return

    if not os.path.exists(MANIFEST_PATH):
        return

    manifest = load_manifest(MANIFEST_PATH)
    cwd = data.get("cwd", os.getcwd())

    matches = []
    for name, defn in manifest.get("skills", {}).items():
        r = match_skill(name, defn, prompt, cwd)
        if r:
            matches.append(r)

    if not matches:
        return

    matches.sort(key=lambda m: (-m["score"], m["priority"]))
    top = matches[:2]

    lines = ["[skill-router] 可能相关的 skill:"]
    for m in top:
        lines.append(f"  - {m['hint']}  [{', '.join(m['dims'])}]")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
