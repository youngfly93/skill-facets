#!/usr/bin/env python3
"""检查 OOXML 文档中的字体。"""
import zipfile, re, os


def check(check_type, params, files):
    violations = []
    font_spec = params.get("font_spec", "")
    expected = _extract_names(font_spec)

    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext not in ('.docx', '.pptx'):
            continue
        try:
            with zipfile.ZipFile(f, 'r') as z:
                found_fonts = set()
                for name in z.namelist():
                    if name.endswith('.xml') and 'slide' in name or 'document' in name:
                        xml = z.read(name).decode('utf-8', errors='ignore')
                        found_fonts.update(re.findall(r'typeface="([^"]+)"', xml))
                        found_fonts.update(re.findall(r'w:ascii="([^"]+)"', xml))
                        found_fonts.update(re.findall(r'w:eastAsia="([^"]+)"', xml))
                # 检查期望字体是否在文档中被使用
                if expected and not any(e in found_fonts for e in expected):
                    violations.append({"file": f, "issue": f"未找到期望字体 {expected}，实际: {found_fonts & _non_default(found_fonts)}"})
        except Exception as e:
            violations.append({"file": f, "issue": str(e)})

    return {"passed": len(violations) == 0, "check_type": check_type,
            "details": f"期望: {expected}", "violations": violations}


def _extract_names(spec):
    names = []
    for p in re.findall(r'[（(]([^）)]+)[）)]', spec):
        names.extend(n.strip() for n in p.split('/'))
    base = re.sub(r'[（(][^）)]+[）)]', '', spec).strip().rstrip('，,')
    if base:
        names.append(base)
    return names


def _non_default(fonts):
    defaults = {'Calibri', 'Calibri Light', 'Arial', 'Times New Roman'}
    return fonts - defaults
