"""Test constraint validators: checkers + CLI integration."""
import os
import pytest
from PIL import Image


@pytest.fixture
def white_png(tmp_path):
    """创建一个白底 300DPI PNG。"""
    img = Image.new('RGB', (100, 100), (255, 255, 255))
    path = tmp_path / "white.png"
    img.save(str(path), dpi=(300, 300))
    return str(path)


@pytest.fixture
def gray_png(tmp_path):
    """创建一个灰底 72DPI PNG。"""
    img = Image.new('RGB', (100, 100), (200, 200, 200))
    path = tmp_path / "gray.png"
    img.save(str(path), dpi=(72, 72))
    return str(path)


@pytest.fixture
def sample_csv(tmp_path):
    """创建一个 CSV 文件。"""
    path = tmp_path / "data.csv"
    path.write_text("a,b\n1,2\n")
    return str(path)


class TestColorChecker:
    def test_white_background_passes(self, white_png):
        from checkers.color_checker import check
        r = check("color", {"expected_color": "#FFFFFF"}, [white_png])
        assert r["passed"] is True

    def test_gray_background_fails(self, gray_png):
        from checkers.color_checker import check
        r = check("color", {"expected_color": "#FFFFFF"}, [gray_png])
        assert r["passed"] is False
        assert len(r["violations"]) > 0


class TestDpiChecker:
    def test_300dpi_passes(self, white_png):
        from checkers.dpi_checker import check
        r = check("dpi", {"min_dpi": 300}, [white_png])
        assert r["passed"] is True

    def test_72dpi_fails(self, gray_png):
        from checkers.dpi_checker import check
        r = check("dpi", {"min_dpi": 300}, [gray_png])
        assert r["passed"] is False
        assert "72" in r["violations"][0]["issue"]


class TestFormatChecker:
    def test_png_in_allowed(self, white_png):
        from checkers.format_checker import check
        r = check("format", {"allowed": [".png", ".pdf"]}, [white_png])
        assert r["passed"] is True

    def test_csv_not_in_allowed(self, sample_csv):
        from checkers.format_checker import check
        r = check("format", {"allowed": [".png", ".pdf"]}, [sample_csv])
        assert r["passed"] is False

    def test_empty_allowed_list(self, white_png):
        from checkers.format_checker import check
        r = check("format", {"allowed": []}, [white_png])
        assert r["passed"] is None


class TestContentChecker:
    def test_no_markdown_clean(self, tmp_path):
        from checkers.content_checker import check
        # 创建一个干净的 docx（最小 ZIP）
        import zipfile
        docx = tmp_path / "clean.docx"
        with zipfile.ZipFile(str(docx), 'w') as z:
            z.writestr("word/document.xml",
                       '<w:document><w:body><w:p><w:r><w:t>正常文本内容</w:t></w:r></w:p></w:body></w:document>')
        r = check("no_markdown", {}, [str(docx)])
        assert r["passed"] is True

    def test_no_markdown_dirty(self, tmp_path):
        from checkers.content_checker import check
        import zipfile
        docx = tmp_path / "dirty.docx"
        with zipfile.ZipFile(str(docx), 'w') as z:
            z.writestr("word/document.xml",
                       '<w:document><w:body><w:p><w:r><w:t>**加粗** 和 ## 标题</w:t></w:r></w:p></w:body></w:document>')
        r = check("no_markdown", {}, [str(docx)])
        assert r["passed"] is False

    def test_numbering_sequential(self, tmp_path):
        from checkers.content_checker import check
        import zipfile
        docx = tmp_path / "numbered.docx"
        with zipfile.ZipFile(str(docx), 'w') as z:
            # 每个编号出现至少 2 次（标题 + 正文引用）
            z.writestr("word/document.xml",
                       '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                       '<w:p><w:r><w:t>如图 1 所示，结果显著</w:t></w:r></w:p>'
                       '<w:p><w:r><w:t>图 1 PCA 散点图</w:t></w:r></w:p>'
                       '<w:p><w:r><w:t>图 2 展示了差异基因</w:t></w:r></w:p>'
                       '<w:p><w:r><w:t>图 2 火山图</w:t></w:r></w:p>'
                       '</w:body></w:document>')
        r = check("numbering", {}, [str(docx)])
        assert r["passed"] is True

    def test_numbering_gap(self, tmp_path):
        from checkers.content_checker import check
        import zipfile
        docx = tmp_path / "gap.docx"
        with zipfile.ZipFile(str(docx), 'w') as z:
            z.writestr("word/document.xml",
                       '<w:document><w:body>'
                       '<w:p><w:r><w:t>图 1 结果</w:t></w:r></w:p>'
                       '<w:p><w:r><w:t>图 3 分析</w:t></w:r></w:p>'
                       '</w:body></w:document>')
        r = check("numbering", {}, [str(docx)])
        assert r["passed"] is False


class TestValidatorCLI:
    """Integration tests for cli.py via skills.yaml contract."""

    def test_sci_fig_validation(self, project_root, example_figures_dir):
        """sci-fig 验证应从 skills.yaml 读取 contract。"""
        import subprocess
        cli = os.path.join(project_root, ".claude", "scripts", "constraint_validator", "cli.py")
        result = subprocess.run(
            ["python3", cli, "sci-fig", example_figures_dir],
            capture_output=True, text=True, cwd=project_root
        )
        import json
        report = json.loads(result.stdout)
        assert report.get("source", "").endswith("skills.yaml")
        assert report["total"] >= 3
        assert "hard_fail" in report

    def test_nonexistent_skill_errors(self, project_root):
        import subprocess
        cli = os.path.join(project_root, ".claude", "scripts", "constraint_validator", "cli.py")
        result = subprocess.run(
            ["python3", cli, "nonexistent-xyz"],
            capture_output=True, text=True, cwd=project_root
        )
        import json
        report = json.loads(result.stdout)
        assert "error" in report
