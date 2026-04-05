"""Shared fixtures for skill-facets tests."""
import os
import sys
import shutil
import pytest

# 项目根 = tests/ 的父目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAUDE_DIR = os.path.join(PROJECT_ROOT, ".claude")
SCRIPTS_DIR = os.path.join(CLAUDE_DIR, "scripts")
FRAMEWORK_DIR = os.path.join(PROJECT_ROOT, "framework")
BIO_EXAMPLE = os.path.join(PROJECT_ROOT, "examples", "bioinformatics")

# 让测试能 import 模块
sys.path.insert(0, FRAMEWORK_DIR)
sys.path.insert(0, os.path.join(FRAMEWORK_DIR, "constraint_validator"))
sys.path.insert(0, SCRIPTS_DIR)
sys.path.insert(0, os.path.join(SCRIPTS_DIR, "constraint_validator"))


@pytest.fixture
def project_root():
    return PROJECT_ROOT


@pytest.fixture
def claude_dir():
    return CLAUDE_DIR


@pytest.fixture
def skills_yaml_path():
    """测试用 skills.yaml — 使用生信示例（含完整 contract）。"""
    return os.path.join(BIO_EXAMPLE, "skills.yaml")


@pytest.fixture
def example_figures_dir():
    return os.path.join(BIO_EXAMPLE, "real_project", "figures")


@pytest.fixture
def example_reports_dir():
    return os.path.join(BIO_EXAMPLE, "real_project", "reports")


@pytest.fixture(autouse=True)
def use_bio_example_manifest(tmp_path):
    """测试期间临时将生信 skills.yaml 复制到 .claude/ 中，使 manifest 能找到。"""
    from manifest import _cache
    _cache.clear()

    bio_yaml = os.path.join(BIO_EXAMPLE, "skills.yaml")
    claude_yaml = os.path.join(CLAUDE_DIR, "skills.yaml")
    backup = None

    if os.path.exists(bio_yaml):
        # 备份当前空模板
        if os.path.exists(claude_yaml):
            backup = str(tmp_path / "skills.yaml.bak")
            shutil.copy2(claude_yaml, backup)
        # 用生信示例替换
        shutil.copy2(bio_yaml, claude_yaml)

    yield

    # 恢复空模板
    _cache.clear()
    if backup and os.path.exists(backup):
        shutil.copy2(backup, claude_yaml)
    elif os.path.exists(claude_yaml) and os.path.exists(bio_yaml):
        # 写回空模板
        template = os.path.join(PROJECT_ROOT, "templates", "skills.yaml.template")
        if os.path.exists(template):
            shutil.copy2(template, claude_yaml)
