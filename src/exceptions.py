"""
自定义异常类模块

定义项目专用的异常类，用于区分不同阶段的错误：
- 爬虫阶段：网络超时、页面加载失败等
- 解析阶段：HTML 结构不匹配、解析错误等
- 导出阶段：文件写入失败、pandoc 调用失败等

异常继承关系：
DoubaoExportError (基类)
├── CrawlerError (爬虫相关)
├── ParseError (解析相关)
└── ExportError (导出相关)
"""

from typing import Optional


class DoubaoExportError(Exception):
    """
    基础异常类

    所有自定义异常的基类，提供错误消息和可选的原始异常。
    这样做的好处是可以保留完整的错误链，便于调试。

    Attributes:
        message: 错误消息，描述发生了什么问题
        cause: 原始异常，如果错误是由另一个异常引起的
    """
    def __init__(self, message: str, cause: Optional[Exception] = None):
        """
        初始化异常

        Args:
            message: 错误消息，描述问题
            cause: 原始异常（可选），用于保留错误链
        """
        super().__init__(message)
        self.cause = cause


class CrawlerError(DoubaoExportError):
    """爬虫阶段错误 - 网页访问、元素定位、滚动加载等操作失败时抛出"""
    pass


class ParseError(DoubaoExportError):
    """解析阶段错误 - HTML 内容解析、结构提取等操作失败时抛出"""
    pass


class ExportError(DoubaoExportError):
    """导出阶段错误 - Word 文档生成、文件保存等操作失败时抛出"""
    pass