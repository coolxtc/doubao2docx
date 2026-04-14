"""自定义异常类模块"""

from typing import Optional


class DoubaoExportError(Exception):
    def __init__(self, message: str, cause: Optional[Exception] = None):
        super().__init__(message)
        self.cause = cause


class CrawlerError(DoubaoExportError):
    """爬虫相关错误"""
    pass


class ParseError(DoubaoExportError):
    """解析相关错误"""
    pass


class ExportError(DoubaoExportError):
    """导出相关错误"""
    pass