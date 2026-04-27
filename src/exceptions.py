"""项目异常定义"""

from typing import Optional


class DoubaoExportError(Exception):
    """基础异常类，保留错误链便于调试"""

    def __init__(self, message: str, cause: Optional[Exception] = None):
        """
        初始化异常

        Args:
            message: 错误消息
            cause: 原始异常（可选）
        """
        super().__init__(message)
        self.cause = cause


class CrawlerError(DoubaoExportError):
    """爬虫相关错误"""


class ParseError(DoubaoExportError):
    """解析相关错误"""


class ExportError(DoubaoExportError):
    """导出相关错误"""
