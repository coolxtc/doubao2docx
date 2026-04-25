"""
Word 文档构建器模块

将解析后的内容块转换为 Word 文档（.docx 格式）。
使用 python-docx 库创建文档，通过 pandoc 将 LaTeX 公式转换为 Word 原生格式。
"""

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Optional

import requests

from copy import deepcopy
from docx import Document
from lxml.etree import _Element as Element
from docx.oxml.ns import qn
from docx.oxml import parse_xml
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK

from ..preprocessor import TextBlock, InlineContent
from ..preprocessor.base import BaseParser as _BaseParser
from ..config import DocumentStyleConfig, get_config
from ..exceptions import ExportError
from .latex_converter import LaTeXConverter


@dataclass
class DocumentConfig:
    """
    文档配置 - 定义 Word 文档的全局样式和属性

    为什么使用 dataclass？
    - 自动生成 __init__、__repr__ 等方法
    - 类型注解让代码更易维护
    - 不可变属性（默认）避免意外修改
    """
    title: str = "豆包聊天记录"
    author: str = "Doubao Export"
    margin_left: float = 1.0
    margin_right: float = 1.0
    margin_top: float = 1.0
    margin_bottom: float = 1.0
    font_name: str = "微软雅黑"
    font_size: int = 12
    style_config: DocumentStyleConfig | None = None

    def __post_init__(self):
        if self.style_config is None:
            self.style_config = get_config().document_style


class DocxBuilder:
    """
    Word 文档构建器 - 将内容块转换为 Word 文档

    这是核心的文档生成类，负责将解析后的 TextBlock 列表转换为可读的 Word 文档。

    为什么需要这个类？
    - 解析器只能提取结构化数据，不能直接生成 Word 文件
    - python-docx API 比较底层，需要封装成更易用的接口
    - 不同类型的内容（公式、代码、表格）需要不同的处理逻辑
    """

    def __init__(self, config: Optional[DocumentConfig] = None) -> None:
        """
        初始化文档构建器

        Args:
            config: 文档配置，如果为 None 则使用默认配置

        初始化时做了什么？
        1. 创建 Document 对象（Word 文档的根节点）
        2. 初始化 LaTeX 转换器（用于公式转换）
        3. 设置页面边距和默认字体
        4. 初始化列表状态追踪器（用于有序列表序号）
        """
        self.config = config or DocumentConfig(style_config=get_config().document_style)
        self.document = Document()  # python-docx 文档对象
        self.latex_converter = LaTeXConverter()  # LaTeX 公式转换器
        self._setup_document()

        # 列表状态追踪（用于有序列表序号连续性）
        self._last_list_type: str | None = None  # 上一个列表类型（"ul" 或 "ol"）
        self._last_list_level: int = 0  # 上一个列表的嵌套层级
        self._list_counter: int = 0  # 当前有序列表的序号
        self._last_block_type: str | None = None  # 上一个内容块类型

        # 图片下载失败追踪
        self._image_failure_count: int = 0  # 失败图片数量
        self._image_failure_urls: list[str] = []  # 失败图片 URL 列表

        self._config = get_config()
        self._pandoc_timeout: int = self._config.pandoc.timeout if self._config.pandoc else 15

    def _setup_document(self) -> None:
        """设置文档基础样式（页边距和默认字体）"""
        section = self.document.sections[0]
        section.top_margin = Inches(self.config.margin_top)
        section.bottom_margin = Inches(self.config.margin_bottom)
        section.left_margin = Inches(self.config.margin_left)
        section.right_margin = Inches(self.config.margin_right)

        # 设置默认字体
        style = self.document.styles["Normal"]
        style.font.name = self.config.font_name  # pyright: ignore[reportAttributeAccessIssue]
        style.font.size = Pt(self.config.font_size)  # pyright: ignore[reportAttributeAccessIssue]

    def _set_run_font(self, run) -> None:
        """设置字体（包含中文字体支持）"""
        run.font.name = self.config.font_name
        run.font.size = Pt(self.config.font_size)
        try:
            run._element.rPr.rFonts.set(qn('w:eastAsia'), self.config.font_name)
        except (AttributeError, TypeError):
            pass

    def _add_title(self, title: str) -> None:
        """添加文档标题（居中显示）"""
        heading = self.document.add_heading(title, level=1)
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in heading.runs:
            run.font.size = Pt(self.config.style_config.title_font_size if self.config.style_config else 18)
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
        """从内容块构建文档（主入口方法）"""
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

        footer_mark = self._config.document_style.footer_mark
        if footer_mark:
            self._add_paragraph(footer_mark)

        self.document.save(output_path)
        return output_path

    def get_image_failures(self) -> tuple[int, list[str]]:
        return self._image_failure_count, self._image_failure_urls

    def _add_text_block(self, block: "TextBlock") -> None:
        """根据块类型分发处理"""
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
            # 标题意味着新的逻辑分组，重置列表状态，让后续列表从 1 开始编号
            self._last_list_type = None
            self._last_list_level = 0
            self._list_counter = 0
        elif block.type == "list":
            self._add_list(block.content, block.language)
        elif block.type == "list_item":
            self._add_list_item(block)
        elif block.type == "table":
            self._add_table(block.data)
        elif block.type == "blockquote":
            self._add_blockquote(block.content)
        elif block.type == "image":
            self._add_image(block.content)
        elif block.type == "paragraph" and block.items:
            # 包含内联内容（文本和公式混合）的段落
            self._add_inline_content(block.items)
        else:
            # 普通段落
            content = block.content.rstrip("\n") if block.content else ""
            if content:
                self._add_paragraph(content)

    def _add_list_item(self, block: "TextBlock") -> None:
        """添加列表项（支持有序和无序列表）"""
        list_type = block.language if block.language in ("ul", "ol") else "ul"
        level = getattr(block, 'level', 0)

        if block.items:
            # 包含内联内容的列表项（如加粗文本、公式）
            if list_type == "ol":
                if self._last_block_type == "heading" or self._last_list_level != level or self._last_list_type == "ul":
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
                if self._last_block_type == "heading" or self._last_list_level != level or self._last_list_type == "ul":
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
        
        self._last_block_type = block.type

    def _add_inline_content(self, items: list[InlineContent], list_type: Optional[str] = None, start_index: int = 1, level: int = 0) -> None:
        """添加内联内容（文本和公式混合的段落）"""
        if not items:
            return

        para = self._create_inline_paragraph(list_type, start_index, level)
        last_run = None
        prev_was_latex = False
        for idx, item in enumerate(items):
            # 有列表标记时，创建新的无序列表段落
            if item.list_marker and item.type == "text":
                para = self.document.add_paragraph(style="List Bullet")
                run = para.add_run(item.content)
                self._set_run_font(run)
                if item.bold:
                    run.font.bold = True
                if item.italic:
                    run.font.italic = True
                item_level = getattr(item, 'level', level)
                if item_level > 0:
                    para.paragraph_format.left_indent = Inches(item_level * 0.5)
                last_run = None
                prev_was_latex = False
                continue

            if item.type == "text":
                # 跳过纯换行符（下一个元素是列表项时会自己创建段落）
                if item.content == "\n":
                    next_item = items[idx + 1] if idx + 1 < len(items) else None
                    if next_item and next_item.list_marker:
                        continue
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
            elif item.type == "image" and item.image_url:
                url = item.image_url
                image_data = self._download_image(url)
                if image_data:
                    temp_path = None
                    try:
                        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                            f.write(image_data)
                            temp_path = f.name
                        max_width = Inches(self.config.style_config.inline_image_width if self.config.style_config else 4.0)
                        # 创建新段落放置图片，确保独立成段
                        para = self.document.add_paragraph()
                        para.add_run().add_picture(temp_path, width=max_width)
                    except Exception:
                        self._image_failure_count += 1
                        self._image_failure_urls.append(url)
                    finally:
                        if temp_path and os.path.exists(temp_path):
                            os.unlink(temp_path)
                else:
                    self._image_failure_count += 1
                    self._image_failure_urls.append(url or "(空URL)")
                last_run = None
                prev_was_latex = False
            elif item.type == "table":
                self._add_table(item.data)
                para = self.document.add_paragraph()
            elif item.type == "code":
                self._add_code_block(item.content)
                para = self.document.add_paragraph()

    def _create_inline_paragraph(self, list_type: Optional[str], start_index: int, level: int):
        """
        创建内联段落并设置列表样式

        为什么需要单独的方法？
        在 Word 中，有序列表（1. 2. 3.）和无序列表（• • •）是不同的样式。
        创建时需要指定使用哪种样式，以及序号从几开始。
        """

        # Word 列表样式：List Number 有序，List Bullet 无序
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
        """添加 LaTeX 公式为 Word 公式对象"""
        if not latex.strip():
            return

        # 预处理 LaTeX 公式
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
        """添加内联公式到已有段落"""
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

    def _latex_to_omml(self, latex: str, is_display: bool = False) -> Element | None:
        """
        使用 pandoc 将 LaTeX 转换为 OMML 元素"""
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
                mode='w', suffix='.tex', delete=False, encoding='utf-8'
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
                        self._set_math_chinese_font(math_el, self.config.font_name)
                        return math_el
            if result.stderr:
                print(f"pandoc警告: {result.stderr[:200]}")
        except Exception as e:
            raise ExportError(f"Pandoc转换失败: {e}") from e
        finally:
            # 清理临时文件
            import logging
            logger = logging.getLogger(__name__)
            for path in [tmp_tex_path, tmp_docx_path]:
                if path:
                    try:
                        if os.path.exists(path):
                            os.unlink(path)
                    except OSError as e:
                        logger.debug(f"临时文件清理失败: {e}")

        return None

    def _extract_math_from_paragraph(self, p_element) -> Element | None:
        """从段落元素中提取数学公式"""
        for child in p_element:
            tag = child.tag
            if "oMath" in tag:
                return child
            if "oMathPara" in tag:
                return child
        return None

    def _set_math_chinese_font(self, math_element: Element, font_name: str) -> None:
        W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

        def qn_m(tag: str) -> str:
            return "{%s}%s" % (M_NS, tag)

        def qn_w(tag: str) -> str:
            return "{%s}%s" % (W_NS, tag)

        def is_chinese(text: str) -> bool:
            return any('\u4e00' <= c <= '\u9fff' for c in text)

        for m_r in math_element.iter(qn_m("r")):
            m_t = m_r.find(qn_m("t"))
            if m_t is not None and m_t.text and is_chinese(m_t.text):
                w_rPr = m_r.find(qn_w("rPr"))
                if w_rPr is None:
                    from docx.oxml import parse_xml
                    w_rPr = parse_xml(
                        f'<w:rPr xmlns:w="{W_NS}">'
                        f'<w:rFonts w:hint="eastAsia" w:ascii="{font_name}" w:hAnsi="{font_name}" w:eastAsia="{font_name}" w:cs="{font_name}"/>'
                        f"<w:b w:val='0'/><w:i w:val='0'/>"
                        f"</w:rPr>"
                    )
                    m_r.append(w_rPr)

    def _compensate_text_latex(self, latex: str) -> str:
        """补偿 \\text{} 中的空格丢失问题"""
        compensated = re.sub(r'\\text\{ ', lambda m: '\\text{~', latex)
        return compensated

    def _add_code_block(self, code: str, language: Optional[str] = None) -> None:
        """添加代码块（带灰色背景）"""
        para = self.document.add_paragraph()
        run = para.add_run(code)
        run.font.size = Pt(self.config.style_config.code_font_size if self.config.style_config else 10)
        self._set_run_font(run)

        # 添加灰色背景
        pPr = para._element.get_or_add_pPr()
        shd = parse_xml(r'<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:val="pro" w:fill="F2F2F2"/>')
        pPr.append(shd)

    def _add_list(self, content: str, list_type: Optional[str] = None) -> None:
        """添加简单文本列表"""
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
        """添加表格（表头加粗、网格样式）"""
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
        """添加引用块（斜体样式）"""
        para = self.document.add_paragraph(content)
        para.style = "Quote"
        for run in para.runs:
            self._set_run_font(run)
            run.font.italic = True

    def _download_image(self, url: str) -> Optional[bytes]:
        """下载图片到内存"""
        if not url or not url.startswith("http"):
            self._image_failure_count += 1
            self._image_failure_urls.append(url or "(空URL)")
            return None
        try:
            crawler_config = self._config.crawler
            user_agents = crawler_config.user_agents if crawler_config else None
            user_agent = user_agents[0] if user_agents else "Mozilla/5.0"
            resp = requests.get(url, timeout=15, headers={"User-Agent": user_agent})
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                self._image_failure_count += 1
                self._image_failure_urls.append(url)
                return None

            return resp.content
        except requests.RequestException as e:
            self._image_failure_count += 1
            self._image_failure_urls.append(url)
            return None

    def _add_image(self, url: str, max_width: Optional[Inches] = None) -> None:
        """添加图片（独立成段，不与前文同行）"""
        image_data = self._download_image(url)
        if image_data is None:
            self._add_paragraph("[图片加载失败]")
            return

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(image_data)
                temp_path = f.name
            width = max_width or Inches(self.config.style_config.image_width if self.config.style_config else 5.0)
            # 先创建段落再添加图片，确保图片不与前文同行
            para = self.document.add_paragraph()
            para.add_run().add_picture(temp_path, width=width)
        except Exception as e:
            self._image_failure_count += 1
            self._image_failure_urls.append(url)
            self._add_paragraph(f"[图片: {url}]")
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass