#!/usr/bin/env python3
"""检查文件扩展名是否在允许列表中。"""
import os


def check(check_type, params, files):
    allowed = [x.lower() for x in params.get("allowed", [])]
    if not allowed:
        return {"passed": None, "check_type": check_type,
                "details": "无允许格式列表", "violations": []}

    violations = []
    checked = 0
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext:
            checked += 1
            if ext not in allowed:
                violations.append({"file": f, "issue": f"格式 {ext} 不在 {allowed} 中"})

    return {"passed": len(violations) == 0 if checked > 0 else None,
            "check_type": check_type,
            "details": f"允许: {allowed}, 检查 {checked} 个文件",
            "violations": violations}
