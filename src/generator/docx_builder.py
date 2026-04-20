"""
Word文档构建器模块

将解析后的内容块转换为 Word 文档（.docx 格式）。
使用 python-docx 库创建和编辑 Word 文档。

主要功能：
- 创建文档并设置基础样式（页边距、字体）
- 添加标题、段落、列表
- 插入代码块（带灰色背景）
- 插入表格
- 插入数学公式（通过 pandoc 转换为 OMML）
- 添加引用块

支持的内容块类型：
- paragraph: 普通段落
- heading: 标题
- code: 代码块
- latex: 数学公式
- table: 表格
- blockquote: 引用
- list_item: 列表项

核心概念：
- python-docx: Python 操作 Word 文档的库
- OMML: Office Math Markup Language，Word 的内置公式格式
- pandoc: 文档格式转换工具，可将 LaTeX 转换为 Word 公式

依赖：
- pip install python-docx
- brew install pandoc（用于公式转换）
"""

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Optional
from xml.etree import ElementTree as etree

from copy import deepcopy
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml.ns import qn
from docx.oxml import parse_xml

from ..preprocessor import TextBlock, TableData, InlineContent
from ..preprocessor.base import BaseParser as _BaseParser
from ..config import DocumentStyleConfig
from ..exceptions import ExportError
from .latex_converter import LaTeXConverter


@dataclass
class DocumentConfig:
    """
    文档配置 - 定义 Word 文档的样式和属性

    属性说明：
    - title: 文档标题（会显示在生成的文档中）
    - author: 文档作者（Word 文档元数据）
    - margin_left/right/top/bottom: 页边距（英寸）
    - font_name: 正文字体名称
    - font_size: 正文字号（磅）
    - style_config: 样式配置（标题字号、代码字号等）
    """
    title: str = "豆包聊天记录"
    author: str = "Doubao Export"
    margin_left: float = 1.0
    margin_right: float = 1.0
    margin_top: float = 1.0
    margin_bottom: float = 1.0
    font_name: str = "微软雅黑"
    font_size: int = 12
    style_config: DocumentStyleConfig = None

    def __post_init__(self):
        if self.style_config is None:
            self.style_config = DocumentStyleConfig()


class DocxBuilder:
    """
    Word文档构建器 - 将内容块转换为 Word 文档

    这是核心的文档生成类。
    接收解析后的内容块列表，逐个处理并添加到 Word 文档中。

    工作流程：
    1. 创建 Document 对象
    2. 设置页面边距和默认字体
    3. 遍历内容块，根据类型调用相应方法
    4. 保存为 .docx 文件

    支持的内容块类型：
    - paragraph: 普通段落
    - heading: 标题
    - code: 代码块
    - latex: 数学公式
    - table: 表格
    - blockquote: 引用
    - list_item: 列表项
    """

    def __init__(self, config: Optional[DocumentConfig] = None) -> None:
        """
        初始化文档构建器

        Args:
            config: 文档配置，如果为 None 则使用默认配置
        """
        self.config = config or DocumentConfig()
        self.document = Document()
        self.latex_converter = LaTeXConverter()
        self._setup_document()

        # 列表状态追踪（用于有序列表序号）
        self._last_list_type = None
        self._last_list_level = 0
        self._list_counter = 0

        # 从配置读取 pandoc 超时时间
        from ..config import get_config
        self._pandoc_timeout = get_config().pandoc.timeout

    def _setup_document(self) -> None:
        """设置文档基础样式 - 页边距和默认字体"""
        section = self.document.sections[0]
        section.top_margin = Inches(self.config.margin_top)
        section.bottom_margin = Inches(self.config.margin_bottom)
        section.left_margin = Inches(self.config.margin_left)
        section.right_margin = Inches(self.config.margin_right)

        # 设置默认字体
        style = self.document.styles["Normal"]
        style.font.name = self.config.font_name
        style.font.size = Pt(self.config.font_size)

    def _set_run_font(self, run) -> None:
        """
        设置字体 - 包括中文字体

        python-docx 设置中文字体需要特殊处理：
        1. 设置常规字体名（font.name）
        2. 通过 rPr.rFonts 设置东亚字体（w:eastAsia）
        """
        run.font.name = self.config.font_name
        run.font.size = Pt(self.config.font_size)
        try:
            run._element.rPr.rFonts.set(qn('w:eastAsia'), self.config.font_name)
        except (AttributeError, TypeError):
            pass

    def _add_title(self, title: str) -> None:
        """添加文档标题 - 居中显示的 h1 标题"""
        heading = self.document.add_heading(title, level=1)
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in heading.runs:
            run.font.size = Pt(self.config.style_config.title_font_size)
            run.font.bold = True
            run.font.color.rgb = RGBColor(0, 0, 0)
            self._set_run_font(run)

    def _add_paragraph(self, text: str, style: Optional[str] = None) -> None:
        """添加普通段落"""
        para = self.document.add_paragraph(text, style=style)
        for run in para.runs:
            self._set_run_font(run)

    def build_blocks(
        self,
        title: str,
        blocks: list[tuple[str, "TextBlock"]],
        output_path: str,
    ) -> str:
        """
        从文本块构建文档 - 主方法

        Args:
            title: 文档标题
            blocks: 内容块列表，每个元素是 (角色, TextBlock) 元组
                    角色可以是 "user"（用户）或 "assistant"（AI）
            output_path: 输出文件路径

        Returns:
            输出文件的完整路径
        """
        self._add_title(title)

        # 重置列表状态
        self._list_counter = 0
        self._last_list_type = None
        self._last_list_level = 0

        current_role = ""
        for role, block in blocks:
            # 切换角色时添加角色标签（用户/豆包）
            if role != current_role:
                current_role = role
                role_label = "用户" if role == "user" else "豆包"
                heading = self.document.add_heading(f"{role_label}", level=3)
                for run in heading.runs:
                    run.font.color.rgb = RGBColor(0, 0, 0)
                    self._set_run_font(run)

            self._add_text_block(block)

        self.document.save(output_path)
        return output_path

    def _add_text_block(self, block: "TextBlock") -> None:
        """
        添加文本块 - 根据块类型分发处理

        这是主要的分发逻辑，根据 TextBlock.type 调用相应的添加方法。
        """
        if block.type == "latex":
            self._add_latex(block.content, is_display=(block.language == "display"), as_standalone=True)
        elif block.type == "code":
            self._add_code_block(block.content, block.language)
        elif block.type == "heading":
            level = int(block.language) if block.language else 3
            heading = self.document.add_heading(block.content, level=min(level, 6))
            for run in heading.runs:
                run.font.color.rgb = RGBColor(0, 0, 0)
                self._set_run_font(run)
        elif block.type == "list":
            self._add_list(block.content, block.language)
        elif block.type == "list_item":
            self._add_list_item(block)
        elif block.type == "table":
            self._add_table(block.data)
        elif block.type == "blockquote":
            self._add_blockquote(block.content)
        elif block.type == "paragraph" and block.items:
            # 包含内联内容（文本和公式混合）的段落
            self._add_inline_content(block.items)
        else:
            # 普通段落
            content = block.content.rstrip("\n") if block.content else ""
            if content:
                self._add_paragraph(content)

    def _add_list_item(self, block: "TextBlock") -> None:
        """
        添加列表项

        处理有序列表（ol）和无序列表（ul）两种类型。
        有序列表需要维护全局计数器。
        """
        list_type = block.language if block.language in ("ul", "ol") else "ul"
        level = getattr(block, 'level', 0)

        if block.items:
            # 包含内联内容的列表项（如加粗文本、公式）
            if list_type == "ol":
                if self._last_list_type != "ol" or self._last_list_level != level:
                    self._list_counter = 0
                self._list_counter += 1
                start_index = self._list_counter
                self._last_list_type = "ol"
                self._last_list_level = level
            else:
                start_index = 1
                self._last_list_type = "ul"
                self._last_list_level = level
            self._add_inline_content(block.items, list_type, start_index, level)
        else:
            # 纯文本列表项
            if list_type == "ol":
                if self._last_list_type != "ol" or self._last_list_level != level:
                    self._list_counter = 0
                self._list_counter += 1
                self._last_list_type = "ol"
                self._last_list_level = level
                para = self.document.add_paragraph()
                run = para.add_run(f"{self._list_counter}. {block.content}")
                self._set_run_font(run)
            else:
                self._last_list_type = "ul"
                self._last_list_level = level
                para = self.document.add_paragraph(block.content, style="List Bullet")
                for run in para.runs:
                    self._set_run_font(run)

            # 嵌套列表需要增加缩进
            if level > 0:
                para.paragraph_format.left_indent = Inches(level * 0.5)

    def _add_inline_content(self, items: list[InlineContent], list_type: Optional[str] = None, start_index: int = 1, level: int = 0) -> None:
        if not items:
            return

        para = self._create_inline_paragraph(list_type, start_index, level)
        last_run = None
        prev_was_latex = False
        for item in items:
            if item.type == "text":
                if item.content == "\n" and (prev_was_latex or last_run is None):
                    para.add_run("").add_break(WD_BREAK.LINE)
                    prev_was_latex = False
                    continue
                parts = item.content.split("\n")
                for i, part in enumerate(parts):
                    if i > 0 and last_run:
                        last_run.add_break(WD_BREAK.LINE)
                    if part:
                        run = para.add_run(part)
                        self._set_run_font(run)
                        if item.bold:
                            run.font.bold = True
                        if item.italic:
                            run.font.italic = True
                        last_run = run
                prev_was_latex = False
            elif item.type == "latex":
                if item.is_display:
                    self._add_latex(item.content, is_display=True, as_standalone=True)
                    para = self._create_inline_paragraph(list_type, start_index, level)
                else:
                    self._add_latex_to_paragraph(para, item.content, is_display=False, as_standalone=False)
                last_run = None
                prev_was_latex = True

    def _create_inline_paragraph(self, list_type: Optional[str], start_index: int, level: int):
        if list_type == "ol":
            para = self.document.add_paragraph()
            run = para.add_run(f"{start_index}. ")
            self._set_run_font(run)
        elif list_type == "ul":
            para = self.document.add_paragraph(style="List Bullet")
        else:
            para = self.document.add_paragraph()
        if level > 0:
            para.paragraph_format.left_indent = Inches(level * 0.5)
        return para

    def _add_latex(self, latex: str, is_display: bool = False, as_standalone: bool = False) -> None:
        """
        添加 LaTeX 公式为 Word 公式对象

        优先尝试使用 pandoc 转换为 Word 原生公式（OMML），
        如果失败则使用 Unicode 字符作为 fallback。

        Args:
            latex: LaTeX 公式字符串
            is_display: 是否是展示公式（独占一行）
            as_standalone: 是否作为独立段落添加
        """
        if not latex.strip():
            return

        # 预处理：去除边界符、补偿空格
        latex = _BaseParser._strip_latex_delimiters(latex)
        latex = self._compensate_text_latex(latex)

        # 尝试转换为 Word 公式（OMML）
        math_element = self._latex_to_omml(latex, is_display)
        if math_element is not None:
            try:
                p = self.document.add_paragraph()
                p.add_run(" ")
                p._element.append(deepcopy(math_element))
                p.add_run(" ")
                return
            except Exception as e:
                raise ExportError(f"添加公式失败: {e}") from e

        # Fallback: 使用 Unicode 字符表示
        unicode_text = self.latex_converter.convert_inline(latex)
        p = self.document.add_paragraph(unicode_text)
        self._set_run_font(p.runs[0])

    def _add_latex_to_paragraph(self, para, latex: str, is_display: bool = False, as_standalone: bool = False) -> None:
        """
        将 LaTeX 公式添加到已有段落中（内联公式）

        用于内联公式的处理。
        """
        if not latex.strip():
            return

        latex = _BaseParser._strip_latex_delimiters(latex)
        latex = self._compensate_text_latex(latex)

        math_element = self._latex_to_omml(latex, is_display)
        if math_element is not None:
            try:
                para.add_run(" ")
                para._element.append(deepcopy(math_element))
                para.add_run(" ")
            except Exception as e:
                raise ExportError(f"添加公式失败: {e}") from e
        else:
            unicode_text = self.latex_converter.convert_inline(latex)
            run = para.add_run(unicode_text)
            self._set_run_font(run)
            if as_standalone:
                run = para.add_run(" ")
                self._set_run_font(run)

    def _latex_to_omml(self, latex: str, is_display: bool = False) -> Optional[etree._Element]:
        """
        使用 pandoc 将 LaTeX 转换为 OMML 元素

        工作流程：
        1. 将 LaTeX 写入临时 .tex 文件
        2. 用 pandoc 转换为 .docx
        3. 从生成的 docx 中提取公式元素
        4. 清理临时文件

        OMML 是 Word 的公式格式，可以像文字一样编辑。
        """
        deps_ok, _ = self.latex_converter.check_dependencies()
        if not deps_ok:
            return None

        # 格式化 LaTeX 内容
        if is_display:
            tex_content = f'$$\n{latex}\n$$'
        else:
            tex_content = f'\\({latex}\\)'

        tmp_tex_path = None
        tmp_docx_path = None

        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.tex', delete=False
            ) as tmp_tex:
                tmp_tex.write(tex_content)
                tmp_tex_path = tmp_tex.name

            with tempfile.NamedTemporaryFile(
                suffix='.docx', delete=False
            ) as tmp_docx:
                tmp_docx_path = tmp_docx.name

            # 执行 pandoc 转换
            cmd = ["pandoc", tmp_tex_path, "-o", tmp_docx_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self._pandoc_timeout)

            # 从生成的 docx 中提取公式
            if result.returncode == 0 and os.path.exists(tmp_docx_path):
                doc = Document(tmp_docx_path)
                for para in doc.paragraphs:
                    math_el = self._extract_math_from_paragraph(para._element)
                    if math_el is not None:
                        return math_el
            if result.stderr:
                print(f"pandoc警告: {result.stderr[:200]}")
        except Exception as e:
            raise ExportError(f"Pandoc转换失败: {e}") from e
        finally:
            # 清理临时文件
            import sys
            for path in [tmp_tex_path, tmp_docx_path]:
                if path:
                    try:
                        if os.path.exists(path):
                            os.unlink(path)
                    except OSError:
                        # Windows 上文件可能被占用，静默忽略
                        pass

        return None

    def _extract_math_from_paragraph(self, p_element) -> Optional[etree._Element]:
        """
        从段落元素中提取数学公式

        Word 文档中的公式存储在 oMath 或 oMathPara 标签中。
        """
        for child in p_element:
            tag = child.tag
            if "oMath" in tag:
                return child
            if "oMathPara" in tag:
                return child
        return None

    def _compensate_text_latex(self, latex: str) -> str:
        """
        补偿 \\text{} 中的空格丢失问题

        pandoc 在转换 \\text{ K} 时会丢失前面的空格，
        改用 ~ (反斜杠空格) 代替普通空格来保留。
        """
        compensated = re.sub(r'\\text\{ ', lambda m: '\\text{~', latex)
        return compensated

    def _add_code_block(self, code: str, language: Optional[str] = None) -> None:
        """
        添加代码块 - 带灰色背景

        使用等宽字体（代码字号）并添加灰色背景（#F2F2F2）。
        """
        para = self.document.add_paragraph()
        run = para.add_run(code)
        run.font.size = Pt(self.config.style_config.code_font_size)
        self._set_run_font(run)

        # 添加灰色背景
        pPr = para._element.get_or_add_pPr()
        shd = parse_xml(r'<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:val="pro" w:fill="F2F2F2"/>')
        pPr.append(shd)

    def _add_list(self, content: str, list_type: Optional[str] = None) -> None:
        """添加列表（用于简单文本列表）"""
        items = content.split("\n")
        for item in items:
            if item.strip():
                if list_type == "ol":
                    para = self.document.add_paragraph(item.strip(), style="List Number")
                else:
                    para = self.document.add_paragraph(item.strip(), style="List Bullet")
                for run in para.runs:
                    self._set_run_font(run)

    def _add_table(self, table_data) -> None:
        """
        添加表格

        创建 Word 表格，设置表头加粗、网格样式。
        """
        if not table_data or not table_data.headers:
            return

        cols = len(table_data.headers)
        rows_count = len(table_data.rows) + 1

        table = self.document.add_table(rows=rows_count, cols=cols)
        table.style = "Table Grid"

        # 添加表头
        header_bold = getattr(table_data, 'header_bold', []) or [False] * cols
        for i, header in enumerate(table_data.headers):
            cell = table.rows[0].cells[i]
            cell.text = header
            is_bold = header_bold[i] if i < len(header_bold) else True
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.bold = is_bold
                    self._set_run_font(run)

        # 添加数据行
        cell_bold = getattr(table_data, 'cell_bold', []) or []
        for row_idx, row_data in enumerate(table_data.rows):
            row_bold = cell_bold[row_idx] if row_idx < len(cell_bold) else []
            for col_idx, cell_data in enumerate(row_data):
                if col_idx < cols:
                    cell = table.rows[row_idx + 1].cells[col_idx]
                    cell.text = cell_data
                    is_bold = row_bold[col_idx] if col_idx < len(row_bold) else False
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            run.bold = is_bold
                            self._set_run_font(run)

    def _add_blockquote(self, content: str) -> None:
        """添加引用"""
        para = self.document.add_paragraph(content)
        para.style = "Quote"
        for run in para.runs:
            self._set_run_font(run)
            run.font.italic = True