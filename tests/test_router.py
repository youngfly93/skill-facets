"""Test skill_router.py: keyword matching, negative exclusion, scoring."""
import os
import sys
import json
import pytest

# Import router's match function
HOOKS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".claude", "hooks")
sys.path.insert(0, HOOKS_DIR)
from skill_router import match_skill


class TestMatchSkill:
    """Test the core matching logic."""

    def test_keyword_hit(self, tmp_path):
        defn = {"keywords": ["PPT", "幻灯片"], "priority": 10, "hint": "test"}
        result = match_skill("ppt", defn, "帮我做个PPT", str(tmp_path))
        assert result is not None
        assert result["score"] > 0
        assert "keywords" in result["dims"][0]

    def test_multiple_keywords(self, tmp_path):
        defn = {"keywords": ["画图", "火山图", "plot"], "priority": 10, "hint": "test"}
        result = match_skill("sci-fig", defn, "帮我画一个火山图", str(tmp_path))
        assert result is not None
        assert result["score"] >= 10  # 至少 1 个关键词命中（"火山图"含"画图"取决于匹配方式）

    def test_negative_keyword_blocks(self, tmp_path):
        defn = {"keywords": ["PPT"], "negative_keywords": ["excel", "表格"], "priority": 10, "hint": "test"}
        result = match_skill("ppt", defn, "帮我做个excel表格", str(tmp_path))
        assert result is None

    def test_no_keyword_match(self, tmp_path):
        defn = {"keywords": ["PPT", "幻灯片"], "priority": 10, "hint": "test"}
        result = match_skill("ppt", defn, "解释一下这段代码", str(tmp_path))
        assert result is None

    def test_file_pattern_adds_score(self, tmp_path):
        # Create a matching file
        (tmp_path / "test.pptx").touch()
        defn = {"keywords": ["PPT"], "file_patterns": ["*.pptx"], "priority": 10, "hint": "test"}
        result = match_skill("ppt", defn, "帮我做PPT", str(tmp_path))
        assert result is not None
        assert any("file:" in d for d in result["dims"])

    def test_requires_files_missing_reduces_score(self, tmp_path):
        defn = {"keywords": ["交付", "打包"], "requires_files": ["plan.md"], "priority": 10, "hint": "test"}
        result = match_skill("deliver", defn, "帮我打包交付", str(tmp_path))
        # 关键词命中但 requires_files 缺失会降分
        if result is not None:
            assert any("missing:" in d for d in result["dims"])

    def test_requires_files_present(self, tmp_path):
        (tmp_path / "plan.md").write_text("# Plan")
        defn = {"keywords": ["交付"], "requires_files": ["plan.md"], "priority": 10, "hint": "test"}
        result = match_skill("deliver", defn, "帮我交付", str(tmp_path))
        assert result is not None
        assert all("missing:" not in d for d in result["dims"])

    def test_priority_preserved(self, tmp_path):
        defn = {"keywords": ["test"], "priority": 42, "hint": "test"}
        result = match_skill("x", defn, "run test", str(tmp_path))
        assert result["priority"] == 42

    def test_case_insensitive(self, tmp_path):
        defn = {"keywords": ["PPT"], "priority": 10, "hint": "test"}
        result = match_skill("ppt", defn, "帮我做个ppt", str(tmp_path))
        assert result is not None
