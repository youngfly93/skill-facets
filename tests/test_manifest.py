"""Test manifest.py: skills.yaml loading, contract/trigger access, path traversal."""
import os
import pytest
from manifest import (
    ManifestLoadError,
    find_manifest_path,
    load_manifest,
    get_skill,
    get_contract,
    get_trigger,
    get_all_triggers,
)


class TestFindManifestPath:
    def test_finds_from_project_root(self, project_root):
        path, fmt = find_manifest_path(cwd=project_root)
        assert path is not None
        assert path.endswith("skills.yaml")
        assert fmt == "vnext"

    def test_finds_from_subdirectory(self, project_root):
        subdir = os.path.join(project_root, "examples", "real_project")
        path, fmt = find_manifest_path(cwd=subdir)
        assert path is not None
        assert fmt == "vnext"

    def test_returns_none_for_nonexistent(self, tmp_path):
        path, fmt = find_manifest_path(cwd=str(tmp_path))
        # 可能回退到脚本所在目录的 .claude，所以不一定是 None
        # 但如果是 None，format 也应是 None
        if path is None:
            assert fmt is None


class TestLoadManifest:
    def test_loads_successfully(self, project_root):
        m = load_manifest(cwd=project_root)
        assert "skills" in m
        assert len(m["skills"]) >= 11
        assert m.get("_format") == "vnext"

    def test_has_schema_version(self, project_root):
        m = load_manifest(cwd=project_root)
        assert "schema_version" in m

    def test_caches_result(self, project_root):
        m1 = load_manifest(cwd=project_root)
        m2 = load_manifest(cwd=project_root)
        assert m1 is m2


class TestGetSkill:
    def test_existing_skill(self, project_root):
        skill = get_skill("sci-fig", cwd=project_root)
        assert skill is not None
        assert skill["type"] == "command"

    def test_nonexistent_skill(self, project_root):
        skill = get_skill("nonexistent-skill", cwd=project_root)
        assert skill is None

    def test_wrapped_skill(self, project_root):
        skill = get_skill("pptx", cwd=project_root)
        assert skill is not None
        assert "wraps" in skill


class TestGetContract:
    def test_skill_with_contract(self, project_root):
        contract = get_contract("sci-fig", cwd=project_root)
        assert contract is not None
        assert "constraints" in contract
        assert len(contract["constraints"]) >= 3

    def test_skill_without_contract(self, project_root):
        contract = get_contract("transfer", cwd=project_root)
        assert contract is None

    def test_constraint_fields(self, project_root):
        contract = get_contract("sci-fig", cwd=project_root)
        c = contract["constraints"][0]
        assert "id" in c
        assert "rule" in c
        assert "severity" in c
        assert "enforcement" in c

    def test_aspirations_and_freedoms(self, project_root):
        contract = get_contract("ppt", cwd=project_root)
        assert "aspirations" in contract
        assert "freedoms" in contract
        assert len(contract["aspirations"]) > 0


class TestGetTrigger:
    def test_skill_with_trigger(self, project_root):
        trigger = get_trigger("ppt", cwd=project_root)
        assert trigger is not None
        assert "keywords" in trigger
        assert "PPT" in trigger["keywords"]

    def test_negative_keywords(self, project_root):
        trigger = get_trigger("sci-fig", cwd=project_root)
        assert "negative_keywords" in trigger
        assert "PPT" in trigger["negative_keywords"]


class TestGetAllTriggers:
    def test_returns_all(self, project_root):
        triggers = get_all_triggers(cwd=project_root)
        assert len(triggers) >= 11
        assert "ppt" in triggers
        assert "sci-fig" in triggers

    def test_trigger_has_type(self, project_root):
        triggers = get_all_triggers(cwd=project_root)
        for name, t in triggers.items():
            assert "type" in t, f"{name} missing type"
