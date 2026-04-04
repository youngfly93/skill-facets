#!/usr/bin/env python3
"""
skills.yaml 加载模块 — trigger/contract/tools/workflow 的统一读取层。
被 skill_router.py 和 constraint_validator/cli.py 共同导入。
优先读 skills.yaml（vNext），回退到 skill_triggers.yaml（V4 兼容）。
"""
import os

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_CLAUDE_DIR = os.path.dirname(_SCRIPT_DIR)


def _find_manifest(cwd=None):
    """查找 manifest 文件，返回 (path, format)。"""
    bases = [_CLAUDE_DIR]
    if cwd:
        bases.insert(0, os.path.join(cwd, ".claude"))

    for base in bases:
        vnext = os.path.join(base, "skills.yaml")
        if os.path.exists(vnext):
            return vnext, "vnext"
        v4 = os.path.join(base, "skill_triggers.yaml")
        if os.path.exists(v4):
            return v4, "v4"
    return None, None


def _load_yaml(path):
    """加载 YAML，PyYAML 优先，回退简易解析。"""
    try:
        import yaml
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except ImportError:
        return _parse_simple(path)


def _parse_simple(path):
    """简易 YAML 解析，支持三层嵌套和列表。"""
    result = {"skills": {}}
    stack = [result]
    keys = [None]
    prev_indent = -1

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            raw = line.rstrip()
            if not raw or raw.lstrip().startswith('#'):
                continue

            indent = len(raw) - len(raw.lstrip())
            content = raw.strip()

            # 列表项: "- xxx" 或 "- {key: val}"
            if content.startswith('- '):
                item_text = content[2:].strip()
                # dict 列表项: "- id: xxx"
                if ':' in item_text and not item_text.startswith('{'):
                    item = {}
                    # 解析同行的第一个 key:val
                    k, _, v = item_text.partition(':')
                    item[k.strip()] = _parse_val(v.strip())
                    # 后续行会被当作同级 dict 条目
                    parent = stack[-1]
                    if isinstance(parent, dict):
                        last_key = keys[-1]
                        if last_key and last_key in parent:
                            if not isinstance(parent[last_key], list):
                                parent[last_key] = []
                            parent[last_key].append(item)
                            stack.append(item)
                            keys.append(None)
                            prev_indent = indent
                    elif isinstance(parent, list):
                        parent.append(item)
                        stack.append(item)
                        keys.append(None)
                        prev_indent = indent
                elif item_text.startswith('{'):
                    # 内联 dict: {key: val, ...}
                    item = _parse_inline_dict(item_text)
                    parent = stack[-1]
                    if isinstance(parent, dict):
                        last_key = keys[-1]
                        if last_key and last_key in parent:
                            if not isinstance(parent[last_key], list):
                                parent[last_key] = []
                            parent[last_key].append(item)
                    elif isinstance(parent, list):
                        parent.append(item)
                else:
                    # 简单列表项: "- string"
                    val = item_text.strip('"').strip("'")
                    parent = stack[-1]
                    if isinstance(parent, dict):
                        last_key = keys[-1]
                        if last_key and last_key in parent:
                            if not isinstance(parent[last_key], list):
                                parent[last_key] = []
                            parent[last_key].append(val)
                    elif isinstance(parent, list):
                        parent.append(val)
                continue

            # key: value 行
            if ':' in content:
                # 缩进回退时弹栈
                while len(stack) > 1 and indent <= prev_indent:
                    stack.pop()
                    keys.pop()
                    prev_indent -= 2

                k, _, v = content.partition(':')
                k = k.strip()
                v = v.strip()

                current = stack[-1]
                if not isinstance(current, dict):
                    continue

                if v == '' or v == '>-':
                    # 新的 dict 或等待子内容
                    current[k] = {}
                    stack.append(current[k])
                    keys.append(k)
                    prev_indent = indent
                elif v.startswith('[') and v.endswith(']'):
                    current[k] = [s.strip().strip('"').strip("'")
                                  for s in v[1:-1].split(',') if s.strip()]
                    keys[-1] = k
                elif v.startswith('{') and v.endswith('}'):
                    current[k] = _parse_inline_dict(v)
                    keys[-1] = k
                else:
                    current[k] = _parse_val(v)
                    keys[-1] = k

    return result


def _parse_val(v):
    """解析单个值。"""
    if not v:
        return ""
    v = v.strip('"').strip("'")
    if v.isdigit():
        return int(v)
    try:
        return float(v)
    except ValueError:
        pass
    if v.lower() in ('true', 'false'):
        return v.lower() == 'true'
    return v


def _parse_inline_dict(s):
    """解析 {key: val, key: val}。"""
    s = s.strip('{}').strip()
    result = {}
    for part in s.split(','):
        if ':' in part:
            k, _, v = part.partition(':')
            result[k.strip()] = _parse_val(v.strip())
    return result


# === 公开 API ===

_cache = {}


def load_manifest(cwd=None):
    """加载 manifest，返回完整 dict。带缓存。"""
    path, fmt = _find_manifest(cwd)
    if not path:
        return {"skills": {}}
    if path in _cache:
        return _cache[path]
    data = _load_yaml(path)
    data["_source"] = path
    data["_format"] = fmt
    _cache[path] = data
    return data


def get_skill(name, cwd=None):
    """获取单个 skill 定义。"""
    m = load_manifest(cwd)
    return m.get("skills", {}).get(name)


def get_contract(name, cwd=None):
    """获取 skill 的 contract。无 contract 返回 None。"""
    skill = get_skill(name, cwd)
    if skill:
        return skill.get("contract")
    return None


def get_trigger(name, cwd=None):
    """获取 skill 的 trigger。"""
    skill = get_skill(name, cwd)
    if skill:
        return skill.get("trigger")
    return None


def get_all_triggers(cwd=None):
    """获取所有 skill 的 trigger，返回 {name: trigger_dict}。
    兼容 vNext（trigger 子对象）和 V4（keywords 在顶层）两种格式。"""
    m = load_manifest(cwd)
    fmt = m.get("_format", "vnext")
    result = {}
    for name, defn in m.get("skills", {}).items():
        if fmt == "vnext":
            t = defn.get("trigger")
            if t:
                result[name] = {**t, "type": defn.get("type", "command")}
        else:
            # V4 格式：keywords 等在顶层
            if defn.get("keywords"):
                result[name] = {**defn}
    return result
