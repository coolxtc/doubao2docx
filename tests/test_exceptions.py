import pytest
from src.exceptions import DoubaoExportError, CrawlerError, ParseError, ExportError


class TestDoubaoExportError:
    """测试基础异常类"""

    def test_init_with_message_only(self):
        """仅传入消息时"""
        error = DoubaoExportError("测试错误")
        assert str(error) == "测试错误"
        assert error.cause is None

    def test_init_with_cause(self):
        """传入消息和原始异常"""
        original = ValueError("原始错误")
        error = DoubaoExportError("转换错误", cause=original)
        assert str(error) == "转换错误"
        assert error.cause == original

    def test_is_exception_subclass(self):
        """验证继承关系"""
        assert issubclass(DoubaoExportError, Exception)


class TestCrawlerError:
    """测试爬虫错误类"""

    def test_is_export_error_subclass(self):
        """验证继承自 DoubaoExportError"""
        assert issubclass(CrawlerError, DoubaoExportError)

    def test_can_be_raised(self):
        """验证可以抛出"""
        with pytest.raises(CrawlerError):
            raise CrawlerError("爬虫失败")


class TestParseError:
    """测试解析错误类"""

    def test_is_export_error_subclass(self):
        """验证继承自 DoubaoExportError"""
        assert issubclass(ParseError, DoubaoExportError)

    def test_can_be_raised(self):
        """验证可以抛出"""
        with pytest.raises(ParseError):
            raise ParseError("解析失败")


class TestExportError:
    """测试导出错误类"""

    def test_is_export_error_subclass(self):
        """验证继承自 DoubaoExportError"""
        assert issubclass(ExportError, DoubaoExportError)

    def test_can_be_raised(self):
        """验证可以抛出"""
        with pytest.raises(ExportError):
            raise ExportError("导出失败")