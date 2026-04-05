#!/usr/bin/env python3
"""OOXML layout and structure checks for DOCX reports."""

from __future__ import annotations

import os
import re
import zipfile


def check(check_type, params, files):
    dispatch = {
        "line_spacing": _line_spacing,
        "margins": _margins,
        "heading_levels": _heading_levels,
    }
    return dispatch.get(check_type, _noop)(params, files)


def _docx_files(files):
    return [f for f in files if f.endswith(".docx")]


def _read_xml(zf, name):
    try:
        return zf.read(name).decode("utf-8", errors="ignore")
    except KeyError:
        return ""


def _line_spacing(params, files):
    violations = []
    evidence = []
    target = int(round(float(params.get("spacing", 1.5)) * 240))
    tolerance = int(params.get("tolerance", 30))

    for f in _docx_files(files):
        try:
            with zipfile.ZipFile(f, "r") as zf:
                document_xml = _read_xml(zf, "word/document.xml")
                styles_xml = _read_xml(zf, "word/styles.xml")
            lines = [int(x) for x in re.findall(r'w:spacing[^>]*w:line="(\d+)"', document_xml + styles_xml)]
            evidence.append({"file": f, "spacing_values": lines[:20]})
            if not lines or not any(abs(x - target) <= tolerance for x in lines):
                violations.append({"file": f, "issue": f"未检测到接近 {target} twips 的 1.5 倍行距设置"})
        except Exception as exc:
            violations.append({"file": f, "issue": str(exc)})
    return {
        "passed": len(violations) == 0,
        "check_type": "line_spacing",
        "details": f"目标行距≈{target} twips",
        "violations": violations,
        "evidence": {"documents": evidence, "violation_count": len(violations)},
    }


def _margins(params, files):
    violations = []
    evidence = []
    expected = {
        "top": int(params.get("top_twips", 1440)),
        "bottom": int(params.get("bottom_twips", 1440)),
        "left": int(params.get("left_twips", 1800)),
        "right": int(params.get("right_twips", 1800)),
    }
    tolerance = int(params.get("tolerance", 40))

    for f in _docx_files(files):
        try:
            with zipfile.ZipFile(f, "r") as zf:
                document_xml = _read_xml(zf, "word/document.xml")
            match = re.search(
                r'w:pgMar[^>]*w:top="(\d+)"[^>]*w:right="(\d+)"[^>]*w:bottom="(\d+)"[^>]*w:left="(\d+)"',
                document_xml,
            )
            if not match:
                violations.append({"file": f, "issue": "未找到 w:pgMar 页面边距定义"})
                continue
            actual = {
                "top": int(match.group(1)),
                "right": int(match.group(2)),
                "bottom": int(match.group(3)),
                "left": int(match.group(4)),
            }
            evidence.append({"file": f, "margins": actual})
            bad = {k: {"expected": expected[k], "actual": actual[k]} for k in expected if abs(actual[k] - expected[k]) > tolerance}
            if bad:
                violations.append({"file": f, "issue": f"页边距不匹配: {bad}"})
        except Exception as exc:
            violations.append({"file": f, "issue": str(exc)})
    return {
        "passed": len(violations) == 0,
        "check_type": "margins",
        "details": "检查 page margin twips",
        "violations": violations,
        "evidence": {"documents": evidence, "violation_count": len(violations)},
    }


def _heading_levels(params, files):
    violations = []
    evidence = []
    expected = {
        "Heading1": {"fonts": {"SimHei", "黑体"}, "sizes": {32}},
        "Heading2": {"fonts": {"SimHei", "黑体"}, "sizes": {28}},
        "Heading3": {"fonts": {"SimHei", "黑体"}, "sizes": {24}},
    }

    for f in _docx_files(files):
        try:
            with zipfile.ZipFile(f, "r") as zf:
                styles_xml = _read_xml(zf, "word/styles.xml")
                document_xml = _read_xml(zf, "word/document.xml")
            used_levels = set(re.findall(r'w:pStyle[^>]*w:val="(Heading[123])"', document_xml))
            levels_to_check = sorted(used_levels) if used_levels else ["Heading1", "Heading2"]
            file_evidence = {}
            for level in levels_to_check:
                block_match = re.search(
                    rf'<w:style[^>]*w:styleId="{level}"[\s\S]*?</w:style>',
                    styles_xml,
                )
                if not block_match:
                    violations.append({"file": f, "issue": f"未找到 {level} 样式定义"})
                    continue
                block = block_match.group(0)
                fonts = set(re.findall(r'w:(?:ascii|eastAsia)="([^"]+)"', block))
                sizes = {int(x) for x in re.findall(r'w:sz[^>]*w:val="(\d+)"', block)}
                file_evidence[level] = {"fonts": sorted(fonts), "sizes": sorted(sizes)}
                if expected[level]["fonts"].isdisjoint(fonts) or expected[level]["sizes"].isdisjoint(sizes):
                    violations.append(
                        {
                            "file": f,
                            "issue": f"{level} 样式不符合预期: fonts={sorted(fonts)}, sizes={sorted(sizes)}",
                        }
                    )
            evidence.append({"file": f, "levels": file_evidence})
        except Exception as exc:
            violations.append({"file": f, "issue": str(exc)})
    return {
        "passed": len(violations) == 0,
        "check_type": "heading_levels",
        "details": "检查 Heading1/2/3 样式字体和字号",
        "violations": violations,
        "evidence": {"documents": evidence, "violation_count": len(violations)},
    }


def _noop(params, files):
    return {"passed": None, "check_type": "unknown", "details": "未知 layout check", "violations": []}
