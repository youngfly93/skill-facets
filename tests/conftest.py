"""Shared fixtures for skill-facets tests."""
import os
import sys
import pytest

# 项目根 = tests/ 的父目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAUDE_DIR = os.path.join(PROJECT_ROOT, ".claude")
SCRIPTS_DIR = os.path.join(CLAUDE_DIR, "scripts")

# 让所有测试能 import .claude/scripts/ 下的模块
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
    return os.path.join(CLAUDE_DIR, "skills.yaml")


@pytest.fixture
def example_figures_dir():
    return os.path.join(PROJECT_ROOT, "examples", "real_project", "figures")


@pytest.fixture
def example_reports_dir():
    return os.path.join(PROJECT_ROOT, "examples", "real_project", "reports")


@pytest.fixture(autouse=True)
def clear_manifest_cache():
    """每个测试前清除 manifest 缓存。"""
    from manifest import _cache
    _cache.clear()
    yield
    _cache.clear()
