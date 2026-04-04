#!/usr/bin/env python3
"""扫描文件中的 AI 使用痕迹，可选清除文本内容中的匹配项。"""

import os
import sys
import json
import zipfile
import re
import shutil
import tempfile
from pathlib import Path

AI_PATTERNS = [
    r"作为AI", r"作为一个AI", r"I'm an AI", r"as an AI",
    r"由AI生成", r"AI-generated", r"ChatGPT", r"Claude",
    r"GPT-4", r"由人工智能", r"artificial intelligence generated",
]

AI_METADATA_FIELDS = ["creator", "author", "lastModifiedBy", "description", "comments"]
AI_METADATA_VALUES = ["chatgpt", "claude", "openai", "anthropic", "copilot", "ai assistant"]

def scan_docx_metadata(filepath: str) -> list:
    """检查 docx 元数据中的 AI 痕迹。"""
    issues = []
    try:
        with zipfile.ZipFile(filepath, 'r') as z:
            if 'docProps/core.xml' in z.namelist():
                content = z.read('docProps/core.xml').decode('utf-8', errors='ignore').lower()
                for val in AI_METADATA_VALUES:
                    if val in content:
                        issues.append({"file": filepath, "type": "metadata", "match": val})
    except Exception:
        pass
    return issues

def scan_text_content(filepath: str) -> list:
    """检查文本文件中的 AI 表达。"""
    issues = []
    try:
        text = Path(filepath).read_text(encoding='utf-8', errors='ignore')
        for pat in AI_PATTERNS:
            for m in re.finditer(pat, text, re.IGNORECASE):
                issues.append({"file": filepath, "type": "content", "match": m.group(), "pos": m.start()})
    except Exception:
        pass
    return issues

def scan_directory(directory: str) -> list:
    """扫描目录，返回所有 AI 痕迹。"""
    all_issues = []
    for root, _, files in os.walk(directory):
        for f in files:
            full = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()
            if ext in ('.docx', '.xlsx', '.pptx'):
                all_issues.extend(scan_docx_metadata(full))
            if ext in ('.txt', '.md', '.csv', '.tsv', '.xml', '.html'):
                all_issues.extend(scan_text_content(full))
    return all_issues

def clean_text_content(filepath: str, patterns=AI_PATTERNS) -> int:
    """清除文本文件中的 AI 表达，返回清除数量。"""
    try:
        text = Path(filepath).read_text(encoding='utf-8', errors='ignore')
        count = 0
        for pat in patterns:
            text, n = re.subn(pat, '', text, flags=re.IGNORECASE)
            count += n
        if count > 0:
            Path(filepath).write_text(text, encoding='utf-8')
        return count
    except Exception:
        return 0

def clean_docx_metadata(filepath: str) -> int:
    """清除 docx/xlsx/pptx 元数据中的 AI 痕迹，返回清除数量。"""
    count = 0
    try:
        tmp = tempfile.mktemp(suffix=os.path.splitext(filepath)[1])
        shutil.copy2(filepath, tmp)
        with zipfile.ZipFile(tmp, 'r') as zin:
            with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zout:
                for item in zin.namelist():
                    data = zin.read(item)
                    if item == 'docProps/core.xml':
                        text = data.decode('utf-8', errors='ignore')
                        for val in AI_METADATA_VALUES:
                            if val in text.lower():
                                text = re.sub(re.escape(val), '', text, flags=re.IGNORECASE)
                                count += 1
                        data = text.encode('utf-8')
                    zout.writestr(item, data)
        os.remove(tmp)
    except Exception:
        if os.path.exists(tmp):
            shutil.move(tmp, filepath)
    return count

def clean_directory(directory: str) -> list:
    """清除目录中所有文件的 AI 痕迹，返回清除记录。"""
    cleaned = []
    for root, _, files in os.walk(directory):
        for f in files:
            full = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()
            n = 0
            if ext in ('.docx', '.xlsx', '.pptx'):
                n += clean_docx_metadata(full)
            if ext in ('.txt', '.md', '.csv', '.tsv', '.xml', '.html'):
                n += clean_text_content(full)
            if n > 0:
                cleaned.append({"file": full, "cleaned_count": n})
    return cleaned

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"

    if cmd == "scan":
        target = sys.argv[2] if len(sys.argv) > 2 else "."
        issues = scan_directory(target)
        print(json.dumps(issues, ensure_ascii=False, indent=2))
        sys.exit(1 if issues else 0)

    elif cmd == "clean":
        target = sys.argv[2] if len(sys.argv) > 2 else "."
        cleaned = clean_directory(target)
        print(json.dumps(cleaned, ensure_ascii=False, indent=2))
        sys.exit(0)

    else:
        print("Usage: ai_trace_scan.py [scan|clean] <directory>")
        sys.exit(2)
