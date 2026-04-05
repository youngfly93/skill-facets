#!/usr/bin/env python3
"""内容级检查：编号连续、Markdown 残留。"""
import os, re, zipfile


def check(check_type, params, files):
    dispatch = {
        "numbering": _numbering,
        "no_markdown": _no_markdown,
        "no_gridlines": lambda p, f: {"passed": None, "check_type": "no_gridlines",
                                       "details": "需视觉审查", "violations": []},
    }
    return dispatch.get(check_type, _noop)(params, files)


def _numbering(params, files):
    violations = []
    for f in files:
        if not f.endswith('.docx'):
            continue
        try:
            text = _docx_text(f)
            for label, pat in [("图", r'图\s*(\d+)'), ("表", r'表\s*(\d+)')]:
                matches = [int(m) for m in re.findall(pat, text)]
                nums = sorted(set(matches))
                if nums:
                    expected = list(range(1, max(nums) + 1))
                    missing = set(expected) - set(nums)
                    if missing:
                        violations.append({"file": f, "issue": f"{label}编号缺: {sorted(missing)}"})
                    counts = {n: matches.count(n) for n in nums}
                    underreferenced = sorted(n for n, count in counts.items() if count < 2)
                    if underreferenced:
                        violations.append({"file": f, "issue": f"{label}引用/标题可能不一致，出现次数不足 2: {underreferenced}"})
        except Exception:
            pass
    return {"passed": len(violations) == 0, "check_type": "numbering",
            "details": "编号连续性", "violations": violations}


def _no_markdown(params, files):
    violations = []
    pats = [(r'\*\*[^*]+\*\*', '**'), (r'(?<!\S)##?\s', '##'),
            (r'`[^`]+`', '`'), (r'^\s*-\s*\[\s*[xX ]?\s*\]', '- [ ]')]
    for f in files:
        if not f.endswith('.docx'):
            continue
        try:
            text = _docx_text(f)
            for p, desc in pats:
                if re.search(p, text):
                    violations.append({"file": f, "issue": f"Markdown 残留: {desc}"})
        except Exception:
            pass
    return {"passed": len(violations) == 0, "check_type": "no_markdown",
            "details": "Markdown 标记检查", "violations": violations}


def _docx_text(fpath):
    with zipfile.ZipFile(fpath, 'r') as z:
        if 'word/document.xml' in z.namelist():
            xml = z.read('word/document.xml').decode('utf-8', errors='ignore')
            paragraphs = []
            for block in re.findall(r'<w:p\b[\s\S]*?</w:p>', xml):
                texts = re.findall(r'<w:t[^>]*>([^<]+)</w:t>', block)
                if texts:
                    paragraphs.append(''.join(texts))
            return '\n'.join(paragraphs)
    return ""


def _noop(p, f):
    return {"passed": None, "check_type": "unknown", "details": "", "violations": []}
