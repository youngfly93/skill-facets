#!/usr/bin/env python3
"""
约束验证器 CLI。
用法: python3 cli.py <command_or_skill_name> [target_dir]
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))

from parser import parse_constraints, find_source
from checkers import font_checker, color_checker, dpi_checker, content_checker

REGISTRY = {
    "font": font_checker.check,
    "font_size": font_checker.check,
    "color": color_checker.check,
    "dpi": dpi_checker.check,
    "numbering": content_checker.check,
    "no_markdown": content_checker.check,
    "no_gridlines": content_checker.check,
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


def validate(source_name, target_dir, source_file=None):
    sf = source_file or find_source(source_name)
    if not sf or not os.path.exists(sf):
        return {"error": f"找不到 {source_name} 的约束文件"}

    constraints = parse_constraints(sf)
    targets = collect_files(target_dir)
    results = []
    passed = failed = manual = 0

    for c in constraints:
        if c.checkable and c.check_type in REGISTRY:
            r = REGISTRY[c.check_type](c.check_type, c.check_params, targets)
            r["constraint"] = c.raw
            r["line"] = c.line_number
            results.append(r)
            if r["passed"] is True: passed += 1
            elif r["passed"] is False: failed += 1
            else: manual += 1
        else:
            results.append({"passed": None, "check_type": "manual",
                           "constraint": c.raw, "line": c.line_number,
                           "details": "需人工验证", "violations": []})
            manual += 1

    return {"source": sf, "target": target_dir,
            "total": len(constraints), "passed": passed,
            "failed": failed, "manual": manual, "results": results}


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
    sys.exit(1 if report.get("failed", 0) > 0 else 0)


if __name__ == "__main__":
    main()
