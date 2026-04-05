#!/usr/bin/env python3
"""PPTX structure checks."""

from __future__ import annotations

import os
import posixpath
import re
import zipfile


def check(check_type, params, files):
    dispatch = {
        "image_aspect_ratio": _image_aspect_ratio,
        "pure_bullet_page": _pure_bullet_page,
        "slide_structure": _slide_structure,
    }
    return dispatch.get(check_type, _noop)(params, files)


def _pptx_files(files):
    return [f for f in files if f.endswith(".pptx")]


def _load_pptx(path):
    with zipfile.ZipFile(path, "r") as zf:
        names = zf.namelist()
        slides = sorted(
            [name for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)],
            key=lambda x: int(re.search(r"slide(\d+)\.xml", x).group(1)),
        )
        rels = {name: zf.read(name).decode("utf-8", errors="ignore") for name in names if name.endswith(".rels")}
        xml = {name: zf.read(name).decode("utf-8", errors="ignore") for name in slides}
        media_bytes = {name: zf.read(name) for name in names if name.startswith("ppt/media/")}
    return slides, xml, rels, media_bytes


def _slide_texts(slide_xml):
    return re.findall(r"<a:t>([^<]+)</a:t>", slide_xml)


def _slide_bullet_stats(slide_xml):
    paragraphs = re.findall(r"<a:p[\s\S]*?</a:p>", slide_xml)
    total = 0
    bullet = 0
    for para in paragraphs:
        texts = re.findall(r"<a:t>([^<]+)</a:t>", para)
        joined = "".join(texts).strip()
        if not joined:
            continue
        total += 1
        if "<a:buChar" in para or "<a:buAutoNum" in para or joined[:1] in {"•", "-", "·"}:
            bullet += 1
    return total, bullet


def _image_aspect_ratio(params, files):
    violations = []
    evidence = []
    tolerance = float(params.get("tolerance", 0.03))
    try:
        from PIL import Image
        import io
    except ImportError:
        return {"passed": None, "check_type": "image_aspect_ratio", "details": "Pillow 不可用", "violations": []}

    for f in _pptx_files(files):
        try:
            slides, xml_map, rels_map, media_bytes = _load_pptx(f)
            file_evidence = []
            for slide in slides:
                slide_xml = xml_map[slide]
                rel_path = posixpath.join(posixpath.dirname(slide), "_rels", posixpath.basename(slide) + ".rels")
                rel_xml = rels_map.get(rel_path, "")
                rid_to_target = {
                    rid: posixpath.normpath(posixpath.join("ppt/slides", target))
                    for rid, target in re.findall(r'Id="([^"]+)"[^>]+Target="([^"]+)"', rel_xml)
                }
                for picture in re.findall(r"<p:pic[\s\S]*?</p:pic>", slide_xml):
                    rid_match = re.search(r'r:embed="([^"]+)"', picture)
                    ext_match = re.search(r"<a:ext[^>]*cx=\"(\d+)\"[^>]*cy=\"(\d+)\"", picture)
                    crop = "<a:srcRect" in picture
                    if not rid_match or not ext_match or crop:
                        continue
                    target = rid_to_target.get(rid_match.group(1))
                    if not target or target not in media_bytes:
                        continue
                    with Image.open(io.BytesIO(media_bytes[target])) as img:
                        actual_ratio = img.width / max(1, img.height)
                    display_ratio = int(ext_match.group(1)) / max(1, int(ext_match.group(2)))
                    diff = abs(display_ratio - actual_ratio) / max(actual_ratio, 1e-6)
                    entry = {"slide": slide, "target": target, "display_ratio": round(display_ratio, 4), "actual_ratio": round(actual_ratio, 4), "diff": round(diff, 4)}
                    file_evidence.append(entry)
                    if diff > tolerance:
                        violations.append({"file": f, "issue": f"{slide} 图片比例疑似被拉伸: {entry}"})
            evidence.append({"file": f, "images": file_evidence})
        except Exception as exc:
            violations.append({"file": f, "issue": str(exc)})
    return {
        "passed": len(violations) == 0,
        "check_type": "image_aspect_ratio",
        "details": f"容忍比例偏差 <= {tolerance:.2%}",
        "violations": violations,
        "evidence": {"presentations": evidence, "violation_count": len(violations)},
    }


def _pure_bullet_page(params, files):
    violations = []
    evidence = []
    ratio_threshold = float(params.get("bullet_ratio", 0.8))
    min_paras = int(params.get("min_paragraphs", 3))

    for f in _pptx_files(files):
        try:
            slides, xml_map, _, _ = _load_pptx(f)
            file_evidence = []
            for slide in slides:
                total, bullet = _slide_bullet_stats(xml_map[slide])
                ratio = bullet / total if total else 0.0
                file_evidence.append({"slide": slide, "paragraphs": total, "bullet_paragraphs": bullet, "bullet_ratio": round(ratio, 3)})
                if total >= min_paras and ratio >= ratio_threshold:
                    violations.append({"file": f, "issue": f"{slide} 疑似纯列表页: {bullet}/{total} bullet paragraphs"})
            evidence.append({"file": f, "slides": file_evidence})
        except Exception as exc:
            violations.append({"file": f, "issue": str(exc)})
    return {
        "passed": len(violations) == 0,
        "check_type": "pure_bullet_page",
        "details": "检查是否存在高比例 bullet 段落的页面",
        "violations": violations,
        "evidence": {"presentations": evidence, "violation_count": len(violations)},
    }


def _slide_structure(params, files):
    violations = []
    evidence = []
    summary_keywords = params.get("summary_keywords", ["总结", "Summary", "结论", "Takeaway", "Q&A", "谢谢"])

    for f in _pptx_files(files):
        try:
            slides, xml_map, _, _ = _load_pptx(f)
            texts = [_slide_texts(xml_map[slide]) for slide in slides]
            summary_found = False
            if texts:
                last_text = " ".join(texts[-1])
                summary_found = any(keyword.lower() in last_text.lower() for keyword in summary_keywords)
            file_evidence = {
                "slide_count": len(slides),
                "first_slide_text_count": len(texts[0]) if texts else 0,
                "last_slide_text_count": len(texts[-1]) if texts else 0,
                "summary_found": summary_found,
            }
            evidence.append({"file": f, **file_evidence})
            if len(slides) < 3:
                violations.append({"file": f, "issue": "幻灯片数量不足，无法满足总分总结构"})
            if texts and len(texts[0]) == 0:
                violations.append({"file": f, "issue": "封面页缺少标题文本"})
            if texts and not summary_found:
                violations.append({"file": f, "issue": "最后一页未检测到总结/结论类关键词"})
        except Exception as exc:
            violations.append({"file": f, "issue": str(exc)})
    return {
        "passed": len(violations) == 0,
        "check_type": "slide_structure",
        "details": "启发式检查封面-主体-总结结构",
        "violations": violations,
        "evidence": {"presentations": evidence, "violation_count": len(violations)},
    }


def _noop(params, files):
    return {"passed": None, "check_type": "unknown", "details": "未知 ppt check", "violations": []}
