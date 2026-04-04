#!/usr/bin/env python3
"""Windows 兼容 ZIP 打包工具。确保中文文件名不乱码。"""

import zipfile
import os
import sys
import datetime
import hashlib

EXCLUDE = {'.DS_Store', '__MACOSX', '.git', '.Rhistory', '.RData', 'Thumbs.db'}

def should_exclude(path: str) -> bool:
    parts = path.split(os.sep)
    return any(p in EXCLUDE for p in parts)

def pack(delivery_dir: str, project_name: str = "项目") -> str:
    """打包 delivery/ 为 Windows 兼容 ZIP，返回 ZIP 路径。"""
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    zip_name = f"{project_name}_交付_{date_str}.zip"
    zip_path = os.path.join(os.path.dirname(delivery_dir), zip_name)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for root, dirs, files in os.walk(delivery_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE]
            for f in files:
                full = os.path.join(root, f)
                arcname = os.path.relpath(full, os.path.dirname(delivery_dir))
                if not should_exclude(arcname):
                    zf.write(full, arcname)

    return zip_path

def verify(zip_path: str) -> dict:
    """验证 ZIP 完整性，返回结果字典。"""
    with zipfile.ZipFile(zip_path, 'r') as zf:
        bad = zf.testzip()
        names = zf.namelist()
        total_size = sum(i.file_size for i in zf.infolist())
    return {
        "crc_ok": bad is None,
        "bad_file": bad,
        "file_count": len(names),
        "total_size_mb": round(total_size / 1024 / 1024, 1),
        "files": names
    }

def checksum(delivery_dir: str) -> str:
    """生成 delivery/ 的 MD5 校验和文件，返回文件路径。"""
    out_path = os.path.join(os.path.dirname(delivery_dir), "delivery_md5.txt")
    lines = []
    for root, dirs, files in sorted(os.walk(delivery_dir)):
        dirs.sort()
        for f in sorted(files):
            full = os.path.join(root, f)
            rel = os.path.relpath(full, delivery_dir)
            md5 = hashlib.md5(open(full, 'rb').read()).hexdigest()
            lines.append(f"{md5}  {rel}")
    with open(out_path, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    return out_path

if __name__ == "__main__":
    import json
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "pack":
        path = pack(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "项目")
        print(json.dumps({"zip_path": path}))
    elif cmd == "verify":
        result = verify(sys.argv[2])
        print(json.dumps(result, ensure_ascii=False))
    elif cmd == "checksum":
        path = checksum(sys.argv[2])
        print(json.dumps({"checksum_path": path}))
    else:
        print("Usage: zip_pack.py [pack|verify|checksum] <path> [project_name]")
