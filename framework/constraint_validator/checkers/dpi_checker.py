#!/usr/bin/env python3
"""检查图片 DPI。"""
import os


def check(check_type, params, files):
    violations = []
    min_dpi = params.get("min_dpi", 300)
    epsilon = float(params.get("epsilon", 0.5))

    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext not in ('.png', '.jpg', '.jpeg', '.tiff', '.tif'):
            continue
        try:
            from PIL import Image
            img = Image.open(f)
            dpi = img.info.get('dpi', (72, 72))
            actual = min(dpi[0], dpi[1])
            if actual + epsilon < min_dpi:
                violations.append({"file": f, "issue": f"DPI={actual}，需>={min_dpi} (epsilon={epsilon})"})
        except ImportError:
            return {"passed": None, "check_type": check_type,
                    "details": "Pillow 不可用", "violations": []}

    return {"passed": len(violations) == 0, "check_type": check_type,
            "details": f"最低: {min_dpi} DPI (epsilon={epsilon})", "violations": violations}
