#!/usr/bin/env python3
"""检查 OOXML 文档中的字体。"""
import os
import re
import zipfile


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
                    if not name.endswith('.xml'):
                        continue
                    if ext == '.pptx' and ('slide' not in name and 'theme' not in name):
                        continue
                    if ext == '.docx' and name not in {'word/document.xml', 'word/styles.xml', 'word/theme/theme1.xml'}:
                        continue
                    xml = z.read(name).decode('utf-8', errors='ignore')
                    found_fonts.update(re.findall(r'typeface="([^"]+)"', xml))
                    found_fonts.update(re.findall(r'w:ascii="([^"]+)"', xml))
                    found_fonts.update(re.findall(r'w:eastAsia="([^"]+)"', xml))
                    found_fonts.update(re.findall(r'w:hAnsi="([^"]+)"', xml))
                    found_fonts.update(re.findall(r'w:cs="([^"]+)"', xml))
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
        aliases = {
            "黑体": ["SimHei"],
            "宋体": ["SimSun"],
        }
        names.extend(aliases.get(base, []))
    return names


def _non_default(fonts):
    defaults = {'Calibri', 'Calibri Light', 'Arial', 'Times New Roman'}
    return fonts - defaults
