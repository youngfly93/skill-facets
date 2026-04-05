#!/usr/bin/env python3
"""
Skill 编译器：从 skills.yaml 生成 SKILL.md / commands/*.md。
让 skills.yaml 成为唯一编写源，Markdown 成为编译产物。

用法:
  python3 skill_compile.py --list                          列出所有可编译 skill
  python3 skill_compile.py <skill_name>                    编译单个 skill 到 stdout
  python3 skill_compile.py <skill_name> --write            写入对应的 .md 文件
  python3 skill_compile.py --all --write                   编译所有有 contract 的 skill
  python3 skill_compile.py --all --write --out-dir ./out   指定输出目录
"""
import sys
import os
import argparse
import json

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

from manifest import load_manifest, ManifestLoadError


def compile_command_md(name, skill_def):
    """从 skills.yaml entry 生成 V4 嵌套信号 command .md 内容。"""
    lines = []
    desc = skill_def.get("description", "")
    lines.append(f"{desc}\n")

    contract = skill_def.get("contract")
    if not contract:
        return "\n".join(lines)

    constraints = contract.get("constraints", [])
    aspirations = contract.get("aspirations", [])
    freedoms = contract.get("freedoms", [])

    if constraints:
        lines.append("## 边界（CONSTRAINT）\n")
        for c in constraints:
            lines.append(f"- {c['rule']}")
        lines.append("")

    if aspirations:
        lines.append("  ### 在此边界内追求（ASPIRATION）\n")
        lines.append("  以下所有追求不得违反上方边界。\n")
        for a in aspirations:
            lines.append(f"  - {a}")
        lines.append("")

    if freedoms:
        lines.append("    #### 可自主决定（FREEDOM）\n")
        lines.append("    以下选择空间在上方边界和追求方向内自主发挥。\n")
        for f in freedoms:
            lines.append(f"    - {f}")
        lines.append("")

    return "\n".join(lines)


def compile_skill_md(name, skill_def):
    """从 skills.yaml entry 生成双 Facet SKILL.md 内容。"""
    lines = []
    desc = skill_def.get("description", "")

    # Frontmatter
    lines.append("---")
    lines.append(f"name: {name}")
    lines.append(f"description: >-")
    lines.append(f"  {desc}")
    lines.append("---\n")

    # Tool Facet
    tools = skill_def.get("tools", [])
    if tools:
        lines.append("## Tool Facet — 确定性操作\n")
        for tool in tools:
            lines.append(f"### {tool['name']}\n")
            lines.append("```bash")
            script = tool.get("script", f"scripts/{tool['name']}.py")
            for cmd_name, cmd_def in tool.get("commands", {}).items():
                inputs = cmd_def.get("inputs", {})
                args = " ".join(f"<{k}>" for k in inputs)
                outputs = cmd_def.get("outputs", {})
                out_desc = ", ".join(f"{k}: {v}" for k, v in outputs.items())
                lines.append(f"# {cmd_name}")
                lines.append(f"python3 ${{CLAUDE_SKILL_DIR}}/{script} {cmd_name} {args}")
                lines.append(f"# → {{{out_desc}}}")
            lines.append("```\n")
        lines.append("---\n")

    # Prompt Facet
    lines.append("## Prompt Facet — 流程决策指导\n")

    contract = skill_def.get("contract")
    if contract:
        constraints = contract.get("constraints", [])
        aspirations = contract.get("aspirations", [])
        freedoms = contract.get("freedoms", [])

        if constraints:
            lines.append("### 边界（CONSTRAINT）\n")
            for c in constraints:
                lines.append(f"- {c['rule']}")
            lines.append("")

        if aspirations:
            lines.append("  #### 在此边界内追求（ASPIRATION）\n")
            lines.append("  以下所有追求不得违反上方边界。\n")
            for a in aspirations:
                lines.append(f"  - {a}")
            lines.append("")

        if freedoms:
            lines.append("    ##### 可自主决定（FREEDOM）\n")
            lines.append("    以下选择空间在上方边界和追求方向内自主发挥。\n")
            for f in freedoms:
                lines.append(f"    - {f}")
            lines.append("")

    # Workflow
    workflow = skill_def.get("workflow")
    if workflow:
        states = workflow.get("states", [])
        transitions = workflow.get("transitions", {})
        if states:
            lines.append("### 步骤\n")
            for i, state in enumerate(states):
                trans = transitions.get(state, {})
                condition = trans.get("condition", "")
                fail = trans.get("fail", "")
                step_desc = f"**Step {i+1} — {state}**"
                if condition:
                    step_desc += f"\n条件: {condition}"
                if fail:
                    step_desc += f" | 失败: {fail}"
                lines.append(step_desc + "\n")

    return "\n".join(lines)


def get_output_path(name, skill_def, out_dir, claude_dir):
    """确定编译输出路径。"""
    source = skill_def.get("source", "")
    skill_type = skill_def.get("type", "command")

    if out_dir:
        base = out_dir
    else:
        base = claude_dir

    if source:
        return os.path.join(base, source)
    elif skill_type == "command":
        return os.path.join(base, "commands", f"{name}.md")
    else:
        return os.path.join(base, "skills", name, "SKILL.md")


def main():
    parser = argparse.ArgumentParser(description="Skill 编译器: skills.yaml → SKILL.md / command.md")
    parser.add_argument("skill", nargs="?", help="要编译的 skill 名称")
    parser.add_argument("--list", action="store_true", help="列出所有可编译 skill")
    parser.add_argument("--all", action="store_true", help="编译所有有 contract 的 skill")
    parser.add_argument("--write", action="store_true", help="写入文件（否则输出到 stdout）")
    parser.add_argument("--out-dir", help="输出目录（默认写回 .claude/）")
    parser.add_argument("--diff", action="store_true", help="显示与现有文件的差异")
    parser.add_argument("--cwd", default=".", help="项目根目录")
    args = parser.parse_args()

    try:
        manifest = load_manifest(cwd=args.cwd, search_paths=[args.cwd])
    except ManifestLoadError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    skills = manifest.get("skills", {})
    claude_dir = os.path.join(args.cwd, ".claude") if not args.cwd.endswith(".claude") else args.cwd

    if args.list:
        print("可编译的 skill（有 contract）：")
        for name, defn in skills.items():
            has_contract = bool(defn.get("contract"))
            has_tools = bool(defn.get("tools"))
            source = defn.get("source", "(no source)")
            status = "✅" if has_contract else "○"
            tools_tag = " +tools" if has_tools else ""
            print(f"  {status} {name:<25} → {source}{tools_tag}")
        return

    targets = []
    if args.all:
        targets = [(n, d) for n, d in skills.items() if d.get("contract")]
    elif args.skill:
        if args.skill not in skills:
            print(f"Error: skill '{args.skill}' not found in skills.yaml", file=sys.stderr)
            sys.exit(1)
        targets = [(args.skill, skills[args.skill])]
    else:
        parser.print_help()
        sys.exit(1)

    for name, defn in targets:
        skill_type = defn.get("type", "command")
        if skill_type == "command":
            content = compile_command_md(name, defn)
        else:
            content = compile_skill_md(name, defn)

        if args.write:
            out_path = get_output_path(name, defn, args.out_dir, claude_dir)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)

            if args.diff and os.path.exists(out_path):
                existing = open(out_path, encoding="utf-8").read()
                if existing.strip() == content.strip():
                    print(f"  ≡ {name} → {out_path} (unchanged)")
                    continue
                else:
                    print(f"  Δ {name} → {out_path} (changed)")
            else:
                print(f"  → {name} → {out_path}")

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            if len(targets) > 1:
                print(f"=== {name} ({skill_type}) ===")
            print(content)
            if len(targets) > 1:
                print()


if __name__ == "__main__":
    main()
