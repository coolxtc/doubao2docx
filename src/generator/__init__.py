"""
Docx 生成模块

负责将解析后的内容块转换为 Word 文档（.docx 格式）。

模块架构：
- DocxBuilder: 核心文档构建器
- DocumentConfig: 文档配置
- LaTeXConverter: LaTeX 公式转换器
- DocNamer: 文档命名和序号管理
- LinkRecord: 链接记录数据结构
"""

from .docx_builder import DocxBuilder, DocumentConfig
from .latex_converter import LaTeXConverter
from .doc_namer import DocNamer, LinkRecord

__all__ = ["DocxBuilder", "DocumentConfig", "LaTeXConverter", "DocNamer", "LinkRecord"]