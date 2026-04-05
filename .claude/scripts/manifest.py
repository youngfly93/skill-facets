#!/usr/bin/env python3
"""
skills.yaml 加载模块 — trigger/contract/tools/workflow 的统一读取层。
被 skill_router.py 和 constraint_validator/cli.py 共同导入。

说明:
- 优先读取 vNext `skills.yaml`
- legacy `skill_triggers.yaml` 仅作为显式兼容路径，可由 runtime profile 禁用
- manifest 搜索会从传入路径向上遍历父目录，而不是只依赖当前工作目录
- 不再使用不可靠的手写 YAML fallback；需要 PyYAML 明确可用
"""
import os


class ManifestLoadError(RuntimeError):
    """Manifest 无法可靠读取时抛出。"""

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_CLAUDE_DIR = os.path.dirname(_SCRIPT_DIR)


def _walk_parent_dirs(start):
    """从起点一路向上遍历目录。start 可为文件或目录。"""
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


def _iter_candidate_claude_dirs(cwd=None, search_paths=None):
    """按优先级生成候选 .claude 目录。"""
    seen = set()
    starts = []

    env_project = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_project:
        starts.append(env_project)

    if search_paths:
        starts.extend(p for p in search_paths if p)

    if cwd:
        starts.append(cwd)

    # 最后回退到脚本所在项目的 .claude
    starts.append(_CLAUDE_DIR)

    for start in starts:
        for parent in _walk_parent_dirs(start):
            if os.path.basename(parent) == ".claude":
                candidate = parent
            else:
                candidate = os.path.join(parent, ".claude")
            if candidate not in seen:
                seen.add(candidate)
                yield candidate


def find_manifest_path(cwd=None, search_paths=None, allow_legacy=True):
    """查找 manifest 文件，返回 (path, format)。"""
    for base in _iter_candidate_claude_dirs(cwd=cwd, search_paths=search_paths):
        vnext = os.path.join(base, "skills.yaml")
        if os.path.exists(vnext):
            return vnext, "vnext"
        v4 = os.path.join(base, "skill_triggers.yaml")
        if allow_legacy and os.path.exists(v4):
            return v4, "v4"
    return None, None


def _load_yaml(path):
    """加载 YAML。显式要求 PyYAML，避免伪 fallback 误解析。"""
    try:
        import yaml
    except ImportError as exc:
        raise ManifestLoadError(
            "读取 .claude/skills.yaml 需要 PyYAML。请先安装 `pip install PyYAML`，"
            "或显式使用 `cli.py --file <source.md>` 走 legacy parser 路径。"
        ) from exc

    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ManifestLoadError(f"Manifest 格式错误：{path}")
    return data


# === 公开 API ===

_cache = {}


def load_manifest(cwd=None, search_paths=None, allow_legacy=True):
    """加载 manifest，返回完整 dict。带缓存。"""
    path, fmt = find_manifest_path(cwd=cwd, search_paths=search_paths, allow_legacy=allow_legacy)
    if not path:
        return {"skills": {}}
    cache_key = (path, allow_legacy)
    if cache_key in _cache:
        return _cache[cache_key]
    data = _load_yaml(path)
    data["_source"] = path
    data["_format"] = fmt
    _cache[cache_key] = data
    return data


def get_skill(name, cwd=None, search_paths=None, allow_legacy=True):
    """获取单个 skill 定义。"""
    m = load_manifest(cwd=cwd, search_paths=search_paths, allow_legacy=allow_legacy)
    return m.get("skills", {}).get(name)


def get_contract(name, cwd=None, search_paths=None, allow_legacy=True):
    """获取 skill 的 contract。无 contract 返回 None。"""
    skill = get_skill(name, cwd=cwd, search_paths=search_paths, allow_legacy=allow_legacy)
    if skill:
        return skill.get("contract")
    return None


def get_trigger(name, cwd=None, search_paths=None, allow_legacy=True):
    """获取 skill 的 trigger。"""
    skill = get_skill(name, cwd=cwd, search_paths=search_paths, allow_legacy=allow_legacy)
    if skill:
        return skill.get("trigger")
    return None


def get_all_triggers(cwd=None, search_paths=None, allow_legacy=True):
    """获取所有 skill 的 trigger，返回 {name: trigger_dict}。
    兼容 vNext（trigger 子对象）和 V4（keywords 在顶层）两种格式。"""
    m = load_manifest(cwd=cwd, search_paths=search_paths, allow_legacy=allow_legacy)
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
