"""
HTML 解析模块

负责将 HTML 内容解析为结构化的 TextBlock[] 数据。

模块架构：
- BaseParser: 解析器抽象基类，定义统一接口
- DoubaoHTMLParser: 豆包平台的 HTML 解析器实现
- PlatformConfig: 平台配置数据类
- TextBlock: 内容块数据结构
- InlineContent: 内联内容数据结构
- TableData: 表格数据结构
- ParsedPage: 解析后的页面数据

解析流程：
HTML → BeautifulSoup → BaseParser._parse_impl() → TextBlock[]
"""

from .base import BaseParser, PlatformConfig, TableData, InlineContent, TextBlock, ParsedPage
from .doubao_parser import DoubaoHTMLParser
from ..exceptions import ParseError

__all__ = [
    "BaseParser",
    "PlatformConfig",
    "DoubaoHTMLParser",
    "TableData",
    "InlineContent",
    "TextBlock",
    "ParsedPage",
    "ParseError",
]
