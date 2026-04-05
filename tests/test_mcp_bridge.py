"""Test mcp_bridge.py: code generation + import check."""
import os
import sys
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".claude", "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from mcp_bridge import get_tools_skills, generate_mcp_server


class TestGetToolsSkills:
    def test_finds_deliver(self, project_root):
        from manifest import load_manifest
        m = load_manifest(cwd=project_root)
        tools = get_tools_skills(m)
        assert "deliver-v4" in tools

    def test_no_tools_for_ppt(self, project_root):
        from manifest import load_manifest
        m = load_manifest(cwd=project_root)
        tools = get_tools_skills(m)
        assert "ppt" not in tools


class TestGenerateMcpServer:
    def test_generates_valid_python(self, project_root):
        from manifest import get_skill
        skill = get_skill("deliver-v4", cwd=project_root)
        code = generate_mcp_server("deliver-v4", skill, os.path.join(project_root, ".claude"))
        assert "def zip_pack_pack" in code
        assert "def zip_pack_verify" in code
        assert "def ai_trace_scan_scan" in code
        assert "def ai_trace_scan_clean" in code

    def test_code_is_compilable(self, project_root):
        from manifest import get_skill
        skill = get_skill("deliver-v4", cwd=project_root)
        code = generate_mcp_server("deliver-v4", skill, os.path.join(project_root, ".claude"))
        compile(code, "<mcp_server>", "exec")  # 语法检查

    def test_has_run_script_helper(self, project_root):
        from manifest import get_skill
        skill = get_skill("deliver-v4", cwd=project_root)
        code = generate_mcp_server("deliver-v4", skill, os.path.join(project_root, ".claude"))
        assert "_run_script" in code

    def test_has_mcp_decorators(self, project_root):
        from manifest import get_skill
        skill = get_skill("deliver-v4", cwd=project_root)
        code = generate_mcp_server("deliver-v4", skill, os.path.join(project_root, ".claude"))
        assert "mcp.tool()" in code
