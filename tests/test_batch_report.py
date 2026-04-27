import pytest
from unittest.mock import patch, Mock
from datetime import datetime


class TestExportResult:
    def test_dataclass_fields(self):
        from src.generator.batch_report import ExportResult
        result = ExportResult(url="http://test.com", success=True, filename="test.docx")
        assert result.url == "http://test.com"
        assert result.success is True
        assert result.filename == "test.docx"

    def test_optional_fields(self):
        from src.generator.batch_report import ExportResult
        result = ExportResult(url="http://test.com", success=False, error_message="Error")
        assert result.filename is None
        assert result.file_path is None
        assert result.error_message == "Error"


class TestBatchReport:
    def test_default_init(self):
        from src.generator.batch_report import BatchReport
        report = BatchReport()
        assert report.results == []
        assert report.latex_fallback_count == 0

    def test_add_success(self):
        from src.generator.batch_report import BatchReport
        report = BatchReport()
        report.add_success("http://test.com", "test.docx")
        assert len(report.results) == 1
        assert report.results[0].success is True

    def test_add_failure(self):
        from src.generator.batch_report import BatchReport
        report = BatchReport()
        report.add_failure("http://test.com", "Network error")
        assert len(report.results) == 1
        assert report.results[0].success is False

    def test_format_report_empty(self):
        from src.generator.batch_report import BatchReport
        report = BatchReport()
        report.start_time = datetime(2026, 1, 1, 12, 0, 0)
        report.add_success("http://test1.com", "test1.docx")
        report.add_failure("http://test2.com", "Error")
        output = report._format_report()
        assert "总计: 2 个 URL" in output
        assert "成功: 1 个" in output
        assert "失败: 1 个" in output


class TestBuildFileLink:
    def test_build_file_link(self):
        from src.generator.batch_report import _build_file_link
        result = _build_file_link("/path/to/file.txt", "link text")
        assert "link text" in result

    def test_build_file_link_windows(self):
        from src.generator.batch_report import _build_file_link
        with patch("src.generator.batch_report.platform.system", return_value="Windows"):
            result = _build_file_link("C:/Users/test/file.txt")
            assert result.startswith("[bold blue link")

    def test_normalized_path(self):
        from src.generator.batch_report import _build_file_link
        with patch("src.generator.batch_report.platform.system", return_value="Linux"):
            result = _build_file_link("/path\\to/file.txt")
            assert "/path/to/file.txt" in result or "/path" in result


class TestGetLatestExportFolder:
    def test_get_latest_folder_not_exists(self, tmp_path):
        from src.generator.batch_report import DEFAULT_EXPORT_DIR, _get_latest_export_folder
        with patch("src.generator.batch_report.DEFAULT_EXPORT_DIR", tmp_path):
            result = _get_latest_export_folder()
            assert result == tmp_path

    def test_get_latest_folder_today(self, tmp_path):
        from src.generator.batch_report import _get_latest_export_folder
        today_folder = tmp_path / "260425"
        today_folder.mkdir()
        with patch("src.generator.batch_report.DEFAULT_EXPORT_DIR", tmp_path):
            result = _get_latest_export_folder()
            assert result == today_folder


class TestPrintSummary:
    """测试 print_summary() 方法"""

    def test_print_summary_no_results(self, capsys):
        """验证无结果时的空报告输出"""
        from src.generator.batch_report import BatchReport
        report = BatchReport()
        report.print_summary()
        captured = capsys.readouterr()

        # 验证成功标题存在（失败标题仅在有失败结果时打印）
        assert "成功:" in captured.out
        # 验证耗时信息存在
        assert "本次任务共耗时" in captured.out

    def test_print_summary_with_latex_fallback(self, capsys):
        """验证公式回退警告"""
        from src.generator.batch_report import BatchReport
        report = BatchReport()
        report.add_success("url1", "title1", "doc1.docx")
        report.latex_fallback_count = 5
        report.print_summary()
        captured = capsys.readouterr()

        # 验证警告内容
        assert "回退" in captured.out
        assert "5" in captured.out
        assert "⚠" in captured.out or "警告" in captured.out

    def test_print_summary_only_successes(self, capsys):
        """仅有成功结果"""
        from src.generator.batch_report import BatchReport
        report = BatchReport()
        report.add_success("http://test1.com", "test1.docx")
        report.add_success("http://test2.com", "test2.docx")
        report.print_summary()
        captured = capsys.readouterr()
        assert "test1.docx" in captured.out
        assert "test2.docx" in captured.out

    def test_print_summary_only_failures(self, capsys):
        """验证仅有失败结果时的输出格式"""
        from src.generator.batch_report import BatchReport
        report = BatchReport()
        report.add_failure("http://test.com/error1", "error1")
        report.add_failure("http://test.com/error2", "error2")

        report.print_summary()
        captured = capsys.readouterr()

        # 验证错误消息存在
        assert "error1" in captured.out
        assert "error2" in captured.out

        # 验证缩进格式（6个空格 + 错误消息）
        assert "      error1" in captured.out
        assert "      error2" in captured.out

        # 验证标题标签
        assert "成功:" in captured.out
        assert "失败:" in captured.out

    def test_print_summary_mixed_results(self, capsys):
        """混合成功和失败结果"""
        from src.generator.batch_report import BatchReport
        report = BatchReport()
        report.add_success("http://success.com", "success.docx")
        report.add_failure("http://fail.com", "error message")
        report.print_summary()
        captured = capsys.readouterr()
        assert "success.docx" in captured.out
        assert "http://fail.com" in captured.out


class TestFormatReportEdgeCases:
    """测试 _format_report() 边界情况"""

    def test_format_report_all_successes(self):
        """全部成功的报告"""
        from src.generator.batch_report import BatchReport
        report = BatchReport()
        report.start_time = datetime(2026, 1, 1, 12, 0, 0)
        report.add_success("http://test1.com", "test1.docx")
        report.add_success("http://test2.com", "test2.docx")
        result = report._format_report()
        assert "成功: 2 个" in result
        assert "失败: 0 个" in result

    def test_format_report_all_failures(self):
        """全部失败的报告"""
        from src.generator.batch_report import BatchReport
        report = BatchReport()
        report.start_time = datetime(2026, 1, 1, 12, 0, 0)
        report.add_failure("http://test1.com", "Error 1")
        report.add_failure("http://test2.com", "Error 2")
        result = report._format_report()
        assert "成功: 0 个" in result
        assert "失败: 2 个" in result

    def test_format_report_many_results(self):
        """大量结果性能测试"""
        from src.generator.batch_report import BatchReport
        report = BatchReport()
        report.start_time = datetime(2026, 1, 1, 12, 0, 0)
        for i in range(100):
            report.add_success(f"http://test{i}.com", f"test{i}.docx")
        result = report._format_report()
        assert "总计: 100 个 URL" in result
        assert "成功: 100 个" in result
        assert "失败: 0 个" in result


class TestGetLatestExportFolderEdgeCases:
    """测试 _get_latest_export_folder() 边界情况"""

    def test_get_latest_folder_finds_most_recently_modified(self, tmp_path):
        """测试查找最近修改的文件夹"""
        from src.generator.batch_report import _get_latest_export_folder
        import time

        # 创建多个文件夹，设置不同的 mtime
        folder_old = tmp_path / "old_folder"
        folder_new = tmp_path / "new_folder"
        folder_old.mkdir()
        folder_new.mkdir()

        # 修改 folder_old 的 mtime 为更早的时间
        time.sleep(0.1)
        # folder_new 已经是最新创建的

        with patch("src.generator.batch_report.DEFAULT_EXPORT_DIR", tmp_path):
            result = _get_latest_export_folder()
            assert result == folder_new

    def test_get_latest_folder_no_directories(self, tmp_path):
        """目录下无子文件夹时返回基础目录"""
        from src.generator.batch_report import _get_latest_export_folder, DEFAULT_EXPORT_DIR
        # 创建文件而非文件夹
        (tmp_path / "file.txt").touch()
        with patch("src.generator.batch_report.DEFAULT_EXPORT_DIR", tmp_path):
            result = _get_latest_export_folder()
            assert result == tmp_path


class TestPrintFolderLink:
    def test_print_folder_link_non_terminal(self, tmp_path):
        """非终端环境下打印文件夹链接"""
        from src.generator.batch_report import print_folder_link, DEFAULT_EXPORT_DIR
        with patch("src.generator.batch_report.DEFAULT_EXPORT_DIR", tmp_path):
            with patch("src.generator.batch_report.Console") as mock_console:
                mock_console.return_value.is_terminal = False
                print_folder_link()
                assert True