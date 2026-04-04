#!/usr/bin/env python3
"""从 SKILL.md 或 command .md 中提取 CONSTRAINT 列表。"""
import re
import os
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class Constraint:
    raw: str
    source_file: str
    line_number: int
    checkable: bool = False
    check_type: str = ""
    check_params: dict = field(default_factory=dict)

# (正则, check_type, param提取)
PATTERNS = [
    (r'(?:中文|英文)?(?:正文)?字体[：:]\s*(.+)', 'font', lambda m: {"font_spec": m.group(1)}),
    (r'(?:背景|底色)[^#]*?(?:纯白|#([0-9A-Fa-f]{6}))', 'color', lambda m: {"expected_color": f"#{m.group(1)}" if m.group(1) else "#FFFFFF"}),
    (r'分辨率\s*[>>=]*\s*(\d+)\s*DPI', 'dpi', lambda m: {"min_dpi": int(m.group(1))}),
    (r'(?:输出|文件)格式[为是：:]\s*(.+)', 'format', lambda m: {"allowed": re.findall(r'\.\w+', m.group(1))}),
    (r'行距[：:]\s*([\d.]+)\s*倍', 'line_spacing', lambda m: {"spacing": float(m.group(1))}),
    (r'(?:图表?|表)编号连续', 'numbering', lambda m: {}),
    (r'不使用网格线', 'no_gridlines', lambda m: {}),
    (r'(?:不得有|禁止).{0,5}Markdown.{0,5}标记', 'no_markdown', lambda m: {}),
    (r'(\d+)\s*pt', 'font_size', lambda m: {"size_pt": int(m.group(1))}),
]


def parse_constraints(filepath: str) -> list:
    text = Path(filepath).read_text(encoding='utf-8')
    lines = text.split('\n')
    constraints = []
    in_section = False

    for i, line in enumerate(lines, 1):
        if re.search(r'(?:CONSTRAINT|边界|设计约束)', line, re.IGNORECASE):
            in_section = True
            continue
        if in_section and re.match(r'\s*#+\s', line):
            if re.search(r'(?:ASPIRATION|FREEDOM|追求|自由|自主|在此边界内)', line):
                in_section = False
                continue
        if in_section and re.match(r'\s*-\s+', line):
            raw = re.sub(r'^\s*-\s+', '', line).strip()
            if not raw:
                continue
            c = Constraint(raw=raw, source_file=filepath, line_number=i)
            for pat, ctype, pfn in PATTERNS:
                m = re.search(pat, raw)
                if m:
                    c.checkable = True
                    c.check_type = ctype
                    c.check_params = pfn(m)
                    break
            constraints.append(c)
    return constraints


def find_source(name: str) -> str:
    """优先查找项目级 .claude/，回退到全局 ~/.claude/。"""
    cwd = os.getcwd()
    for path in [
        os.path.join(cwd, f".claude/commands/{name}.md"),
        os.path.join(cwd, f".claude/skills/{name}/SKILL.md"),
        os.path.expanduser(f"~/.claude/commands/{name}.md"),
        os.path.expanduser(f"~/.claude/skills/{name}/SKILL.md"),
    ]:
        if os.path.exists(path):
            return path
    return ""
