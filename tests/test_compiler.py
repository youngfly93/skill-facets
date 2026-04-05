"""Test skill_compile.py: YAML → Markdown compilation."""
import os
import sys
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".claude", "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from skill_compile import compile_command_md, compile_skill_md


class TestCompileCommandMd:
    def test_has_constraint_section(self, project_root):
        from manifest import get_skill
        skill = get_skill("sci-fig", cwd=project_root)
        md = compile_command_md("sci-fig", skill)
        assert "CONSTRAINT" in md
        assert "ASPIRATION" in md
        assert "FREEDOM" in md

    def test_constraints_from_render(self, project_root):
        from manifest import get_skill
        skill = get_skill("ppt", cwd=project_root)
        md = compile_command_md("ppt", skill)
        # compile.constraints_render 应产出人类可读文本，不是 rule 字段
        compile_meta = skill.get("compile", {})
        if compile_meta.get("constraints_render"):
            assert compile_meta["constraints_render"][0] in md

    def test_description_as_lead(self, project_root):
        from manifest import get_skill
        skill = get_skill("sci-fig", cwd=project_root)
        md = compile_command_md("sci-fig", skill)
        # 第一行应该是 description 或 compile.lead
        first_line = md.strip().split('\n')[0]
        assert len(first_line) > 5

    def test_no_empty_output(self, project_root):
        from manifest import get_skill
        skill = get_skill("audit-fix", cwd=project_root)
        md = compile_command_md("audit-fix", skill)
        assert len(md.strip()) > 50


class TestCompileSkillMd:
    def test_has_frontmatter(self, project_root):
        from manifest import get_skill
        skill = get_skill("deliver-v4", cwd=project_root)
        md = compile_skill_md("deliver-v4", skill)
        assert md.startswith("---")
        assert "name: deliver-v4" in md

    def test_has_tool_facet(self, project_root):
        from manifest import get_skill
        skill = get_skill("deliver-v4", cwd=project_root)
        md = compile_skill_md("deliver-v4", skill)
        assert "Tool Facet" in md

    def test_has_prompt_facet(self, project_root):
        from manifest import get_skill
        skill = get_skill("deliver-v4", cwd=project_root)
        md = compile_skill_md("deliver-v4", skill)
        assert "Prompt Facet" in md
        assert "CONSTRAINT" in md

    def test_has_workflow_steps(self, project_root):
        from manifest import get_skill
        skill = get_skill("deliver-v4", cwd=project_root)
        md = compile_skill_md("deliver-v4", skill)
        assert "Step" in md or "步骤" in md


class TestCompileAllSkills:
    def test_all_contract_skills_compile(self, project_root):
        """所有有 contract 的 skill 都应能编译。"""
        from manifest import load_manifest
        m = load_manifest(cwd=project_root)
        for name, defn in m.get("skills", {}).items():
            if not defn.get("contract"):
                continue
            skill_type = defn.get("type", "command")
            if skill_type == "command":
                md = compile_command_md(name, defn)
            else:
                md = compile_skill_md(name, defn)
            assert len(md.strip()) > 20, f"{name} compiled to empty/short output"
