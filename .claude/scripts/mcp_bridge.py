#!/usr/bin/env python3
"""
MCP Bridge: 从 skills.yaml 的 tools 定义自动生成 MCP tool server。
让 Tool Facet 的脚本可被任何支持 MCP 的 agent 调用。

用法:
  python3 mcp_bridge.py --list                列出所有可暴露为 MCP tool 的 skill
  python3 mcp_bridge.py --generate <skill>    生成 MCP server 代码到 stdout
  python3 mcp_bridge.py --generate <skill> --write  写入 .claude/mcp/<skill>_server.py
  python3 mcp_bridge.py --serve <skill>       直接启动 MCP server（需要 fastmcp）
"""
import sys
import os
import argparse
import json
import subprocess

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

from manifest import load_manifest, ManifestLoadError


def get_tools_skills(manifest):
    """获取有 tools 定义的 skill。"""
    result = {}
    for name, defn in manifest.get("skills", {}).items():
        tools = defn.get("tools")
        if tools:
            result[name] = defn
    return result


def generate_mcp_server(skill_name, skill_def, claude_dir):
    """生成 MCP server Python 代码。"""
    tools = skill_def.get("tools", [])
    desc = skill_def.get("description", skill_name)

    lines = [
        '#!/usr/bin/env python3',
        f'"""MCP Tool Server for {skill_name}: {desc}',
        f'Auto-generated from skills.yaml by mcp_bridge.py."""',
        '',
        'import json',
        'import subprocess',
        'import os',
        'import sys',
        '',
        '# Skill 脚本根目录',
        f'SKILL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills", "{skill_name}")',
        '',
        'try:',
        '    from fastmcp import FastMCP',
        '    mcp = FastMCP(f"{skill_name} tools")',
        '    HAS_MCP = True',
        'except ImportError:',
        '    HAS_MCP = False',
        '    print("Warning: fastmcp not installed. Run: pip install fastmcp", file=sys.stderr)',
        '',
        '',
        'def _run_script(script, command, args_dict):',
        '    """调用 Tool Facet 脚本，返回 JSON 结果。"""',
        '    script_path = os.path.join(SKILL_DIR, script)',
        '    cmd = [sys.executable, script_path, command] + [str(v) for v in args_dict.values()]',
        '    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)',
        '    if result.returncode not in (0, 1):',
        '        return {"error": result.stderr.strip(), "exit_code": result.returncode}',
        '    try:',
        '        return json.loads(result.stdout)',
        '    except json.JSONDecodeError:',
        '        return {"raw_output": result.stdout.strip(), "exit_code": result.returncode}',
        '',
        '',
    ]

    # 生成每个 tool command 的函数
    for tool in tools:
        tool_name = tool.get("name", "unknown")
        script = tool.get("script", f"scripts/{tool_name}.py")

        for cmd_name, cmd_def in tool.get("commands", {}).items():
            func_name = f"{tool_name}_{cmd_name}"
            inputs = cmd_def.get("inputs", {})
            outputs = cmd_def.get("outputs", {})

            # 函数签名
            params = []
            for param_name, param_type in inputs.items():
                py_type = _yaml_type_to_python(param_type)
                params.append(f"{param_name}: {py_type}")
            params_str = ", ".join(params)

            # 文档字符串
            out_desc = ", ".join(f"{k}: {v}" for k, v in outputs.items())
            exit_codes = cmd_def.get("exit_codes", {})
            exit_desc = ", ".join(f"{k}={v}" for k, v in exit_codes.items())

            lines.append(f'def {func_name}({params_str}) -> dict:')
            lines.append(f'    """{tool_name} {cmd_name}')
            if out_desc:
                lines.append(f'    Returns: {{{out_desc}}}')
            if exit_desc:
                lines.append(f'    Exit codes: {exit_desc}')
            lines.append(f'    """')

            # 构建参数字典
            arg_dict_items = ", ".join(f'"{k}": {k}' for k in inputs)
            lines.append(f'    return _run_script("{script}", "{cmd_name}", {{{arg_dict_items}}})')
            lines.append('')

            # MCP 装饰器版本
            lines.append(f'if HAS_MCP:')
            lines.append(f'    @mcp.tool()')
            lines.append(f'    def mcp_{func_name}({params_str}) -> dict:')
            lines.append(f'        """{tool_name} {cmd_name}"""')
            lines.append(f'        return {func_name}({", ".join(inputs.keys())})')
            lines.append('')
            lines.append('')

    # 主入口
    lines.extend([
        'def main():',
        '    import argparse',
        '    parser = argparse.ArgumentParser()',
        '    parser.add_argument("--serve", action="store_true", help="启动 MCP server")',
        '    parser.add_argument("--call", help="直接调用: tool_command")',
        '    parser.add_argument("args", nargs="*", help="调用参数")',
        '    args = parser.parse_args()',
        '',
        '    if args.serve:',
        '        if not HAS_MCP:',
        '            print("Error: pip install fastmcp", file=sys.stderr)',
        '            sys.exit(1)',
        '        mcp.run()',
        '    elif args.call:',
        '        fn = globals().get(args.call)',
        '        if fn and callable(fn):',
        '            result = fn(*args.args)',
        '            print(json.dumps(result, ensure_ascii=False, indent=2))',
        '        else:',
        f'            available = [k for k in globals() if k.startswith(("{tool_name}_" for tool_name in [t["name"] for t in {json.dumps([t["name"] for t in tools])}]))]',
        '            print(f"Unknown: {{args.call}}. Available: {{available}}", file=sys.stderr)',
        '    else:',
        '        parser.print_help()',
        '',
        '',
        'if __name__ == "__main__":',
        '    main()',
    ])

    return "\n".join(lines)


def _yaml_type_to_python(yaml_type):
    """YAML 类型映射到 Python 类型注解。"""
    mapping = {
        "path": "str",
        "string": "str",
        "int": "int",
        "float": "float",
        "bool": "bool",
        "list": "list",
    }
    return mapping.get(str(yaml_type), "str")


def main():
    parser = argparse.ArgumentParser(description="MCP Bridge: skills.yaml → MCP tool server")
    parser.add_argument("--list", action="store_true", help="列出可暴露为 MCP tool 的 skill")
    parser.add_argument("--generate", metavar="SKILL", help="生成 MCP server 代码")
    parser.add_argument("--write", action="store_true", help="写入文件")
    parser.add_argument("--serve", metavar="SKILL", help="直接启动 MCP server")
    parser.add_argument("--cwd", default=".", help="项目根目录")
    args = parser.parse_args()

    try:
        manifest = load_manifest(cwd=args.cwd, search_paths=[args.cwd])
    except ManifestLoadError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    claude_dir = os.path.join(args.cwd, ".claude")
    tools_skills = get_tools_skills(manifest)

    if args.list:
        print(f"有 Tool Facet 的 skill（{len(tools_skills)} 个）：")
        for name, defn in tools_skills.items():
            tools = defn.get("tools", [])
            cmds = sum(len(t.get("commands", {})) for t in tools)
            print(f"  {name:<25} {len(tools)} tools, {cmds} commands")
            for t in tools:
                for cmd in t.get("commands", {}):
                    print(f"    └─ {t['name']}.{cmd}")
        return

    if args.generate:
        if args.generate not in tools_skills:
            print(f"Error: '{args.generate}' has no tools definition", file=sys.stderr)
            sys.exit(1)
        code = generate_mcp_server(args.generate, tools_skills[args.generate], claude_dir)

        if args.write:
            out_dir = os.path.join(claude_dir, "mcp")
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f"{args.generate}_server.py")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(code)
            print(f"Generated: {out_path}")
        else:
            print(code)
        return

    if args.serve:
        if args.serve not in tools_skills:
            print(f"Error: '{args.serve}' has no tools definition", file=sys.stderr)
            sys.exit(1)
        server_path = os.path.join(claude_dir, "mcp", f"{args.serve}_server.py")
        if not os.path.exists(server_path):
            print(f"Server not generated yet. Run: python3 mcp_bridge.py --generate {args.serve} --write")
            sys.exit(1)
        os.execvp(sys.executable, [sys.executable, server_path, "--serve"])

    parser.print_help()


if __name__ == "__main__":
    main()
