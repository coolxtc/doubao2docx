"""解析器基类模块"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString, PageElement

logger = logging.getLogger(__name__)

# =============================================================================
# 标签名常量
# =============================================================================

BOLD_TAGS = ("strong", "b")  # 加粗标签
ITALIC_TAGS = ("em", "i")  # 斜体标签
INLINE_CONTAINER_TAGS = ("div", "span")  # 内联容器标签
LIST_TAGS = ("ul", "ol")  # 列表标签
HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")  # 标题标签
IMAGE_TAGS = ("picture",)  # 图片标签（单元素元组）
BREAK_TAGS = ("br",)  # 换行标签（单元素元组）
TABLE_TAGS = ("table",)  # 表格标签（单元素元组）
CODE_TAGS = ("pre",)  # 代码标签（单元素元组）
BLOCKQUOTE_TAGS = ("blockquote",)  # 引用标签（单元素元组）
PARAGRAPH_TAGS = ("p",)  # 段落标签（单元素元组）
SECTION_TAGS = ("section",)  # 区域标签（单元素元组）
INLINE_TAGS = ("strong", "em", "span", "a", "b", "i", "u", "small", "del", "mark")  # 所有内联格式标签
LIST_ITEM_TAGS = ("li",)  # 列表项标签（单元素元组）

# =============================================================================
# Block / Inline 内容类型常量
# =============================================================================

# TextBlock 类型
BLOCK_PARAGRAPH = "paragraph"
BLOCK_LATEX = "latex"
BLOCK_CODE = "code"
BLOCK_HEADING = "heading"
BLOCK_LIST_ITEM = "list_item"
BLOCK_TABLE = "table"
BLOCK_BLOCKQUOTE = "blockquote"
BLOCK_IMAGE = "image"

# InlineContent 类型
INLINE_TEXT = "text"
INLINE_LATEX = "latex"
INLINE_IMAGE = "image"
INLINE_TABLE = "table"
INLINE_CODE = "code"

# 复合类型元组（用于过滤非文本内联项）
INLINE_NON_TEXT_TYPES = (INLINE_LATEX, INLINE_IMAGE, INLINE_TABLE, INLINE_CODE)

# LaTeX 公式语言标识
LATEX_DISPLAY = "display"
LATEX_INLINE = "inline"

# =============================================================================
# 类型别名
# =============================================================================

FlushFunc = Callable[[], None]  # flush 回调函数类型


# =============================================================================
# 数据类型
# =============================================================================

@dataclass
class PlatformConfig:
    """平台配置"""
    name: str = "doubao"  # 平台名称标识
    latex_attr: str = ""  # LaTeX 公式属性名
    math_display_classes: list[str] = field(default_factory=lambda: ["math-block", "katex--display"])  # 展示公式 CSS 类
    line_break_classes: list[str] = field(default_factory=lambda: ["md-box-line-break", "line-break"])  # 换行符 CSS 类
    code_container_class: str = "custom-code-block-container"  # 代码容器 CSS 类
    code_button_pattern: str = "button-"  # 代码按钮 CSS 类前缀
    code_expanded_attr: str = "data-expanded-code"  # 代码展开状态属性
    message_item_selector: str = "[class*='message-item']"  # 消息项选择器
    user_message_class: str = "justify-end"  # 用户消息 CSS 类
    heading_selectors: str = "h1, .chat-title, [class*='title']"  # 标题选择器
    paragraph_prefix: str = "paragraph-"  # 段落 CSS 类前缀
    parser: str = "lxml"  # HTML 解析器
    picture_container_class: str = "picture"  # 图片容器 CSS 类
    image_wrapper_class: str = "image-wrapper"  # 图片包装器 CSS 类


@dataclass
class TableData:
    """表格数据"""
    headers: list[str]  # 表头文本列表
    rows: list[list[str]]  # 数据行列表
    header_bold: list[bool] = field(default_factory=list)  # 表头加粗标记
    cell_bold: list[list[bool]] = field(default_factory=list)  # 单元格加粗标记


@dataclass
class InlineContent:
    """内联内容"""
    type: str  # 内容类型：text/latex/image/table/code
    content: str  # 文本内容或 LaTeX 公式
    is_display: bool = False  # 是否为展示公式
    bold: bool = False  # 是否加粗
    italic: bool = False  # 是否斜体
    image_url: Optional[str] = None  # 图片 URL
    data: Any = None  # 附加数据（如 TableData）
    list_marker: Optional[str] = None  # 列表标记（"•" 用于无序列表）
    level: int = 0  # 嵌套层级（0 表示无嵌套或顶层）
    language: Optional[str] = None  # 代码语言（如 "python"）


@dataclass
class TextBlock:
    """文本块"""
    type: str  # 块类型：paragraph/latex/code/heading/list_item/table/blockquote/image
    content: str  # 文本内容
    language: Optional[str] = None  # 代码语言或标题级别
    data: Any = None  # 附加数据（如 TableData）
    inline: bool = False  # 是否内联元素
    items: list[InlineContent] = field(default_factory=list)  # 内联内容列表
    level: int = 0  # 嵌套层级


@dataclass
class ParsedPage:
    """解析后的页面"""
    title: str = ""  # 页面标题
    blocks: list[TextBlock] = field(default_factory=list)  # 内容块列表
    latex_fallback_count: int = 0  # 公式识别回退计数：当 copy-text 属性缺失时触发策略2


# =============================================================================
# BaseParser - 解析器抽象基类
# =============================================================================

class BaseParser(ABC):
    """解析器抽象基类"""
    config: PlatformConfig  # 平台配置（子类必须设置）
    _tag_handlers: dict[str, Callable[[Tag, list[TextBlock]], None]]  # 标签 → 处理方法映射

    def __init__(self) -> None:
        super().__init__()
        # 幂等初始化：已有字典则跳过
        if not hasattr(self, "_tag_handlers"):
            self._build_tag_handlers()

    def _build_tag_handlers(self) -> None:
        """构建标签名 → 处理方法的映射字典（幂等，可重复调用）"""
        h: dict[str, Callable[[Tag, list[TextBlock]], None]] = {}

        # 表格
        for tag in TABLE_TAGS:
            h[tag] = self._handle_table

        # 标题 h1 - h6
        for tag in HEADING_TAGS:
            h[tag] = self._handle_heading

        # 列表 ul / ol
        for tag in LIST_TAGS:
            h[tag] = self._handle_list

        # 段落 p
        for tag in PARAGRAPH_TAGS:
            h[tag] = self._process_paragraph  # 签名一致，直接复用

        # 预格式化代码块 pre
        for tag in CODE_TAGS:
            h[tag] = self._handle_pre

        # 引用 blockquote
        for tag in BLOCKQUOTE_TAGS:
            h[tag] = self._handle_blockquote

        # 换行 br
        for tag in BREAK_TAGS:
            h[tag] = self._handle_br

        # 图片 picture
        for tag in IMAGE_TAGS:
            h[tag] = self._handle_picture

        # div / section
        h["div"] = self._process_div_or_section  # 签名一致，直接复用
        for tag in SECTION_TAGS:
            h[tag] = self._process_div_or_section

        # 所有内联格式标签
        for tag in INLINE_TAGS:
            h[tag] = self._handle_inline

        self._tag_handlers = h

    def _handle_table(self, element: Tag, blocks: list[TextBlock]) -> None:
        """处理表格标签"""
        table_data = self._parse_table(element)
        if table_data:
            blocks.append(TextBlock(type=BLOCK_TABLE, content="", data=table_data))

    def _handle_heading(self, element: Tag, blocks: list[TextBlock]) -> None:
        """处理标题标签 h1-h6"""
        text = element.get_text(strip=True)
        if text:
            level = int(element.name[1]) if len(element.name) == 2 else 1
            blocks.append(TextBlock(type=BLOCK_HEADING, content=text, language=str(level)))

    def _handle_list(self, element: Tag, blocks: list[TextBlock]) -> None:
        """处理列表标签 ul / ol"""
        self._process_list(element, element.name, blocks, 0)

    def _handle_pre(self, element: Tag, blocks: list[TextBlock]) -> None:
        """处理预格式化代码块标签 pre"""
        if element.get(self.config.code_expanded_attr):
            return
        code = element.get_text("\n", strip=True)
        language = self._extract_code_language(element)
        blocks.append(TextBlock(type=BLOCK_CODE, content=code, language=language))

    def _handle_blockquote(self, element: Tag, blocks: list[TextBlock]) -> None:
        """处理引用标签 blockquote"""
        text = element.get_text(strip=True)
        if text:
            blocks.append(TextBlock(type=BLOCK_BLOCKQUOTE, content=text))

    def _handle_br(self, element: Tag, blocks: list[TextBlock]) -> None:
        """处理换行标签 br"""
        if blocks and blocks[-1].type == BLOCK_PARAGRAPH:
            blocks[-1].content += "\n"

    def _handle_picture(self, element: Tag, blocks: list[TextBlock]) -> None:
        """处理图片标签 picture"""
        url = self._extract_image_url(element)
        if url:
            blocks.append(TextBlock(type=BLOCK_IMAGE, content=url))

    def _handle_inline(self, element: Tag, blocks: list[TextBlock]) -> None:
        """处理内联格式标签（strong, em, span, a, b, i, u, small, del, mark 等）"""
        if self._is_math_element(element):
            self._process_math_element(element, blocks)
        else:
            self._process_inline_element(element, blocks)


    def parse(self, html: str) -> ParsedPage:
        """
        解析 HTML 页面

        Args:
            html: HTML 字符串

        Returns:
            ParsedPage: 包含 title 和 blocks 的解析结果
        """
        return self._parse_impl(html)

    def _parse_impl(self, html: str) -> ParsedPage:
        """
        解析实现

        默认实现提供了完整的解析流程骨架。
        如果子类需要完全自定义解析逻辑，可以覆盖此方法。

        Args:
            html: HTML 字符串

        Returns:
            ParsedPage: 解析结果
        """
        soup = BeautifulSoup(html, self.config.parser)
        title = self._extract_title(soup)
        container = soup.body if soup.body else soup
        blocks = self._extract_blocks(container)
        return ParsedPage(title=title, blocks=blocks)


    # -------------------------------------------------------------------------
    # 抽象钩子方法 - 子类必须实现
    # -------------------------------------------------------------------------

    @abstractmethod
    def _get_title_selectors(self) -> list[str]:
        """获取标题选择器列表"""
        raise NotImplementedError("子类必须实现 _get_title_selectors()")

    @abstractmethod
    def _is_math_element(self, element: Tag) -> bool:
        """判断元素是否为公式元素"""
        raise NotImplementedError("子类必须实现 _is_math_element()")

    @abstractmethod
    def _is_display_math(self, element: Tag) -> bool:
        """判断元素是否为展示公式"""
        raise NotImplementedError("子类必须实现 _is_display_math()")

    @abstractmethod
    def _is_code_container(self, element: Tag) -> bool:
        """判断元素是否为代码容器"""
        raise NotImplementedError("子类必须实现 _is_code_container()")

    @abstractmethod
    def _is_paragraph_container(self, element: Tag) -> bool:
        """判断元素是否为段落容器"""
        raise NotImplementedError("子类必须实现 _is_paragraph_container()")

    @abstractmethod
    def _is_code_button(self, element: Tag) -> bool:
        """判断元素是否为代码展开按钮"""
        raise NotImplementedError("子类必须实现 _is_code_button()")

    @abstractmethod
    def _extract_latex_content(self, element: Tag) -> str:
        """从公式元素中提取 LaTeX 内容"""
        raise NotImplementedError("子类必须实现 _extract_latex_content()")

    @abstractmethod
    def _is_image_element(self, element: Tag) -> bool:
        """判断元素是否为图片元素"""
        raise NotImplementedError("子类必须实现 _is_image_element()")

    @abstractmethod
    def _extract_image_url(self, element: Tag) -> str:
        """从图片元素中提取 URL"""
        raise NotImplementedError("子类必须实现 _extract_image_url()")


    # -------------------------------------------------------------------------
    # 通用方法
    # -------------------------------------------------------------------------

    def _has_any_class(self, element: Tag, class_names: list[str]) -> bool:
        """
        检查元素是否包含指定类名中的任意一个

        Args:
            element: HTML 元素
            class_names: 要检查的类名列表

        Returns:
            True 如果元素包含任意一个指定类名，否则 False
        """
        classes = element.get("class") or []
        if isinstance(classes, str):
            classes = classes.split()
        return any(c in class_names for c in classes)

    def _skip_whitespace_siblings(self, prev_sibling: PageElement | None) -> PageElement | None:
        """跳过连续的空白文本兄弟节点"""
        while prev_sibling is not None and isinstance(prev_sibling, NavigableString) and not str(prev_sibling).strip():
            prev_sibling = prev_sibling.previous_sibling
        return prev_sibling

    def _handle_line_break(self, prev_sibling: PageElement | None, items: list[InlineContent],
                           current_text: str, current_bold: bool, current_italic: bool,
                           parent_bold: bool, parent_italic: bool,
                           flush_fn: Optional[FlushFunc] = None) -> tuple[str, bool, bool]:
        """
        处理换行符

        Args:
            prev_sibling: 前一个兄弟节点
            items: 内联内容列表
            current_text: 当前累积文本
            current_bold: 当前加粗状态
            current_italic: 当前斜体状态
            parent_bold: 父级加粗状态
            parent_italic: 父级斜体状态
            flush_fn: 刷新回调函数

        Returns:
            (剩余文本, 加粗状态, 斜体状态)
        """
        prev = self._skip_whitespace_siblings(prev_sibling)

        if flush_fn:
            flush_fn()
        else:
            stripped = current_text.strip()
            if stripped:
                items.append(InlineContent(
                    type=INLINE_TEXT,
                    content=stripped,
                    bold=current_bold,
                    italic=current_italic
                ))

        if isinstance(prev, Tag):
            if (prev.name in INLINE_CONTAINER_TAGS and self._has_any_class(prev, self.config.line_break_classes)
                and not prev.get_text(strip=True)):
                items.append(InlineContent(type=INLINE_TEXT, content="\n"))
                return "", parent_bold, parent_italic

        if isinstance(prev, NavigableString):
            items.append(InlineContent(type=INLINE_TEXT, content="\n"))
            return "", parent_bold, parent_italic
        elif isinstance(prev, Tag) and prev.name in LIST_TAGS:
            return "", parent_bold, parent_italic
        elif isinstance(prev, Tag) and prev.name in INLINE_CONTAINER_TAGS:
            return "", parent_bold, parent_italic
        else:
            items.append(InlineContent(type=INLINE_TEXT, content="\n"))
            return "", parent_bold, parent_italic

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """
        提取页面标题

        Args:
            soup: BeautifulSoup 对象

        Returns:
            页面标题文本
        """
        for selector in self._get_title_selectors():
            tag = soup.select_one(selector)
            if tag:
                return tag.get_text(strip=True)

        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)

        return ""

    def _extract_blocks(self, container: Tag) -> list[TextBlock]:
        """
        从容器中提取所有内容块

        Args:
            container: HTML 容器元素

        Returns:
            TextBlock 列表
        """
        blocks = []

        for child in container.children:
            try:
                if isinstance(child, NavigableString):
                    text = str(child).strip()
                    if text:
                        blocks.append(TextBlock(type=BLOCK_PARAGRAPH, content=text))
                elif isinstance(child, Tag):
                    self._process_element(child, blocks)
            except Exception:
                # 解析失败时跳过该元素，确保其余内容仍然导出
                logger.exception(
                    f"解析元素失败，跳过: {child.name if hasattr(child, 'name') else 'Unknown'}",
                    stack_info=False,
                )
                continue

        return blocks

    def _process_element(self, element: Tag, blocks: list[TextBlock]) -> None:
        """
        处理单个元素（基于字典分发）

        已知标签查表分发，未知标签走通用检测兜底逻辑。

        Args:
            element: HTML 元素
            blocks: 内容块列表
        """
        tag = element.name
        # 懒初始化：子类未调用 super().__init__() 时兜底
        if not hasattr(self, "_tag_handlers"):
            self._build_tag_handlers()
        handler = self._tag_handlers.get(tag)
        if handler is not None:
            handler(element, blocks)
            return

        # ---- 兜底逻辑：标签名不在已知映射中 ----
        if self._is_math_element(element):
            self._process_math_element(element, blocks)
            return

        if self._is_image_element(element):
            url = self._extract_image_url(element)
            if url:
                blocks.append(TextBlock(type=BLOCK_IMAGE, content=url))
            return

        if self._is_paragraph_container(element):
            self._process_paragraph(element, blocks)
            return

        text = element.get_text(strip=True)
        if text:
            if blocks and blocks[-1].type == BLOCK_PARAGRAPH:
                blocks[-1].content += " " + text
            else:
                blocks.append(TextBlock(type=BLOCK_PARAGRAPH, content=text))

    def _process_div_or_section(self, element: Tag, blocks: list[TextBlock]) -> None:
        """
        处理 div 或 section 元素

        Args:
            element: div 或 section 元素
            blocks: 内容块列表
        """
        # 代码展开按钮
        if self._is_code_button(element):
            expanded_pre = element.find("pre", attrs={self.config.code_expanded_attr: "true"})
            if expanded_pre:
                code = expanded_pre.get_text("\n", strip=True)
                blocks.append(TextBlock(type=BLOCK_CODE, content=code, language="language-plaintext"))
            return

        # 公式元素
        if self._is_math_element(element):
            self._process_math_element(element, blocks)
            return

        # 代码容器
        if self._is_code_container(element):
            self._process_code_container(element, blocks)
            return

        # 图片元素
        if self._is_image_element(element):
            url = self._extract_image_url(element)
            if url:
                blocks.append(TextBlock(type=BLOCK_IMAGE, content=url))
            return

        # 段落容器
        if self._is_paragraph_container(element):
            self._process_paragraph(element, blocks)
            return

        # 查找单个 p 子元素（用于包裹简单段落）
        p_child = None
        for child in element.children:
            if isinstance(child, Tag) and child.name in PARAGRAPH_TAGS:
                if p_child is None:
                    p_child = child
                else:
                    p_child = None
                    break

        # 单个 p 子元素：直接处理
        if p_child:
            self._process_element(p_child, blocks)
        else:
            classes = element.get("class") or []
            class_str = " ".join(c for c in classes) if isinstance(classes, list) else str(classes)
            # 检查是否为图片包装器
            if self.config.image_wrapper_class in class_str:
                # 提取图片
                pics = element.find_all(IMAGE_TAGS)
                for pic in pics:
                    url = self._extract_image_url(pic)
                    if url:
                        blocks.append(TextBlock(type=BLOCK_IMAGE, content=url))
                return

            # 其他情况：递归提取子元素
            sub_blocks = self._extract_blocks(element)
            blocks.extend(sub_blocks)

    def _process_code_container(self, element: Tag, blocks: list[TextBlock]) -> None:
        """
        处理代码块容器

        Args:
            element: 代码容器元素
            blocks: 内容块列表
        """
        code_elem = element.find("code")
        pre_elem = element.find(CODE_TAGS)

        # 优先从 pre 标签提取代码
        if pre_elem:
            code_content = pre_elem.get_text("\n", strip=True)
        # 其次从 code 标签提取
        elif code_elem:
            code_content = code_elem.get_text("\n", strip=True)
        # 最后从元素自身提取
        else:
            code_content = element.get_text("\n", strip=True)
            if code_content.startswith("plaintext"):
                code_content = code_content[len("plaintext"):].lstrip("\n")

        if code_content:
            language = self._extract_code_language(element)
            blocks.append(TextBlock(type=BLOCK_CODE, content=code_content, language=language))

    @staticmethod
    def _extract_code_language(element: Tag) -> str:
        """
        从代码块元素中提取编程语言标识

        Args:
            element: 代码块根元素（pre 或代码容器）

        Returns:
            语言标识字符串，如 "python"、"language-plaintext"，默认 "text"
        """
        # 优先从 <code> 子元素的 class 中提取（如 "language-python"）
        code_elem = element.find("code")
        if code_elem:
            classes = code_elem.get("class") or []
            # 过滤掉 highlight.js 的通用类名 "hljs"
            lang = " ".join(c for c in classes if c != "hljs")
            if lang:
                return lang

        # 兜底：从容器自身的类名判断（如豆包的 "plaintext"）
        container_classes = element.get("class") or []
        if "plaintext" in container_classes:
            return "language-plaintext"

        return "text"

    def _process_list(self, element: Tag, list_type: str, blocks: list[TextBlock], level: int = 0) -> None:
        """
        处理列表元素

        Args:
            element: ul 或 ol 元素
            list_type: 列表类型 ("ul" 或 "ol")
            blocks: 内容块列表
            level: 嵌套层级
        """
        list_items = element.find_all("li", recursive=False)
        for i, li in enumerate(list_items):
            self._process_list_item(li, blocks, list_type, i + 1, level)

    def _process_list_item(self, li: Tag, blocks: list[TextBlock], list_type: str = "ul", index: int = 1, level: int = 0) -> None:
        """
        处理单个列表项

        Args:
            li: li 元素
            blocks: 内容块列表
            list_type: 列表类型
            index: 列表项序号
            level: 嵌套层级
        """
        has_nested_list = li.find(LIST_TAGS, recursive=False)
        has_br = li.find(BREAK_TAGS) is not None or any(
            isinstance(x, str) and "line-break" in x
            for x in (li.get("class") or [])
        ) or any(
            isinstance(child, Tag) and child.name == "div" and self._has_any_class(child, self.config.line_break_classes)
            for child in li.children
        )
        has_strong = li.find(BOLD_TAGS)
        has_math = self._find_math_in_element(li)
        has_em = li.find(ITALIC_TAGS)
        has_picture = li.find(IMAGE_TAGS) is not None
        has_table = li.find(TABLE_TAGS) is not None
        has_pre = li.find(CODE_TAGS) is not None

        # 包含内联内容的列表项
        if has_br or has_strong or has_math or has_em or has_nested_list or has_picture or has_table or has_pre:
            self._process_complex_list_item(li, blocks, list_type, level)
            return

        # 简单列表项：直接提取文本
        text = li.get_text(strip=True)
        if text:
            blocks.append(TextBlock(type=BLOCK_LIST_ITEM, content=text, language=list_type, level=level))

    def _process_complex_list_item(self, li: Tag, blocks: list[TextBlock], list_type: str, level: int = 0) -> None:
        """
        处理复杂的列表项

        Args:
            li: li 元素
            blocks: 内容块列表
            list_type: 列表类型
            level: 嵌套层级
        """
        items = self._walk_inline_children(
            li,
            parent_bold=False,
            parent_italic=False,
            conditional_format_flush=False,
            handle_line_break_div=True,
            parse_div_span_inline=True,
            strip_nav_strings=True,
            reset_format_to_parent=False,
            handle_nested_lists=True,
            list_level=level,
        )
        if items:
            valid_items = [item for item in items if item.content.strip() or item.content == "\n" or item.type in INLINE_NON_TEXT_TYPES]
            if valid_items:
                blocks.append(TextBlock(type=BLOCK_LIST_ITEM, content="", language=list_type, items=valid_items, level=level))

    def _walk_inline_children(
        self,
        element: Tag,
        *,
        parent_bold: bool = False,
        parent_italic: bool = False,
        conditional_format_flush: bool = False,
        handle_line_break_div: bool = True,
        parse_div_span_inline: bool = True,
        strip_nav_strings: bool = True,
        reset_format_to_parent: bool = False,
        handle_nested_lists: bool = False,
        list_level: int = 1,
    ) -> list[InlineContent]:
        """
        统一遍历内联子元素并返回 InlineContent 列表
        
        该方法是三个内联处理方法的公共核心，通过参数控制细微行为差异。

        Args:
            element: 待遍历的 HTML 元素
            parent_bold: 继承的父级加粗状态
            parent_italic: 继承的父级斜体状态
            conditional_format_flush: 遇到 strong/em 时是否条件 flush（仅文本非空时）
            handle_line_break_div: 处理 line-break-class div 还是直接添加换行
            parse_div_span_inline: 递归解析 div/span 内联内容还是仅提取图片
            strip_nav_strings: 对 NavigableString 是否先 strip
            reset_format_to_parent: flush 后重置为父级状态还是 False
            handle_nested_lists: 处理 ul/ol 嵌套列表还是跳过
            list_level: 嵌套列表层级

        Returns:
            InlineContent 列表
        """
        items: list[InlineContent] = []
        current_text = ""
        current_bold = parent_bold
        current_italic = parent_italic

        def flush() -> None:
            nonlocal current_text, current_bold, current_italic
            stripped = current_text.strip()
            if stripped:
                items.append(InlineContent(
                    type=INLINE_TEXT,
                    content=stripped,
                    bold=current_bold,
                    italic=current_italic
                ))
            current_text = ""
            current_bold = parent_bold if reset_format_to_parent else False
            current_italic = parent_italic if reset_format_to_parent else False

        for child in element.children:
            if isinstance(child, NavigableString):
                text = str(child).strip() if strip_nav_strings else str(child)
                if text:
                    current_text += text
            elif isinstance(child, Tag):
                # 公式元素
                if self._is_math_element(child):
                    flush()
                    latex = self._extract_latex_content(child)
                    is_display = self._is_display_math(child)
                    items.append(InlineContent(type=INLINE_LATEX, content=latex, is_display=is_display))
                # 加粗标签
                elif child.name in BOLD_TAGS:
                    if conditional_format_flush:
                        if current_text.strip():
                            flush()
                    else:
                        flush()
                    items.extend(
                        self._walk_inline_children(
                            child,
                            parent_bold=True,
                            parent_italic=current_italic,
                            conditional_format_flush=conditional_format_flush,
                            handle_line_break_div=handle_line_break_div,
                            parse_div_span_inline=parse_div_span_inline,
                            strip_nav_strings=strip_nav_strings,
                            reset_format_to_parent=reset_format_to_parent,
                            handle_nested_lists=False,
                            list_level=list_level,
                        )
                    )
                # 斜体标签
                elif child.name in ITALIC_TAGS:
                    if conditional_format_flush:
                        if current_text.strip():
                            flush()
                    else:
                        flush()
                    items.extend(
                        self._walk_inline_children(
                            child,
                            parent_bold=current_bold,
                            parent_italic=True,
                            conditional_format_flush=conditional_format_flush,
                            handle_line_break_div=handle_line_break_div,
                            parse_div_span_inline=parse_div_span_inline,
                            strip_nav_strings=strip_nav_strings,
                            reset_format_to_parent=reset_format_to_parent,
                            handle_nested_lists=False,
                            list_level=list_level,
                        )
                    )
                # line-break-class div
                elif child.name in INLINE_CONTAINER_TAGS and self._has_any_class(child, self.config.line_break_classes):
                    if handle_line_break_div and child.previous_sibling is not None:
                        current_text, current_bold, current_italic = self._handle_line_break(
                            child.previous_sibling, items, current_text, current_bold, current_italic,
                            parent_bold, parent_italic, flush
                        )
                    else:
                        flush()
                        items.append(InlineContent(type=INLINE_TEXT, content="\n"))
                # 换行标签
                elif child.name in BREAK_TAGS:
                    flush()
                    items.append(InlineContent(type=INLINE_TEXT, content="\n"))
                # 图片元素
                elif child.name in IMAGE_TAGS:
                    flush()
                    url = self._extract_image_url(child)
                    if url:
                        items.append(InlineContent(type=INLINE_IMAGE, content="", image_url=url))
                # 表格元素
                elif child.name in TABLE_TAGS:
                    flush()
                    table_data = self._parse_table(child)
                    if table_data:
                        items.append(InlineContent(type=INLINE_TABLE, content="", data=table_data, bold=current_bold, italic=current_italic))
                # 代码块
                elif child.name in CODE_TAGS:
                    if not child.get(self.config.code_expanded_attr):
                        flush()
                        code_content = child.get_text("\n", strip=True)
                        items.append(InlineContent(type=INLINE_CODE, content=code_content, bold=current_bold, italic=current_italic))
                # 段落容器
                elif child.name in PARAGRAPH_TAGS:
                    flush()
                    items.extend(
                        self._walk_inline_children(
                            child, parent_bold=current_bold, parent_italic=current_italic,
                            conditional_format_flush=conditional_format_flush, handle_line_break_div=handle_line_break_div,
                            parse_div_span_inline=parse_div_span_inline, strip_nav_strings=strip_nav_strings,
                            reset_format_to_parent=reset_format_to_parent, handle_nested_lists=False, list_level=list_level
                        )
                    )
                # 嵌套列表
                elif child.name in LIST_TAGS:
                    if handle_nested_lists:
                        flush()
                        self._extract_nested_list_text(child, items, current_bold, current_italic, list_level + 1)
                    else:
                        pass  # 跳过
                # 内联容器 div/span
                elif child.name in INLINE_CONTAINER_TAGS:
                    if parse_div_span_inline:
                        if self._contains_block_elements(child):
                            # 内联容器中包含块级元素，不扁平化，提取纯文本并保留格式状态
                            saved_bold, saved_italic = current_bold, current_italic
                            flush()
                            text = child.get_text(strip=True)
                            if text:
                                items.append(InlineContent(type=INLINE_TEXT, content="\n" + text + "\n", bold=saved_bold, italic=saved_italic))
                        else:
                            flush()
                            items.extend(
                                self._walk_inline_children(
                                    child, parent_bold=current_bold, parent_italic=current_italic,
                                    conditional_format_flush=conditional_format_flush, handle_line_break_div=handle_line_break_div,
                                    parse_div_span_inline=parse_div_span_inline, strip_nav_strings=strip_nav_strings,
                                    reset_format_to_parent=reset_format_to_parent, handle_nested_lists=handle_nested_lists, list_level=list_level
                                )
                            )
                    else:
                        has_pic, text = self._extract_images_recursive(child, items, flush)
                        if not has_pic and text:
                            current_text += text
                # 其他元素
                else:
                    sub_text = child.get_text(strip=False)
                    if sub_text:
                        current_text += sub_text

        flush()
        return items

    def _extract_nested_list_text(self, element: Tag, items: list[InlineContent], bold: bool = False, italic: bool = False, level: int = 1) -> None:
        """
        提取嵌套列表的文本内容

        Args:
            element: ul 或 ol 元素
            items: 内联内容列表
            bold: 加粗状态
            italic: 斜体状态
            level: 嵌套层级
        """
        counter = 1
        li_elements = element.find_all(LIST_ITEM_TAGS, recursive=False)
        for idx, child in enumerate(li_elements):
            direct_text = self._get_direct_text(child)
            list_marker = "•" if element.name == "ul" else None
            has_nested_list = child.find(LIST_TAGS, recursive=False) is not None

            if direct_text:
                if element.name == "ul":
                    items.append(InlineContent(type=INLINE_TEXT, content=direct_text, bold=bold, italic=italic, list_marker=list_marker, level=level))
                else:
                    items.append(InlineContent(type=INLINE_TEXT, content=f"{counter}. {direct_text}", bold=bold, italic=italic, level=level))

            if element.name == "ol" and (direct_text or has_nested_list):
                counter += 1

            nested_items = []
            self._collect_nested_content_in_li(child, nested_items, bold, italic)
            for ni in nested_items:
                ni.list_marker = list_marker
                ni.level = level
            items.extend(nested_items)

            nested = child.find(LIST_TAGS, recursive=False)
            if nested:
                self._extract_nested_list_text(nested, items, bold, italic, level + 1)

    def _get_direct_text(self, element: Tag) -> str:
        """
        获取元素的直接文本（排除嵌套的 ul/ol）

        Args:
            element: HTML 元素

        Returns:
            直接文本字符串
        """
        texts = []
        for child in element.children:
            if isinstance(child, str):
                text = str(child).strip()
                if text:
                    texts.append(text)
            elif isinstance(child, Tag) and child.name in LIST_TAGS:
                continue
            elif isinstance(child, Tag):
                texts.append(self._get_direct_text(child))
        return ''.join(texts).strip()

    def _collect_nested_content_in_li(self, li: Tag, items: list[InlineContent], bold: bool, italic: bool) -> None:
        """
        收集列表项中的深层嵌套内容块

        Args:
            li: li 元素
            items: 内联内容列表
            bold: 加粗状态
            italic: 斜体状态
        """
        for pic in li.find_all(IMAGE_TAGS):
            url = self._extract_image_url(pic)
            if url:
                items.append(InlineContent(type=INLINE_IMAGE, content="", image_url=url))

        for table in li.find_all(TABLE_TAGS, recursive=False):
            table_data = self._parse_table(table)
            if table_data:
                items.append(InlineContent(type=INLINE_TABLE, content="", data=table_data, bold=bold, italic=italic))

        for pre in li.find_all(CODE_TAGS, recursive=False):
            if pre.get(self.config.code_expanded_attr):
                continue
            code_content = pre.get_text("\n", strip=True)
            language = self._extract_code_language(pre)
            items.append(InlineContent(type=INLINE_CODE, content=code_content, bold=bold, italic=italic, language=language))

    def _process_nested_container(self, element: Tag, items: list[InlineContent],
                                   parent_bold: bool = False, parent_italic: bool = False) -> None:
        """
        递归处理嵌套容器

        Args:
            element: HTML 容器元素
            items: 内联内容列表
            parent_bold: 父级加粗状态
            parent_italic: 父级斜体状态
        """
        items.extend(
            self._walk_inline_children(
                element,
                parent_bold=parent_bold,
                parent_italic=parent_italic,
                conditional_format_flush=True,
                handle_line_break_div=True,
                parse_div_span_inline=True,
                strip_nav_strings=True,
                reset_format_to_parent=True,
                handle_nested_lists=False,
            )
        )

    def _should_parse_as_complex(self, element: Tag) -> bool:
        """
        判断段落元素是否包含需要复杂解析的内联内容

        Args:
            element: p 元素

        Returns:
            True 如果包含数学公式、加粗、斜体、链接、内联代码或图片
        """
        return (
            bool(self._find_math_in_element(element)) or  # 数学公式
            element.find(BOLD_TAGS) is not None or  # 加粗
            element.find(ITALIC_TAGS) is not None or  # 斜体
            element.find("a") is not None or  # 链接
            element.find("code") is not None or  # 内联代码
            element.find(IMAGE_TAGS) is not None  # 图片
        )

    def _process_paragraph(self, element: Tag, blocks: list[TextBlock]) -> None:
        """
        处理段落元素

        Args:
            element: p 元素
            blocks: 内容块列表
        """
        # 简单段落：直接提取文本
        if not self._should_parse_as_complex(element):
            text = element.get_text(strip=True)
            if text:
                blocks.append(TextBlock(type=BLOCK_PARAGRAPH, content=text))
            return

        # 复杂段落：解析内联内容
        items = self._walk_inline_children(
            element,
            parent_bold=False,
            parent_italic=False,
            conditional_format_flush=True,
            handle_line_break_div=False,
            parse_div_span_inline=False,
            strip_nav_strings=False,
            reset_format_to_parent=False,
            handle_nested_lists=False,
        )
        if items:
            blocks.append(TextBlock(type=BLOCK_PARAGRAPH, content="", items=items))

    def _extract_images_recursive(self, element: Tag, items: list[InlineContent], flush_func: FlushFunc) -> tuple[bool, str]:
        """
        递归查找嵌套的 picture 并提取图片

        Args:
            element: HTML 元素
            items: 内联内容列表
            flush_func: 刷新回调函数

        Returns:
            (是否有图片, 剩余文本)
        """
        pics = element.find_all(IMAGE_TAGS)
        if pics:
            for pic in pics:
                flush_func()
                url = self._extract_image_url(pic)
                if url:
                    items.append(InlineContent(type=INLINE_IMAGE, content="", image_url=url))
            return True, ""
        else:
            sub_text = element.get_text(strip=False)
            return False, sub_text

    def _extract_inline_text_with_format(self, element: Tag, in_bold: bool = False) -> list[InlineContent]:
        """
        提取内联元素的文本（委托给 _walk_inline_children）

        注意：此方法仅用于单元测试。业务逻辑已内联到 _walk_inline_children。

        Args:
            element: HTML 元素
            in_bold: 是否继承父级加粗

        Returns:
            InlineContent 列表
        """
        return self._walk_inline_children(
            element,
            parent_bold=in_bold,
            parent_italic=False,
            conditional_format_flush=False,
            handle_line_break_div=False,
            parse_div_span_inline=False,
            strip_nav_strings=True,
            reset_format_to_parent=False,
            handle_nested_lists=False,
            list_level=1,
        )

    def _extract_strong_recursive(self, element: Tag) -> list[InlineContent]:
        """
        递归提取 strong/b 内的内容（委托给 _walk_inline_children）

        注意：此方法仅用于单元测试。业务逻辑已内联到 _walk_inline_children。

        Args:
            element: strong 或 b 元素

        Returns:
            InlineContent 列表
        """
        return self._walk_inline_children(
            element,
            parent_bold=True,
            parent_italic=False,
            conditional_format_flush=True,
            handle_line_break_div=False,
            parse_div_span_inline=False,
            strip_nav_strings=True,
            reset_format_to_parent=False,
            handle_nested_lists=False,
            list_level=1,
        )

    def _extract_italic_recursive(self, element: Tag) -> list[InlineContent]:
        """
        递归提取斜体/强调内容（委托给 _walk_inline_children）

        注意：此方法仅用于单元测试。业务逻辑已内联到 _walk_inline_children。

        Args:
            element: em 或 i 元素

        Returns:
            InlineContent 列表
        """
        return self._walk_inline_children(
            element,
            parent_bold=False,
            parent_italic=True,
            conditional_format_flush=True,
            handle_line_break_div=False,
            parse_div_span_inline=False,
            strip_nav_strings=True,
            reset_format_to_parent=False,
            handle_nested_lists=False,
            list_level=1,
        )

    def _process_inline_element(self, element: Tag, blocks: list[TextBlock]) -> None:
        """
        处理内联元素

        Args:
            element: HTML 元素
            blocks: 内容块列表
        """
        # 统一使用 _walk_inline_children 提取内联内容（包括图片）
        bold = element.name in BOLD_TAGS
        italic = element.name in ITALIC_TAGS
        items = self._walk_inline_children(
            element,
            parent_bold=bold,
            parent_italic=italic,
            conditional_format_flush=False,
            handle_line_break_div=False,
            parse_div_span_inline=False,
            strip_nav_strings=True,
            reset_format_to_parent=False,
            handle_nested_lists=False,
            list_level=1,
        )
        if items:
            blocks.append(TextBlock(type=BLOCK_PARAGRAPH, content="", items=items))
        else:
            text = element.get_text(strip=True)
            if text:
                blocks.append(TextBlock(type=BLOCK_PARAGRAPH, content=text, language="bold" if bold else None))

    def _process_element_with_inline_math(self, element: Tag, blocks: list[TextBlock]) -> None:
        """
        处理包含公式的内联元素（委托给 _process_inline_element）

        注意：此方法仅用于单元测试兼容。与 _process_inline_element 逻辑一致。

        Args:
            element: HTML 元素
            blocks: 内容块列表
        """
        return self._process_inline_element(element, blocks)

    def _process_math_element(self, element: Tag, blocks: list[TextBlock]) -> None:
        """
        处理公式元素

        Args:
            element: 公式元素
            blocks: 内容块列表
        """
        latex = self._extract_latex_content(element)

        if not latex:
            latex = element.get_text(strip=True)

        latex = self._strip_latex_delimiters(latex)
        is_display = self._is_display_math(element)

        blocks.append(TextBlock(
            type=BLOCK_LATEX,
            content=latex,
            language=LATEX_DISPLAY if is_display else LATEX_INLINE
        ))

        # 内联公式（非 display）可合并到前一个 paragraph
        if not is_display and len(blocks) >= 2:
            prev_block = blocks[-2]
            if prev_block.type == BLOCK_PARAGRAPH and not prev_block.items and not prev_block.content:
                prev_block.items.append(InlineContent(type=INLINE_LATEX, content=latex, is_display=is_display))
                blocks.pop()

    # -------------------------------------------------------------------------
    # 辅助方法
    # -------------------------------------------------------------------------

    def _find_math_in_element(self, element: Tag) -> list[Tag]:
        """
        在元素中查找所有公式元素

        Args:
            element: HTML 元素

        Returns:
            公式元素列表
        """
        return [
            el for el in element.descendants
            if isinstance(el, Tag) and self._is_math_element(el)
        ]

    def _contains_block_elements(self, element: Tag) -> bool:
        """
        检查元素是否包含块级子元素

        Args:
            element: HTML 元素

        Returns:
            如果包含块级元素返回 True，否则返回 False
        """
        block_tags = set(HEADING_TAGS) | set(LIST_TAGS) | set(TABLE_TAGS) | set(CODE_TAGS) | set(BLOCKQUOTE_TAGS)
        for child in element.descendants:
            if isinstance(child, Tag) and child.name in block_tags:
                return True
        return False

    @staticmethod
    def _parse_table(table: Tag) -> Optional[TableData]:
        """
        解析表格

        Args:
            table: table 元素

        Returns:
            TableData 对象，解析失败返回 None
        """
        headers = []  # 表头文本列表
        rows = []  # 数据行列表
        header_bold = []  # 表头加粗标记
        cell_bold = []  # 单元格加粗标记

        thead = table.find("thead")
        if thead:
            header_row = thead.find("tr")
            if header_row:
                headers = []
                header_bold = []
                for th in header_row.find_all(["th", "td"]):
                    headers.append(th.get_text(strip=True))
                    header_bold.append(th.find(BOLD_TAGS) is not None)

        tbody = table.find("tbody")
        if not tbody:
            tbody = table

        for row in tbody.find_all("tr"):
            row_data = []
            row_bold = []
            for td in row.find_all(["td", "th"]):
                row_data.append(td.get_text(strip=True))
                row_bold.append(td.find(BOLD_TAGS) is not None)
            if row_data:
                rows.append(row_data)
                cell_bold.append(row_bold)

        if not rows and not headers:
            return None

        if not headers:
            headers = rows[0] if rows else []
            rows = rows[1:] if rows else []
            header_bold = [False] * len(headers)
            cell_bold = cell_bold[1:] if cell_bold else []

        return TableData(headers=headers, rows=rows, header_bold=header_bold, cell_bold=cell_bold)

    @staticmethod
    def _strip_latex_delimiters(latex: str) -> str:
        """
        去除 LaTeX 公式的边界符

        Args:
            latex: LaTeX 公式字符串

        Returns:
            去除边界符后的公式
        """
        latex = latex.strip()
        if latex.startswith("\\[") and latex.endswith("\\]"):
            return latex[2:-2]
        if latex.startswith("$$") and latex.endswith("$$"):
            return latex[2:-2]
        if latex.startswith("\\(") and latex.endswith("\\)"):
            return latex[2:-2]
        if latex.startswith("$") and latex.endswith("$"):
            return latex[1:-1]
        return latex
