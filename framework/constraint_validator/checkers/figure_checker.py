#!/usr/bin/env python3
"""Heuristic figure checks for rendered scientific figures."""

from __future__ import annotations

import os


def check(check_type, params, files):
    dispatch = {
        "axis_labels": _axis_labels,
        "legend_present": _legend_present,
        "no_gridlines": _no_gridlines,
    }
    return dispatch.get(check_type, _noop)(params, files)


def _image_files(files):
    return [f for f in files if os.path.splitext(f)[1].lower() in (".png", ".jpg", ".jpeg", ".tiff", ".tif")]


def _load_rgb(path):
    from PIL import Image

    return Image.open(path).convert("RGB")


def _pixel_stats(img, region):
    x0, y0, x1, y1 = region
    dark = 0
    nonwhite = 0
    colorful = 0
    total = max(1, (x1 - x0) * (y1 - y0))
    for x in range(x0, x1):
        for y in range(y0, y1):
            r, g, b = img.getpixel((x, y))
            avg = (r + g + b) / 3
            if avg < 210:
                dark += 1
            if avg < 245:
                nonwhite += 1
            if max(r, g, b) - min(r, g, b) > 25 and avg < 240:
                colorful += 1
    return {
        "dark_ratio": dark / total,
        "nonwhite_ratio": nonwhite / total,
        "colorful_ratio": colorful / total,
    }


def _axis_labels(params, files):
    violations = []
    evidence = []
    try:
        images = _image_files(files)
        for path in images:
            img = _load_rgb(path)
            w, h = img.size
            bottom = _pixel_stats(img, (int(w * 0.18), int(h * 0.82), int(w * 0.82), int(h * 0.98)))
            left = _pixel_stats(img, (0, int(h * 0.18), int(w * 0.18), int(h * 0.82)))
            evidence.append({"file": path, "bottom_dark_ratio": round(bottom["dark_ratio"], 4), "left_dark_ratio": round(left["dark_ratio"], 4)})
            if bottom["dark_ratio"] < 0.006 or left["dark_ratio"] < 0.006:
                violations.append(
                    {
                        "file": path,
                        "issue": f"轴标签区域文字密度过低: bottom={bottom['dark_ratio']:.4f}, left={left['dark_ratio']:.4f}",
                    }
                )
        return {
            "passed": len(violations) == 0,
            "check_type": "axis_labels",
            "details": "启发式检查底部与左侧轴标签区域是否存在明显文字",
            "violations": violations,
            "evidence": {"images": evidence, "violation_count": len(violations)},
        }
    except ImportError:
        return {"passed": None, "check_type": "axis_labels", "details": "Pillow 不可用", "violations": []}


def _legend_present(params, files):
    violations = []
    evidence = []
    try:
        images = _image_files(files)
        for path in images:
            img = _load_rgb(path)
            w, h = img.size
            regions = {
                "upper_right": (int(w * 0.62), int(h * 0.08), int(w * 0.98), int(h * 0.42)),
                "mid_right": (int(w * 0.62), int(h * 0.32), int(w * 0.98), int(h * 0.72)),
                "lower_right": (int(w * 0.62), int(h * 0.58), int(w * 0.98), int(h * 0.96)),
            }
            region_stats = {name: _pixel_stats(img, region) for name, region in regions.items()}
            evidence.append({"file": path, "regions": {k: {sk: round(sv, 4) for sk, sv in v.items()} for k, v in region_stats.items()}})
            found = False
            for stats in region_stats.values():
                if stats["dark_ratio"] > 0.01 and (stats["colorful_ratio"] > 0.002 or stats["nonwhite_ratio"] > 0.05):
                    found = True
                    break
            if not found:
                violations.append({"file": path, "issue": "未在右侧候选区域检测到明显 legend 结构"})
        return {
            "passed": len(violations) == 0,
            "check_type": "legend_present",
            "details": "启发式检查右侧区域是否存在图例文本/色块组合",
            "violations": violations,
            "evidence": {"images": evidence, "violation_count": len(violations)},
        }
    except ImportError:
        return {"passed": None, "check_type": "legend_present", "details": "Pillow 不可用", "violations": []}


def _no_gridlines(params, files):
    violations = []
    evidence = []
    try:
        images = _image_files(files)
        for path in images:
            img = _load_rgb(path)
            w, h = img.size
            x0, y0, x1, y1 = int(w * 0.2), int(h * 0.15), int(w * 0.82), int(h * 0.85)
            row_flags = []
            col_flags = []
            for y in range(y0, y1):
                hits = 0
                total = x1 - x0
                for x in range(x0, x1):
                    r, g, b = img.getpixel((x, y))
                    avg = (r + g + b) / 3
                    if 150 <= avg <= 240 and max(r, g, b) - min(r, g, b) < 18:
                        hits += 1
                row_flags.append(total and hits / total > 0.22)
            for x in range(x0, x1):
                hits = 0
                total = y1 - y0
                for y in range(y0, y1):
                    r, g, b = img.getpixel((x, y))
                    avg = (r + g + b) / 3
                    if 150 <= avg <= 240 and max(r, g, b) - min(r, g, b) < 18:
                        hits += 1
                col_flags.append(total and hits / total > 0.22)
            row_hits = sum(1 for flag in row_flags if flag)
            col_hits = sum(1 for flag in col_flags if flag)
            row_groups = _count_groups(row_flags)
            col_groups = _count_groups(col_flags)
            evidence.append({"file": path, "row_hits": row_hits, "col_hits": col_hits, "row_groups": row_groups, "col_groups": col_groups})
            if row_groups > 1 or col_groups > 1 or row_hits > 12 or col_hits > 12:
                violations.append({"file": path, "issue": f"检测到疑似网格线组: row_groups={row_groups}, col_groups={col_groups}, rows={row_hits}, cols={col_hits}"})
        return {
            "passed": len(violations) == 0,
            "check_type": "no_gridlines",
            "details": "启发式检查图中是否存在大范围浅灰色水平/垂直辅助线",
            "violations": violations,
            "evidence": {"images": evidence, "violation_count": len(violations)},
        }
    except ImportError:
        return {"passed": None, "check_type": "no_gridlines", "details": "Pillow 不可用", "violations": []}


def _noop(params, files):
    return {"passed": None, "check_type": "unknown", "details": "未知 figure check", "violations": []}


def _count_groups(flags):
    groups = 0
    in_group = False
    for flag in flags:
        if flag and not in_group:
            groups += 1
            in_group = True
        elif not flag:
            in_group = False
    return groups
