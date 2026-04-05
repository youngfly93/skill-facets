#!/usr/bin/env python3
"""
约束验证器 CLI (vNext)。
命名 skill 时强制走 skills.yaml contract；只有 `--file` 才走 parser.py legacy 路径。
用法: python3 cli.py <name> [target_dir]
      python3 cli.py --file <source.md> [target_dir]
"""
import sys
import os
import json
import time

_CLI_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _CLI_DIR)
sys.path.insert(0, os.path.join(os.path.dirname(_CLI_DIR)))  # scripts/

from parser import parse_constraints
from checkers import (
    font_checker,
    color_checker,
    dpi_checker,
    content_checker,
    format_checker,
    figure_checker,
    layout_checker,
    ppt_checker,
)

try:
    from manifest import ManifestLoadError, find_manifest_path, get_contract
    from logger import log_event
    from runtime_profile import RuntimeProfileError, load_runtime_profile
except ImportError:
    ManifestLoadError = RuntimeError
    RuntimeProfileError = RuntimeError
    find_manifest_path = lambda *a, **k: (None, None)
    get_contract = lambda *a, **k: None
    log_event = lambda *a, **k: None
    load_runtime_profile = lambda *a, **k: {
        "name": "core",
        "description": "fallback profile",
        "allow_legacy_parser": False,
        "include_stabilities": ["core"],
        "include_enforcements": ["machine"],
        "include_runtime_enforced": True,
    }

REGISTRY = {
    "font": font_checker.check,
    "font_size": font_checker.check,
    "color": color_checker.check,
    "dpi": dpi_checker.check,
    "numbering": content_checker.check,
    "no_markdown": content_checker.check,
    "no_gridlines": content_checker.check,
    "format": format_checker.check,
    "axis_labels": figure_checker.check,
    "legend_present": figure_checker.check,
    "line_spacing": layout_checker.check,
    "margins": layout_checker.check,
    "heading_levels": layout_checker.check,
    "image_aspect_ratio": ppt_checker.check,
    "pure_bullet_page": ppt_checker.check,
    "slide_structure": ppt_checker.check,
    # 从 skills.yaml checker 字段映射
    "font_checker": font_checker.check,
    "color_checker": color_checker.check,
    "dpi_checker": dpi_checker.check,
    "content_checker": content_checker.check,
    "format_checker": format_checker.check,
    "figure_checker": figure_checker.check,
    "layout_checker": layout_checker.check,
    "ppt_checker": ppt_checker.check,
}


def _normalize_constraint(constraint):
    severity = constraint.get("severity", "manual_review")
    checker_name = constraint.get("checker", "")
    enforcement = constraint.get("enforcement")
    enforced_by = constraint.get("enforced_by")
    stability = constraint.get("stability")

    if not enforcement:
        if checker_name:
            enforcement = "machine"
        elif severity == "soft_warn":
            enforcement = "human"
        else:
            enforcement = "human"

    if not enforced_by:
        if checker_name:
            enforced_by = "checker"
        elif enforcement == "machine":
            enforced_by = "runtime"
        else:
            enforced_by = "human"

    if not stability:
        stability = "experimental" if enforcement in ("heuristic", "human") else "core"

    return {
        **constraint,
        "severity": severity,
        "checker": checker_name,
        "enforcement": enforcement,
        "enforced_by": enforced_by,
        "stability": stability,
    }


def _review_result(constraint, details, outcome):
    return {
        "passed": None,
        "check_type": constraint.get("type", "manual"),
        "details": details,
        "violations": [],
        "outcome": outcome,
        "evidence": {"details": details, "violation_count": 0},
    }


def _is_constraint_enabled(constraint, profile):
    stability = constraint.get("stability", "core")
    if stability not in set(profile.get("include_stabilities", ["core"])):
        return False
    enforced_by = constraint.get("enforced_by", "human")
    enforcement = constraint.get("enforcement", "human")
    if enforced_by == "runtime":
        return profile.get("include_runtime_enforced", True)
    return enforcement in set(profile.get("include_enforcements", []))


def _skip_reason(constraint, profile):
    stability = constraint.get("stability", "core")
    if stability not in set(profile.get("include_stabilities", ["core"])):
        return f"profile={profile['name']} 不包含 stability={stability}"
    enforced_by = constraint.get("enforced_by", "human")
    enforcement = constraint.get("enforcement", "human")
    if enforced_by == "runtime":
        return f"profile={profile['name']} 禁用了 runtime_enforced"
    return f"profile={profile['name']} 不包含 enforcement={enforcement}"


def _finalize_result(result, constraint):
    result["constraint_id"] = constraint.get("id", "")
    result["constraint"] = constraint.get("rule", "")
    result["severity"] = constraint.get("severity", "manual_review")
    result["repair_hint"] = constraint.get("repair_hint", "")
    result["enforcement"] = constraint.get("enforcement", "human")
    result["enforced_by"] = constraint.get("enforced_by", "human")
    result["stability"] = constraint.get("stability", "core")
    result.setdefault("outcome", "pass" if result.get("passed") is True else "fail" if result.get("passed") is False else "review")
    result.setdefault(
        "evidence",
        {
            "details": result.get("details", ""),
            "violation_count": len(result.get("violations", [])),
        },
    )
    return result


def collect_files(target_dir):
    exts = {'.docx', '.pptx', '.xlsx', '.png', '.jpg', '.jpeg', '.tiff', '.pdf'}
    if os.path.isfile(target_dir):
        base = os.path.basename(target_dir)
        ext = os.path.splitext(base)[1].lower()
        if not base.startswith(('._', '.')) and ext in exts:
            return [target_dir]
        return []
    files = []
    for root, _, names in os.walk(target_dir):
        for f in names:
            if f.startswith('._') or f.startswith('.'):
                continue
            if os.path.splitext(f)[1].lower() in exts:
                files.append(os.path.join(root, f))
    return files


def _build_search_paths(target_dir=None, source_file=None):
    """为 manifest 搜索提供多个锚点，避免依赖单一 cwd。"""
    paths = []
    if target_dir:
        paths.append(target_dir)
    if source_file:
        paths.append(source_file)
    paths.append(os.getcwd())
    env_project = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_project:
        paths.append(env_project)
    return paths


def validate_from_contract(contract, targets, profile):
    """新路径：从 skills.yaml contract 验证。"""
    constraints = contract.get("constraints", [])
    results = []
    skipped_constraints = []
    hard_fail = soft_warn = manual_review = passed = 0
    runtime_enforced = heuristic_review = human_review = 0

    for raw in constraints:
        c = _normalize_constraint(raw)
        if not _is_constraint_enabled(c, profile):
            skipped_constraints.append(
                {
                    "constraint_id": c.get("id", ""),
                    "constraint": c.get("rule", ""),
                    "stability": c.get("stability", "core"),
                    "enforcement": c.get("enforcement", "human"),
                    "reason": _skip_reason(c, profile),
                }
            )
            continue
        checker_name = c.get("checker", "")
        severity = c.get("severity", "manual_review")
        params = c.get("params", {})
        enforcement = c.get("enforcement", "human")
        enforced_by = c.get("enforced_by", "human")
        logical_check_type = c.get("check_type", c.get("type", ""))

        if checker_name and checker_name in REGISTRY:
            r = REGISTRY[checker_name](logical_check_type, params, targets)
            r["outcome"] = "pass" if r["passed"] is True else "fail" if r["passed"] is False else "review"
        elif enforced_by == "runtime":
            r = _review_result(c, "由 runtime 强执行；validate CLI 不重放执行期 gate", "runtime_enforced")
        else:
            details = "需启发式审查" if enforcement == "heuristic" else "需人工验证"
            outcome = "heuristic_review" if enforcement == "heuristic" else "human_review"
            r = _review_result(c, details, outcome)

        r = _finalize_result(r, c)
        results.append(r)

        if r["passed"] is True:
            passed += 1
        elif r["passed"] is False:
            if severity == "hard_fail":
                hard_fail += 1
            else:
                soft_warn += 1
        else:
            if r["outcome"] == "runtime_enforced":
                runtime_enforced += 1
            else:
                manual_review += 1
                if enforcement == "heuristic":
                    heuristic_review += 1
                else:
                    human_review += 1

    return {
        "available_total": len(constraints),
        "total": len(results),
        "skipped": len(skipped_constraints),
        "passed": passed,
        "hard_fail": hard_fail,
        "soft_warn": soft_warn,
        "manual_review": manual_review,
        "runtime_enforced": runtime_enforced,
        "heuristic_review": heuristic_review,
        "human_review": human_review,
        "profile": profile["name"],
        "profile_description": profile.get("description", ""),
        "skipped_constraints": skipped_constraints,
        "results": results,
    }


def validate_from_parser(source_file, targets):
    """回退路径：从 .md 正则提取验证。"""
    constraints = parse_constraints(source_file)
    results = []
    passed = hard_fail = manual_review = 0

    for c in constraints:
        if c.checkable and c.check_type in REGISTRY:
            r = REGISTRY[c.check_type](c.check_type, c.check_params, targets)
            parser_enforcement = "machine" if r.get("passed") in (True, False) else "human"
            parser_enforced_by = "checker" if parser_enforcement == "machine" else "human"
            r = _finalize_result(
                r,
                {
                    "id": "",
                    "rule": c.raw,
                    "severity": "hard_fail" if r["passed"] is False else "manual_review",
                    "repair_hint": "",
                    "enforcement": parser_enforcement,
                    "enforced_by": parser_enforced_by,
                },
            )
            results.append(r)
            if r["passed"] is True:
                passed += 1
            elif r["passed"] is False:
                hard_fail += 1
            else:
                manual_review += 1
        else:
            results.append(
                _finalize_result(
                    _review_result({}, "需人工验证", "human_review"),
                    {
                        "id": "",
                        "rule": c.raw,
                        "severity": "manual_review",
                        "repair_hint": "",
                        "enforcement": "human",
                        "enforced_by": "human",
                    },
                )
            )
            manual_review += 1

    return {
        "available_total": len(constraints),
        "total": len(constraints),
        "skipped": 0,
        "passed": passed,
        "hard_fail": hard_fail,
        "soft_warn": 0,
        "manual_review": manual_review,
        "runtime_enforced": 0,
        "heuristic_review": 0,
        "human_review": manual_review,
        "results": results,
    }


def validate(source_name, target_dir, source_file=None, profile_name=None):
    t0 = time.time()
    targets = collect_files(target_dir)
    search_paths = _build_search_paths(target_dir=target_dir, source_file=source_file)
    try:
        profile = load_runtime_profile(cwd=os.getcwd(), override=profile_name)
    except RuntimeProfileError as exc:
        return {"error": str(exc), "skill": source_name, "target": target_dir}

    # 显式 legacy 路径：只有 --file 才使用 parser
    if source_file:
        if not profile.get("allow_legacy_parser", False):
            return {
                "error": (
                    f"当前 runtime profile={profile['name']} 已禁用 legacy parser。"
                    "如需旧路径，请使用 `--profile full --file <source.md>`。"
                ),
                "skill": source_name,
                "target": target_dir,
                "profile": profile["name"],
            }
        sf = source_file
        if not os.path.exists(sf):
            return {"error": f"找不到约束文件: {source_file}"}

        report = validate_from_parser(sf, targets)
        report["profile"] = profile["name"]
        report["profile_description"] = profile.get("description", "")
        report["source"] = sf
        report["skill"] = source_name
        report["target"] = target_dir

        duration = int((time.time() - t0) * 1000)
        log_event({
            "type": "validate", "skill": source_name or "",
            "target_dir": target_dir, "source": "parser",
            "profile": profile["name"],
            "total": report["total"], "passed": report["passed"],
            "hard_fail": report.get("hard_fail", 0),
            "soft_warn": report.get("soft_warn", 0),
            "manual_review": report.get("manual_review", 0),
            "runtime_enforced": report.get("runtime_enforced", 0),
            "duration_ms": duration,
        })
        return report

    # 命名 skill：稳定走 manifest contract
    if not source_name:
        return {"error": "必须提供 skill 名，或使用 --file <source.md> 走 legacy parser"}

    try:
        manifest_path, manifest_fmt = find_manifest_path(cwd=os.getcwd(), search_paths=search_paths)
    except ManifestLoadError as exc:
        return {"error": str(exc), "skill": source_name, "target": target_dir}

    if not manifest_path:
        return {
            "error": "未找到 .claude/skills.yaml 或 .claude/skill_triggers.yaml",
            "skill": source_name,
            "target": target_dir,
        }

    if manifest_fmt != "vnext":
        return {
            "error": (
                f"当前找到的是 legacy manifest: {manifest_path}。"
                "命名 skill 验证要求 vNext skills.yaml；如需旧路径，请显式使用 --file <source.md>。"
            ),
            "skill": source_name,
            "target": target_dir,
            "source": manifest_path,
        }

    try:
        contract = get_contract(source_name, cwd=os.getcwd(), search_paths=search_paths)
    except ManifestLoadError as exc:
        return {"error": str(exc), "skill": source_name, "target": target_dir, "source": manifest_path}

    if not contract or not contract.get("constraints"):
        return {
            "error": f"skills.yaml 中未找到 {source_name} 的 contract.constraints",
            "skill": source_name,
            "target": target_dir,
            "source": manifest_path,
        }

    report = validate_from_contract(contract, targets, profile)
    report["source"] = manifest_path
    report["skill"] = source_name
    report["target"] = target_dir

    duration = int((time.time() - t0) * 1000)
    log_event({
        "type": "validate", "skill": source_name,
        "target_dir": target_dir, "source": "skills.yaml",
        "profile": profile["name"],
        "total": report["total"], "passed": report["passed"],
        "hard_fail": report["hard_fail"], "soft_warn": report["soft_warn"],
        "manual_review": report["manual_review"],
        "runtime_enforced": report.get("runtime_enforced", 0),
        "duration_ms": duration,
    })
    return report


def _parse_args(argv):
    profile = None
    source_file = None
    positional = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--profile":
            if i + 1 >= len(argv):
                raise SystemExit("missing value for --profile")
            profile = argv[i + 1]
            i += 2
            continue
        if arg == "--file":
            if i + 1 >= len(argv):
                raise SystemExit("missing value for --file")
            source_file = argv[i + 1]
            i += 2
            continue
        positional.append(arg)
        i += 1
    return profile, source_file, positional


def main():
    argv = sys.argv[1:]
    if not argv:
        print("Usage: python3 cli.py [--profile core|full] <name> [target_dir]")
        print("       python3 cli.py --profile full --file <source.md> [target_dir]")
        sys.exit(1)

    profile, source_file, positional = _parse_args(argv)

    if source_file:
        td = positional[0] if positional else os.getcwd()
        report = validate("", td, source_file=source_file, profile_name=profile)
    else:
        if not positional:
            print("Usage: python3 cli.py [--profile core|full] <name> [target_dir]")
            sys.exit(1)
        name = positional[0]
        td = positional[1] if len(positional) > 1 else os.getcwd()
        report = validate(name, td, profile_name=profile)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get("error"):
        sys.exit(2)
    sys.exit(1 if report.get("hard_fail", 0) > 0 else 0)


if __name__ == "__main__":
    main()
