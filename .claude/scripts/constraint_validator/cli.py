#!/usr/bin/env python3
"""
约束验证器 CLI (vNext)。
双路径：优先从 skills.yaml contract 读取约束，回退到 parser.py 正则提取。
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

from parser import parse_constraints, find_source
from checkers import font_checker, color_checker, dpi_checker, content_checker, format_checker

try:
    from manifest import get_contract
    from logger import log_event
except ImportError:
    get_contract = lambda *a, **k: None
    log_event = lambda *a, **k: None

REGISTRY = {
    "font": font_checker.check,
    "font_size": font_checker.check,
    "color": color_checker.check,
    "dpi": dpi_checker.check,
    "numbering": content_checker.check,
    "no_markdown": content_checker.check,
    "no_gridlines": content_checker.check,
    "format": format_checker.check,
    # 从 skills.yaml checker 字段映射
    "font_checker": font_checker.check,
    "color_checker": color_checker.check,
    "dpi_checker": dpi_checker.check,
    "content_checker": content_checker.check,
    "format_checker": format_checker.check,
}


def collect_files(target_dir):
    exts = {'.docx', '.pptx', '.xlsx', '.png', '.jpg', '.jpeg', '.tiff', '.pdf'}
    files = []
    for root, _, names in os.walk(target_dir):
        for f in names:
            if f.startswith('._') or f.startswith('.'):
                continue
            if os.path.splitext(f)[1].lower() in exts:
                files.append(os.path.join(root, f))
    return files


def validate_from_contract(contract, targets):
    """新路径：从 skills.yaml contract 验证。"""
    constraints = contract.get("constraints", [])
    results = []
    hard_fail = soft_warn = manual_review = passed = 0

    for c in constraints:
        checker_name = c.get("checker", "")
        severity = c.get("severity", "manual_review")
        params = c.get("params", {})

        if checker_name and checker_name in REGISTRY:
            r = REGISTRY[checker_name](c.get("type", ""), params, targets)
        else:
            r = {"passed": None, "check_type": c.get("type", "manual"),
                 "details": "需人工验证", "violations": []}

        r["constraint_id"] = c.get("id", "")
        r["constraint"] = c.get("rule", "")
        r["severity"] = severity
        r["repair_hint"] = c.get("repair_hint", "")
        results.append(r)

        if r["passed"] is True:
            passed += 1
        elif r["passed"] is False:
            if severity == "hard_fail":
                hard_fail += 1
            else:
                soft_warn += 1
        else:
            manual_review += 1

    return {
        "total": len(constraints),
        "passed": passed,
        "hard_fail": hard_fail,
        "soft_warn": soft_warn,
        "manual_review": manual_review,
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
            r["constraint"] = c.raw
            r["constraint_id"] = ""
            r["severity"] = "hard_fail" if r["passed"] is False else "manual_review"
            r["repair_hint"] = ""
            results.append(r)
            if r["passed"] is True:
                passed += 1
            elif r["passed"] is False:
                hard_fail += 1
            else:
                manual_review += 1
        else:
            results.append({
                "passed": None, "check_type": "manual",
                "constraint": c.raw, "constraint_id": "",
                "severity": "manual_review", "repair_hint": "",
                "details": "需人工验证", "violations": [],
            })
            manual_review += 1

    return {
        "total": len(constraints),
        "passed": passed,
        "hard_fail": hard_fail,
        "soft_warn": 0,
        "manual_review": manual_review,
        "results": results,
    }


def validate(source_name, target_dir, source_file=None):
    t0 = time.time()
    targets = collect_files(target_dir)
    source_used = "unknown"

    # 新路径：尝试从 skills.yaml contract 读取
    if source_name and not source_file:
        contract = get_contract(source_name, os.getcwd())
        if contract and contract.get("constraints"):
            report = validate_from_contract(contract, targets)
            report["source"] = "skills.yaml"
            report["skill"] = source_name
            report["target"] = target_dir
            source_used = "skills.yaml"
            duration = int((time.time() - t0) * 1000)
            log_event({
                "type": "validate", "skill": source_name,
                "target_dir": target_dir, "source": source_used,
                "total": report["total"], "passed": report["passed"],
                "hard_fail": report["hard_fail"], "soft_warn": report["soft_warn"],
                "manual_review": report["manual_review"],
                "duration_ms": duration,
            })
            return report

    # 回退路径：从 .md 正则提取
    sf = source_file or find_source(source_name)
    if not sf or not os.path.exists(sf):
        return {"error": f"找不到 {source_name} 的约束文件"}

    report = validate_from_parser(sf, targets)
    report["source"] = sf
    report["skill"] = source_name
    report["target"] = target_dir
    source_used = "parser"

    duration = int((time.time() - t0) * 1000)
    log_event({
        "type": "validate", "skill": source_name,
        "target_dir": target_dir, "source": source_used,
        "total": report["total"], "passed": report["passed"],
        "hard_fail": report.get("hard_fail", 0),
        "soft_warn": report.get("soft_warn", 0),
        "manual_review": report.get("manual_review", 0),
        "duration_ms": duration,
    })
    return report


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 cli.py <name> [target_dir]")
        print("       python3 cli.py --file <source.md> [target_dir]")
        sys.exit(1)

    if sys.argv[1] == '--file':
        sf = sys.argv[2]
        td = sys.argv[3] if len(sys.argv) > 3 else os.getcwd()
        report = validate("", td, source_file=sf)
    else:
        name = sys.argv[1]
        td = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
        report = validate(name, td)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(1 if report.get("hard_fail", 0) > 0 else 0)


if __name__ == "__main__":
    main()
