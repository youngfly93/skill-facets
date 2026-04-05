#!/usr/bin/env python3
"""检查图片背景色。"""
import os


def check(check_type, params, files):
    violations = []
    expected = params.get("expected_color", "#FFFFFF").upper()

    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext not in ('.png', '.jpg', '.jpeg', '.tiff'):
            continue
        try:
            from PIL import Image
            img = Image.open(f).convert('RGB')
            corners = [img.getpixel((0, 0)), img.getpixel((img.width-1, 0)),
                       img.getpixel((0, img.height-1)), img.getpixel((img.width-1, img.height-1))]
            exp_rgb = tuple(int(expected.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            for c in corners:
                dist = sum((a-b)**2 for a, b in zip(c, exp_rgb)) ** 0.5
                if dist > 30:
                    hex_c = f"#{c[0]:02X}{c[1]:02X}{c[2]:02X}"
                    violations.append({"file": f, "issue": f"背景色 {hex_c} 偏离 {expected}"})
                    break
        except ImportError:
            return {"passed": None, "check_type": check_type,
                    "details": "Pillow 不可用", "violations": []}
        except Exception as e:
            violations.append({"file": f, "issue": str(e)})

    return {"passed": len(violations) == 0, "check_type": check_type,
            "details": f"期望: {expected}", "violations": violations}
