"""解析器基类模块"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Optional

from bs4 import BeautifulSoup, Tag
from bs4.element import Comment, NavigableString, PageElement

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
INLINE_CODE_TAGS = ("code",)  # 内联代码标签（区别于块级 pre）
LIST_ITEM_TAGS = ("li",)  # 列表项标签（单元素元组）
INLINE_NEUTRAL_TAGS = ("a", "u", "small", "del", "mark")  # 中性内联标签（不改变粗体/斜体状态）

# 内联结构检测用的块级元素集合（标签名硬匹配）
# 当段落/列表项内出现这些标签时，视为复杂内容，需要内联解析。
# 注意：此集合仅用于 _has_inline_structure 的硬匹配快速通道；
# 图片元素的检测同时依赖 _is_image_element 动态判断以支持子类扩展。
_INLINE_STRUCTURE_BLOCK_TAGS = set(IMAGE_TAGS) | set(TABLE_TAGS) | set(CODE_TAGS)

# =============================================================================
# 单个标签名常量（用于精确匹配，与标签组常量并存）
# =============================================================================

HTML_DIV = "div"
HTML_LI = "li"
HTML_PRE = "pre"
HTML_CODE = "code"
HTML_PICTURE = "picture"
HTML_UL = "ul"
HTML_OL = "ol"

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
INLINE_CODE_INLINE = "inline_code"   # 行内代码（区别于块级 pre）

# 复合类型元组（用于过滤非文本内联项）
INLINE_NON_TEXT_TYPES = (INLINE_LATEX, INLINE_IMAGE, INLINE_TABLE, INLINE_CODE, INLINE_CODE_INLINE)

# LaTeX 公式语言标识
LATEX_DISPLAY = "display"
LATEX_INLINE = "inline"

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
    list_marker: Optional[str] = None  # 列表标记（"•" 用于无序列表，"ol" 表示有序）
    list_start: Optional[int] = None  # 有序列表起始序号（仅当 list_marker="ol" 且为列表首项时有效）
    level: int = 0  # 嵌套层级（0 表示无嵌套或顶层）
    language: Optional[str] = None  # 代码语言（如 "python"）


# TextBlock 字段语义说明：
#   - type: 块类型：paragraph/latex/code/heading/list_item/table/blockquote/image
#   - language: 根据块类型承载不同含义：
#       heading -> 标题级别 (str: "1"~"6")
#       code -> 编程语言标识 (str: "python", "language-plaintext")
#       list_item -> 列表类型 (str: "ul" | "ol")
#       latex -> 公式类型 (str: "display" | "inline")
#       其他类型通常为 None
@dataclass
class TextBlock:
    """文本块"""
    type: str  # 块类型
    content: str  # 文本内容
    language: Optional[str] = None  # 用途见上方语义说明
    data: Any = None  # 附加数据（如 TableData）
    inline: bool = False  # 是否内联元素
    items: list[InlineContent] = field(default_factory=list)  # 内联内容列表
    level: int = 0  # 嵌套层级
    list_start: Optional[int] = None  # 有序列表起始序号（仅 list_item 类型有效）


@dataclass
class ParsedPage:
    """解析后的页面"""
    title: str = ""  # 页面标题
    blocks: list[TextBlock] = field(default_factory=list)  # 内容块列表
    latex_fallback_count: int = 0  # 公式识别回退计数：当 copy-text 属性缺失时触发策略2


@dataclass(frozen=True)
class WalkOptions:
    """遍历策略配置（不可变，遍历过程中配置不应改变）"""
    handle_line_break_div: bool = True  # True: 根据上下文智能判断是否在 line-break div 处插入换行；False: 忽略其换行语义，当作普通内联容器递归解析
    parse_div_span_inline: bool = True  # 递归解析 div/span 内联内容还是仅提取图片
    strip_nav_strings: bool = True  # 对 NavigableString 是否先 strip
    reset_format_to_parent: bool = True  # flush 后重置为父级状态
    handle_nested_lists: bool = False  # 处理 ul/ol 嵌套列表还是跳过
    list_level: int = 1  # 当前列表嵌套层级（1 表示第一层嵌套，0 表示顶层/无嵌套）


@dataclass
class _WalkContext:
    """封装 _walk_inline_children 过程中的运行时可变状态"""
    items: list[InlineContent] = field(default_factory=list)  # 内联内容列表
    current_text: str = ""  # 累积的文本
    current_bold: bool = False  # 当前加粗状态
    current_italic: bool = False  # 当前斜体状态
    parent_bold: bool = False  # 父级加粗状态
    parent_italic: bool = False  # 父级斜体状态
    options: WalkOptions = field(default_factory=WalkOptions)  # 遍历策略配置

    def __post_init__(self) -> None:
        """防御 None，确保 options 始终有效"""
        if self.options is None:
            self.options = WalkOptions()

    def flush(self) -> None:
        """将累积的文本 flush 到 items 列表"""
        # 检查是否有实际内容（非全空白），但保留原始格式化的 current_text
        # （首部无空格，尾部可能有空格，由 _append_normalized_text 保证）
        if self.current_text.strip():
            self.items.append(InlineContent(
                type=INLINE_TEXT,
                content=self.current_text,  # 保留可能存在的尾部空格
                bold=self.current_bold,
                italic=self.current_italic
            ))
        self.current_text = ""
        if self.options.reset_format_to_parent:
            self.current_bold = self.parent_bold
            self.current_italic = self.parent_italic
        else:
            self.current_bold = False
            self.current_italic = False


# =============================================================================
# BaseParser - 解析器抽象基类
# =============================================================================

class BaseParser(ABC):
    """
    解析器抽象基类

    ！！！重要：子类必须在 __init__ 中调用 super().__init__() 以初始化标签处理器映射。
    """
    config: ClassVar[PlatformConfig]  # 平台配置（子类必须设置）
    _tag_handlers: dict[str, Callable[[Tag, list[TextBlock]], None]]  # 标签 → 处理方法映射
    _walk_handler_map: dict[str, Callable[[Tag, "_WalkContext"], None]]  # 内联遍历分派映射

    def __init__(self) -> None:
        super().__init__()
        self._build_tag_handlers()
        self._walk_handler_map = self._build_walk_handler_map()

    def _build_tag_handlers(self) -> None:
        """构建标签名 → 处理方法的映射字典（幂等，可重复调用）"""
        h: dict[str, Callable[[Tag, list[TextBlock]], None]] = {}

        mapping: list[tuple[tuple[str, ...], Callable[[Tag, list[TextBlock]], None]]] = [
            (TABLE_TAGS, self._handle_table),
            (HEADING_TAGS, self._handle_heading),
            (LIST_TAGS, self._handle_list),
            (PARAGRAPH_TAGS, self._process_paragraph),
            (CODE_TAGS, self._handle_pre),
            (BLOCKQUOTE_TAGS, self._handle_blockquote),
            (BREAK_TAGS, self._handle_br),
            (IMAGE_TAGS, self._handle_picture),
            (SECTION_TAGS, self._handle_div_or_section),
            (INLINE_TAGS, self._handle_inline),
        ]
        h[HTML_DIV] = self._handle_div_or_section  # 单独注册，div 不在 INLINE_TAGS 中
        self._register_handlers(h, mapping)
        self._tag_handlers = h

    # -------------------------------------------------------------------------
    # 块级标签处理（由 _tag_handlers 分派）
    # -------------------------------------------------------------------------

    @staticmethod
    def _register_handlers(
        target: dict[str, Callable[..., None]],
        mapping: list[tuple[tuple[str, ...], Callable[..., None]]],
    ) -> None:
        """
        将 (标签组, 处理器) 对批量注册到目标字典中

        Args:
            target: 目标映射字典
            mapping: (标签组元组, 处理器) 列表
        """
        for tags, handler in mapping:
            for tag in tags:
                target[tag] = handler

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
        if self._is_code_expanded(element):
            return
        code = element.get_text("\n", strip=False).strip('\n')
        language = self._extract_code_language(element)
        blocks.append(TextBlock(type=BLOCK_CODE, content=code, language=language))

    def _handle_blockquote(self, element: Tag, blocks: list[TextBlock]) -> None:
        """处理引用标签 blockquote"""
        text = element.get_text(strip=True)
        if text:
            blocks.append(TextBlock(type=BLOCK_BLOCKQUOTE, content=text))

    def _handle_br(self, element: Tag, blocks: list[TextBlock]) -> None:
        """
        处理换行标签 br

        决策逻辑：
        - 如果上一个块是段落：将换行符追加到该段落末尾。
        - 否则：创建一个独立的换行段落块（将孤立 <br> 视为段分隔，
          而非行内换行，避免换行语义在无段落上下文中丢失）。
        """
        if self._last_block_is_paragraph(blocks):
            blocks[-1].content += "\n"
        else:
            blocks.append(TextBlock(type=BLOCK_PARAGRAPH, content="\n"))

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

    # -------------------------------------------------------------------------
    # 公开解析接口
    # -------------------------------------------------------------------------

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
        return any(c in class_names for c in classes)

    def _is_code_expanded(self, element: Tag) -> bool:
        """判断代码块是否已展开（属性值为 'true'）"""
        return element.get(self.config.code_expanded_attr) == "true"

    @staticmethod
    def _last_block_is_paragraph(blocks: list[TextBlock]) -> bool:
        """判断 blocks 最后一个元素的类型是否为段落"""
        return len(blocks) > 0 and blocks[-1].type == BLOCK_PARAGRAPH

    def _get_meaningful_children(self, element: Tag) -> list[PageElement]:
        """
        返回有意义（非注释、非空白文本）的子节点列表

        用于判断"唯一子元素"场景，过滤掉干扰判断的空白和注释。

        Args:
            element: HTML 元素

        Returns:
            有实质内容的子节点列表
        """
        result: list[PageElement] = []
        for child in element.children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                if str(child).strip():
                    result.append(child)
            elif isinstance(child, Tag):
                result.append(child)
        return result

    def _skip_whitespace_siblings(self, prev_sibling: PageElement | None) -> PageElement | None:
        """跳过连续的空白文本兄弟节点和注释节点"""
        while (prev_sibling is not None
               and isinstance(prev_sibling, NavigableString)
               and (isinstance(prev_sibling, Comment) or not str(prev_sibling).strip())):
            prev_sibling = prev_sibling.previous_sibling
        return prev_sibling

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
                    if isinstance(child, Comment):
                        continue
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
        # 直接查表分发（子类必须调用 super().__init__()）
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
            if self._last_block_is_paragraph(blocks):
                blocks[-1].content += " " + text
            else:
                blocks.append(TextBlock(type=BLOCK_PARAGRAPH, content=text))

    def _is_pure_inline_container(self, element: Tag) -> bool:
        """
        检查元素是否仅包含内联内容（无块级元素、无列表、无表格等）。
        块级标签集与 _handle_div_or_section 的逻辑对应。

        Args:
            element: HTML 元素

        Returns:
            True 如果元素仅包含内联内容，无块级后代
        """
        block_tags = {
            'p', 'div', 'section', 'table', 'ul', 'ol', 'pre',
            'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'
        }
        # 检查直接子级即可，无需深度遍历
        for child in element.children:
            if isinstance(child, Tag):
                if child.name in block_tags:
                    return False
                # 公式元素应作为独立公式块处理，不视为纯内联
                if self._is_math_element(child):
                    return False
        return True

    def _handle_div_or_section(self, element: Tag, blocks: list[TextBlock]) -> None:
        """
        处理 div 或 section 元素

        决策顺序：
        1. 如果是 line-break 类 div → 附加换行到上一个段落或新建空段落。
        2. 如果是代码展开按钮 → 提取展开后的 pre 代码。
        3. 如果是公式元素 → 作为独立公式块。
        4. 如果是代码容器 → 提取代码。
        5. 如果是图片元素 → 提取为图片块。
        6. 如果是图片包装器（含有特定类名）→ 提取内部所有图片。
        7. 如果是段落容器 → 按段落处理。
        8. 如果只包含单个 <p> 子元素 → 直接处理该段落。
        9. 其他情况 → 递归提取内部块级元素。
        """
        # line-break div：块级换行符处理
        if self._has_any_class(element, self.config.line_break_classes):
            if self._last_block_is_paragraph(blocks):
                blocks[-1].content += "\n"
            else:
                blocks.append(TextBlock(type=BLOCK_PARAGRAPH, content="\n"))
            return

        # 代码展开按钮
        if self._is_code_button(element):
            expanded_pre = element.find(HTML_PRE, attrs={self.config.code_expanded_attr: "true"})
            if expanded_pre:
                code = expanded_pre.get_text("\n", strip=False).strip('\n')
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

        # 图片包装器（通用，支持子类自定义图片元素）
        if self._has_any_class(element, [self.config.image_wrapper_class]):
            # 收集所有图片后代，过滤只保留无图片祖先的最外层图片
            image_elements = [
                d for d in element.descendants
                if isinstance(d, Tag) and self._is_image_element(d)
            ]
            if image_elements:
                outermost = []
                for img in image_elements:
                    # 检查所有祖先中是否有其他图片元素（表明当前是内层嵌套）
                    has_image_ancestor = any(
                        ancestor in image_elements for ancestor in img.parents
                        if isinstance(ancestor, Tag)
                    )
                    if not has_image_ancestor:
                        outermost.append(img)
                for img in outermost:
                    url = self._extract_image_url(img)
                    if url:
                        blocks.append(TextBlock(type=BLOCK_IMAGE, content=url))
            return

        # 段落容器
        if self._is_paragraph_container(element):
            self._process_paragraph(element, blocks)
            return

        # 查找单个 p 子元素（用于包裹简单段落）
        # 过滤掉空白文本和注释节点，确保"唯一子节点"的判断准确
        meaningful_children = self._get_meaningful_children(element)

        if (len(meaningful_children) == 1
                and isinstance(meaningful_children[0], Tag)
                and meaningful_children[0].name in PARAGRAPH_TAGS):
            # 唯一有意义子节点是 <p>，直接处理该段落
            self._process_element(meaningful_children[0], blocks)
        else:
            # 纯内联容器：作为内联段落处理，避免割裂
            if self._is_pure_inline_container(element):
                self._process_paragraph(element, blocks)
            else:
                # 其他情况：递归提取所有块
                sub_blocks = self._extract_blocks(element)
                blocks.extend(sub_blocks)

    def _process_code_container(self, element: Tag, blocks: list[TextBlock]) -> None:
        """
        处理代码块容器

        Args:
            element: 代码容器元素
            blocks: 内容块列表
        """
        code_elem = element.find(HTML_CODE)
        pre_elem = element.find(HTML_PRE)

        # 优先从 pre 标签提取代码
        if pre_elem:
            code_content = pre_elem.get_text("\n", strip=False).strip('\n')
        # 其次从 code 标签提取
        elif code_elem:
            code_content = code_elem.get_text("\n", strip=False).strip('\n')
        # 最后从元素自身提取
        else:
            code_content = element.get_text("\n", strip=False).strip('\n')
            if code_content.startswith("plaintext"):
                code_content = code_content[len("plaintext"):].lstrip("\n")

        if code_content:
            language = self._extract_code_language(element)
            blocks.append(TextBlock(type=BLOCK_CODE, content=code_content, language=language))

    @staticmethod
    def _extract_code_language(element: Tag) -> str:
        """
        从代码块元素中提取编程语言标识

        优先级：
        1. <code> 子元素 class 中的第一个 language-* 类名
        2. <code> 子元素 class 中所有非 hljs 类名拼接
        3. 容器 class 含 "plaintext" → "language-plaintext"
        4. 默认 "text"

        Args:
            element: 代码块根元素（pre 或代码容器）

        Returns:
            语言标识字符串，如 "python"、"language-plaintext"，默认 "text"
        """
        code_elem = element.find(HTML_CODE)
        if code_elem:
            classes = code_elem.get("class") or []
            # 优先查找 language-* 类名，返回第一个匹配项
            for cls in classes:
                if cls.startswith("language-"):
                    return cls
            # 回退：合并所有非 hljs 类名
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
        # 提取有序列表的 start 属性（默认 1）
        list_start = 1
        if list_type == HTML_OL:
            start_attr = element.get("start")
            if start_attr is not None:
                try:
                    list_start = int(start_attr)
                except ValueError:
                    list_start = 1

        list_items = element.find_all(HTML_LI, recursive=False)
        for i, li in enumerate(list_items):
            is_first = (i == 0)
            self._process_list_item(
                li, blocks, list_type, level,
                list_start=list_start if (list_type == HTML_OL and is_first) else None,
                is_first=is_first
            )

    def _process_list_item(
        self, li: Tag, blocks: list[TextBlock],
        list_type: str = "ul", level: int = 0,
        list_start: Optional[int] = None,
        is_first: bool = False
    ) -> None:
        """
        处理单个列表项

        决策逻辑：
        1. 检测是否包含复杂内容（嵌套列表、换行、加粗、公式、图片、表格、代码）。
        2. 如果包含复杂内容，委托给 _process_complex_list_item 解析内联结构。
        3. 否则直接提取文本作为简单列表项。

        Args:
            li: li 元素
            blocks: 内容块列表
            list_type: 列表类型 ("ul" 或 "ol")
            level: 嵌套层级
            list_start: 有序列表的起始序号（仅用于该列表的第一个 li，其余为 None）
            is_first: 是否为该列表的第一个 li
        """
        has_nested_list = li.find(LIST_TAGS, recursive=False)
        # 复用 _has_inline_structure 统一判断，支持 <a>, <u>, <small> 等所有内联格式标签
        if has_nested_list or self._has_inline_structure(li):
            self._process_complex_list_item(li, blocks, list_type, level, list_start, is_first)
            return

        # 简单列表项：直接提取文本
        text = li.get_text(strip=True)
        if text:
            blocks.append(TextBlock(
                type=BLOCK_LIST_ITEM,
                content=text,
                language=list_type,
                level=level,
                list_start=list_start if list_type == "ol" else None
            ))

    def _process_complex_list_item(
        self, li: Tag, blocks: list[TextBlock],
        list_type: str, level: int = 0,
        list_start: Optional[int] = None,
        is_first: bool = False
    ) -> None:
        """
        处理复杂的列表项

        Args:
            li: li 元素
            blocks: 内容块列表
            list_type: 列表类型
            level: 嵌套层级
            list_start: 有序列表的起始序号（仅用于该列表的第一个 li）
            is_first: 是否为该列表的第一个 li
        """
        items = self._walk_inline_children(
            li,
            parent_bold=False,
            parent_italic=False,
            options=WalkOptions(
                handle_line_break_div=True,
                parse_div_span_inline=True,
                strip_nav_strings=True,
                reset_format_to_parent=False,
                handle_nested_lists=True,
                list_level=level,
            ),
        )
        if items:
            valid_items = [
                item for item in items
                if item.type in INLINE_NON_TEXT_TYPES or item.content.strip() or item.content == "\n"
            ]
            if valid_items:
                # 清理首尾无意义的纯空白/换行项（与 _walk_handle_list 保持一致）
                while valid_items and valid_items[0].type == INLINE_TEXT and not valid_items[0].content.strip():
                    valid_items.pop(0)
                while valid_items and valid_items[-1].type == INLINE_TEXT and not valid_items[-1].content.strip():
                    valid_items.pop()

                # 确定标记符号：有序列表用 "ol"，无序列表用 "•"
                marker = "ol" if list_type == "ol" else ("•" if list_type == "ul" else None)

                if marker:
                    # 清理后无有效项，创建纯占位符保留项目符号
                    if not valid_items:
                        placeholder = InlineContent(
                            type=INLINE_TEXT,
                            content="",
                            list_marker=marker,
                            level=level,
                        )
                        if marker == "ol" and is_first:
                            placeholder.list_start = list_start if list_start is not None else 1
                        valid_items = [placeholder]
                    else:
                        # 检查第一个元素：文本直接赋予标记，非文本则插入占位符
                        first = valid_items[0]
                        if first.type == INLINE_TEXT:
                            # 第一个就是文本，直接赋予标记
                            first.list_marker = marker
                            if marker == "ol" and is_first:
                                first.list_start = list_start if list_start is not None else 1
                        else:
                            # 第一个不是文本，插入占位符承载标记
                            placeholder = InlineContent(
                                type=INLINE_TEXT,
                                content="",
                                list_marker=marker,
                                level=level,
                            )
                            if marker == "ol" and is_first:
                                placeholder.list_start = list_start if list_start is not None else 1
                            valid_items.insert(0, placeholder)

                blocks.append(TextBlock(type=BLOCK_LIST_ITEM, content="", language=list_type, items=valid_items, level=level))

    def _append_normalized_text(self, text: str, ctx: _WalkContext) -> None:
        """
        将文本按照选项规范化后追加到上下文累积文本中。

        确保相邻单词间保持空格分隔（如 `<p>Hello<span>world</span></p>` 不会变成 "Helloworld"）。

        Args:
            text: 原始文本
            ctx: 遍历上下文
        """
        if ctx.options.strip_nav_strings:
            # 将连续空白压缩为单空格，但只去除首部空白，保留尾部空格
            # （用于分隔跨标签的单词，如 "Hello <b>world</b>"）
            text = re.sub(r'\s+', ' ', text)
            if text.startswith(' '):
                text = text[1:]
        else:
            text = re.sub(r'\s+', ' ', text)
        if not text:
            return
        if ctx.current_text and not ctx.current_text.endswith(' '):
            ctx.current_text += ' '
        ctx.current_text += text

    def _walk_inline_children(
        self,
        element: Tag,
        *,
        parent_bold: bool = False,
        parent_italic: bool = False,
        options: Optional[WalkOptions] = None,
    ) -> list[InlineContent]:
        """
        统一遍历内联子元素并返回 InlineContent 列表

        该方法是三个内联处理方法的公共核心，通过 options 控制细微行为差异。

        Args:
            element: 待遍历的 HTML 元素
            parent_bold: 继承的父级加粗状态
            parent_italic: 继承的父级斜体状态
            options: 遍历策略配置，默认为 WalkOptions()

        Returns:
            InlineContent 列表
        """
        if options is None:
            options = WalkOptions()
        # 直接使用映射（子类必须调用 super().__init__()）
        ctx = _WalkContext(
            parent_bold=parent_bold,
            parent_italic=parent_italic,
            current_bold=parent_bold,
            current_italic=parent_italic,
            options=options,
        )

        # 使用缓存的分派映射
        for child in element.children:
            if isinstance(child, NavigableString):
                if isinstance(child, Comment):
                    continue
                self._append_normalized_text(str(child), ctx)
            elif isinstance(child, Tag):
                # 公式元素（动态判断）
                if self._is_math_element(child):
                    self._walk_handle_math(child, ctx)
                    continue
                # 图片元素（动态判断，子类可通过 _is_image_element 定义）
                if self._is_image_element(child):
                    self._walk_handle_image(child, ctx)
                    continue
                # 查表分发
                handler = self._walk_handler_map.get(child.name, self._walk_default_handler)
                handler(child, ctx)

        ctx.flush()
        return ctx.items

    # -------------------------------------------------------------------------
    # 内联遍历处理器（由 _walk_inline_children 分发）
    # -------------------------------------------------------------------------

    def _build_walk_handler_map(self) -> dict[str, Callable[[Tag, _WalkContext], None]]:
        """
        构建标签名 → 处理方法的映射字典

        注意：IMAGE_TAGS 的注册作为"文档化/备选"角色。
        在 _walk_inline_children 中，动态 _is_image_element 检测优先于此处注册。
        当子类的 _is_image_element 对 <picture> 返回 True 时，此处映射不会被执行。

        Returns:
            标签名到处理方法的映射字典
        """
        h: dict[str, Callable[[Tag, _WalkContext], None]] = {}

        # 批量注册处理器
        mapping: list[tuple[tuple[str, ...], Callable[[Tag, _WalkContext], None]]] = [
            (BOLD_TAGS, self._walk_handle_bold),
            (ITALIC_TAGS, self._walk_handle_italic),
            (BREAK_TAGS, self._walk_handle_br),
            (TABLE_TAGS, self._walk_handle_table),
            (CODE_TAGS, self._walk_handle_code),
            (INLINE_CODE_TAGS, self._walk_handle_inline_code),
            (PARAGRAPH_TAGS, self._walk_handle_paragraph),
            (LIST_TAGS, self._walk_handle_list),
            (INLINE_CONTAINER_TAGS, self._walk_handle_inline_container),
            # 中性内联标签：不改变格式状态，委托给 _walk_handle_format（set_bold=False, set_italic=False）
            (INLINE_NEUTRAL_TAGS, lambda child, ctx: self._walk_handle_format(child, ctx, set_bold=False, set_italic=False)),
        ]
        self._register_handlers(h, mapping)

        # 图片元素：作为文档化/备选注册（实际由 _is_image_element 动态检测优先）
        for tag in IMAGE_TAGS:
            h[tag] = self._walk_handle_image

        return h

    def _walk_handle_math(self, child: Tag, ctx: _WalkContext) -> None:
        """处理公式元素"""
        ctx.flush()
        latex = self._extract_latex_content(child)
        latex = self._strip_latex_delimiters(latex)
        is_display = self._is_display_math(child)
        ctx.items.append(InlineContent(type=INLINE_LATEX, content=latex, is_display=is_display))

    def _walk_handle_format(self, child: Tag, ctx: _WalkContext, *, set_bold: bool, set_italic: bool) -> None:
        """
        统一处理加粗/斜体标签的内联遍历。

        将当前累积文本 flush 后递归遍历子节点。
        子节点继承叠加后的格式状态：若本标签设置了格式（set_bold=True），
        则无论外部状态如何，子节点均获得该格式；否则继续沿用外部状态。
        例如 <b>bold <em>both</em></b> 中，em 内部会同时继承外层的加粗。
        """
        ctx.flush()
        ctx.items.extend(
            self._walk_inline_children(
                child,
                parent_bold=set_bold or ctx.current_bold,
                parent_italic=set_italic or ctx.current_italic,
                options=ctx.options,
            )
        )

    def _walk_handle_bold(self, child: Tag, ctx: _WalkContext) -> None:
        """处理加粗标签 (strong, b)"""
        self._walk_handle_format(child, ctx, set_bold=True, set_italic=False)

    def _walk_handle_italic(self, child: Tag, ctx: _WalkContext) -> None:
        """处理斜体标签 (em, i)"""
        self._walk_handle_format(child, ctx, set_bold=False, set_italic=True)

    def _walk_handle_br(self, child: Tag, ctx: _WalkContext) -> None:
        """处理换行标签 (br)"""
        ctx.flush()
        ctx.items.append(InlineContent(type=INLINE_TEXT, content="\n"))

    def _walk_handle_line_break_div(self, child: Tag, ctx: _WalkContext) -> None:
        """
        处理 line-break-class div

        注意：此方法仅在 handle_line_break_div=True 时被调用。
        False 的情况由 _walk_handle_inline_container 统一处理为普通容器递归。

        决策逻辑：
        | 前一个兄弟类型          | 条件              | 是否插入换行 |
        |------------------------|-------------------|-------------|
        | 空 line-break div      | 无文本            | 否（折叠连续空行）|
        | 列表标签 (ul/ol)       | 任何情况          | 否          |
        | 其他 Tag / NavigableString | 任何情况        | 是          |
        | None (第一个子元素)    | -                 | 是          |
        """
        # 第一个子元素：直接添加换行
        if child.previous_sibling is None:
            ctx.flush()
            ctx.items.append(InlineContent(type=INLINE_TEXT, content="\n"))
            return

        prev = self._skip_whitespace_siblings(child.previous_sibling)
        ctx.flush()

        if self._should_insert_break_before_line_break_div(prev):
            ctx.items.append(InlineContent(type=INLINE_TEXT, content="\n"))

    def _should_insert_break_before_line_break_div(self, prev: PageElement | None) -> bool:
        """
        判断当前 line-break div 之前是否需要插入换行符

        Args:
            prev: 前一个兄弟元素（已跳过空白文本）

        Returns:
            True 需要插入换行符，False 不插入
        """
        if prev is None:
            return True
        if isinstance(prev, Tag):
            # 连续的空 line-break div：跳过插入换行，避免多余空行
            if (prev.name in INLINE_CONTAINER_TAGS
                    and self._has_any_class(prev, self.config.line_break_classes)
                    and not prev.get_text(strip=True)):
                return False
            # 列表标签后：不插入
            if prev.name in LIST_TAGS:
                return False
        # 其他情况（NavigableString 或其他 Tag）：插入换行
        return True

    def _walk_handle_image(self, child: Tag, ctx: _WalkContext) -> None:
        """处理图片元素 (picture)"""
        ctx.flush()
        url = self._extract_image_url(child)
        if url:
            ctx.items.append(InlineContent(type=INLINE_IMAGE, content="", image_url=url))

    def _walk_handle_table(self, child: Tag, ctx: _WalkContext) -> None:
        """处理表格元素 (table)"""
        ctx.flush()
        table_data = self._parse_table(child)
        if table_data:
            ctx.items.append(InlineContent(type=INLINE_TABLE, content="", data=table_data, bold=ctx.current_bold, italic=ctx.current_italic))

    def _walk_handle_code(self, child: Tag, ctx: _WalkContext) -> None:
        """处理代码块 (pre)"""
        # 仅当代码未展开时处理
        if not self._is_code_expanded(child):
            ctx.flush()
            code_content = child.get_text("\n", strip=False).strip('\n')
            language = self._extract_code_language(child)
            ctx.items.append(InlineContent(type=INLINE_CODE, content=code_content,
                               bold=ctx.current_bold, italic=ctx.current_italic,
                               language=language))

    def _walk_handle_inline_code(self, child: Tag, ctx: _WalkContext) -> None:
        """处理内联代码标签 (code)"""
        ctx.flush()
        code_content = child.get_text()  # 保留内部空格，不 strip
        ctx.items.append(InlineContent(
            type=INLINE_CODE_INLINE,
            content=code_content,
            bold=ctx.current_bold,
            italic=ctx.current_italic,
        ))

    def _walk_handle_paragraph(self, child: Tag, ctx: _WalkContext) -> None:
        """处理段落 (p)"""
        ctx.flush()
        ctx.items.extend(
            self._walk_inline_children(
                child, parent_bold=ctx.current_bold, parent_italic=ctx.current_italic,
                options=ctx.options,
            )
        )

    @staticmethod
    def _find_first_text_item(items: list[InlineContent]) -> Optional[InlineContent]:
        """返回列表中第一个 INLINE_TEXT 项，若没有则返回 None"""
        for item in items:
            if item.type == INLINE_TEXT:
                return item
        return None

    def _walk_handle_list(self, child: Tag, ctx: _WalkContext) -> None:
        """处理列表 (ul, ol) - 完整解析每个 li 的内联内容"""
        if not ctx.options.handle_nested_lists:
            # 不解析嵌套列表结构，但保留纯文本避免信息丢失
            text = child.get_text()
            if text.strip():
                self._append_normalized_text(text, ctx)
            return

        # 保存格式状态，flush 会重置 current_bold/italic
        saved_bold = ctx.current_bold
        saved_italic = ctx.current_italic
        ctx.flush()

        list_type = child.name  # "ul" 或 "ol"
        current_level = ctx.options.list_level + 1

        # 解析有序列表的起始序号（默认 1）
        ol_start = 1
        if list_type == HTML_OL:
            start_attr = child.get("start")
            if start_attr is not None:
                try:
                    ol_start = int(start_attr)
                except ValueError:
                    ol_start = 1

        li_tags = child.find_all(LIST_ITEM_TAGS, recursive=False)
        for idx, li in enumerate(li_tags):
            is_first_li = (idx == 0)
            # 解析当前 li 的全部内联内容（允许更深层列表）
            li_items = self._walk_inline_children(
                li,
                parent_bold=saved_bold,
                parent_italic=saved_italic,
                options=WalkOptions(
                    handle_line_break_div=ctx.options.handle_line_break_div,
                    parse_div_span_inline=ctx.options.parse_div_span_inline,
                    strip_nav_strings=ctx.options.strip_nav_strings,
                    reset_format_to_parent=False,
                    handle_nested_lists=True,
                    list_level=current_level,
                ),
            )

            # 清理首尾无意义的纯空白/换行项
            while li_items and li_items[0].type == INLINE_TEXT and not li_items[0].content.strip():
                li_items.pop(0)
            while li_items and li_items[-1].type == INLINE_TEXT and not li_items[-1].content.strip():
                li_items.pop()

            # 完全空的列表项也需创建占位符（保留项目符号）
            if not li_items:
                if list_type == HTML_UL:
                    placeholder = InlineContent(
                        type=INLINE_TEXT,
                        content="",
                        list_marker="•",
                        level=current_level,
                    )
                else:  # 有序列表：仅标记，不拼接序号
                    placeholder = InlineContent(
                        type=INLINE_TEXT,
                        content="",
                        list_marker="ol",
                        level=current_level,
                    )
                    # 首个 li 设置 list_start（即使没有 start 属性也设为 1，保证独立列表编号重置）
                    if is_first_li:
                        placeholder.list_start = ol_start
                ctx.items.append(placeholder)
                continue  # 跳过后续标记处理，避免重复

            # 构造列表标记 / 序号：检查第一个元素是否为文本
            # 确保标记始终与第一个元素绑定（若首元素非文本则插入占位符）
            if li_items and li_items[0].type == INLINE_TEXT:
                first_text = li_items[0]
                if list_type == HTML_UL:
                    first_text.list_marker = "•"
                    first_text.level = current_level
                else:  # 有序列表：仅标记，不拼接序号
                    first_text.list_marker = "ol"
                    first_text.level = current_level
                    if is_first_li:
                        first_text.list_start = ol_start
            else:
                # 第一个不是文本，插入占位符承载标记
                marker = "•" if list_type == HTML_UL else "ol"
                placeholder = InlineContent(
                    type=INLINE_TEXT,
                    content="",
                    list_marker=marker,
                    level=current_level,
                )
                if list_type == HTML_OL and is_first_li:
                    placeholder.list_start = ol_start
                li_items.insert(0, placeholder)

            # 为所有文本项统一设置层级，用于 docx_builder 的续写缩进
            for item in li_items:
                if item.type == INLINE_TEXT and item.level == 0:
                    item.level = current_level

            ctx.items.extend(li_items)

    def _walk_handle_inline_container(self, child: Tag, ctx: _WalkContext) -> None:
        """处理内联容器 div/span"""
        # 只有明确要求处理 line-break 时才走专用逻辑
        # handle_line_break_div=False：忽略 line-break 语义，当作普通容器递归解析
        if self._has_any_class(child, self.config.line_break_classes):
            if ctx.options.handle_line_break_div:
                self._walk_handle_line_break_div(child, ctx)
                return
            # 否则：忽略 line-break 语义，继续执行后续普通容器递归

        if not ctx.options.parse_div_span_inline:
            return  # 不解析内联内容

        # 统一递归处理内联子元素，不再区分是否包含块级元素
        ctx.flush()
        ctx.items.extend(
            self._walk_inline_children(
                child, parent_bold=ctx.current_bold, parent_italic=ctx.current_italic,
                options=ctx.options,
            )
        )

    def _walk_default_handler(self, child: Tag, ctx: _WalkContext) -> None:
        """默认处理（其他标签）"""
        sub_text = child.get_text(strip=False)
        self._append_normalized_text(sub_text, ctx)

    def _has_inline_structure(self, element: Tag) -> bool:
        """
        判断元素内部是否包含需要内联处理的结构（如格式标签、换行、图片等）。

        检测逻辑（按优先级）：
        1. 标签名快速检查：内联格式标签、内联代码、换行标签、块级元素。
        2. 类名语义检测：div/span 携带 line-break 或 image-wrapper 类名。
        3. 平台自定义内联结构：子类可覆盖 _platform_specific_inline_structure 扩展。
        4. 公式元素检测：在遍历过程中检测，避免二次后代遍历。

        子类可覆盖此方法或 _platform_specific_inline_structure 扩展平台特有逻辑。

        Args:
            element: HTML 元素

        Returns:
            True 如果包含需要内联处理的结构
        """
        # 1. 标签名快速检查
        for child in element.descendants:
            if not isinstance(child, Tag):
                continue

            # 内联格式标签 (strong, em, a, span, code, etc.)
            if child.name in INLINE_TAGS:
                return True
            # 内联代码 (code)
            if child.name in INLINE_CODE_TAGS:
                return True
            # 换行标签 (br)
            if child.name in BREAK_TAGS:
                return True
            # 段落内嵌块级元素（异常但应保留）
            if child.name in _INLINE_STRUCTURE_BLOCK_TAGS:
                return True
            if child.name in PARAGRAPH_TAGS:
                return True
            # 列表标签（嵌套列表结构）
            if child.name in LIST_TAGS:
                return True

            # 2. 类名语义检测（div / span 携带语义 class）
            if child.name in INLINE_CONTAINER_TAGS:
                if self._has_any_class(child, self.config.line_break_classes):
                    return True
                if self._has_any_class(child, [self.config.image_wrapper_class]):
                    return True

            # 3. 平台自定义内联结构
            if self._platform_specific_inline_structure(child):
                return True

            # 4. 公式元素检测
            if self._is_math_element(child):
                return True

            # 5. 图片元素检测（子类可扩展 <img> 等）
            if self._is_image_element(child):
                return True

        return False

    def _platform_specific_inline_structure(self, element: Tag) -> bool:
        """
        子类可覆盖：检测平台特有的内联结构。
        默认返回 False，保持向后兼容。

        Args:
            element: HTML 元素

        Returns:
            True 如果元素是平台特有的内联结构
        """
        return False

    def _process_paragraph(self, element: Tag, blocks: list[TextBlock]) -> None:
        """
        处理段落元素

        决策逻辑：
        1. 如果不是复杂段落（无内联结构）→ 直接提取纯文本作为段落块。
        2. 如果是复杂段落 → 调用 _walk_inline_children 解析内联内容。

        参数:
            element: p 元素
            blocks: 内容块列表
        """
        # 简单段落：直接提取文本
        if not self._has_inline_structure(element):
            text = element.get_text(strip=True)
            if text:
                blocks.append(TextBlock(type=BLOCK_PARAGRAPH, content=text))
            return

        # 复杂段落：解析内联内容
        items = self._walk_inline_children(
            element,
            parent_bold=False,
            parent_italic=False,
            options=WalkOptions(
                handle_line_break_div=True,  # 启用智能换行，保留段落内显式换行
                parse_div_span_inline=True,  # 允许解析 div/span 内联内容
                strip_nav_strings=True,  # 规范化空白
                reset_format_to_parent=False,
                handle_nested_lists=False,
            ),
        )
        if items:
            blocks.append(TextBlock(type=BLOCK_PARAGRAPH, content="", items=items))

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
            options=WalkOptions(
                handle_line_break_div=True,
                handle_nested_lists=False,
                list_level=1,
            ),
        )
        if items:
            blocks.append(TextBlock(type=BLOCK_PARAGRAPH, content="", items=items))
        else:
            text = element.get_text(strip=True)
            if text:
                # 纯文本段落，不再用 language 字段标记加粗
                blocks.append(TextBlock(type=BLOCK_PARAGRAPH, content=text))

    def _process_math_element(self, element: Tag, blocks: list[TextBlock]) -> None:
        """
        处理公式元素，生成独立的公式块

        行内公式的识别与合并已由 _walk_inline_children 在解析内联内容时完成，
        本方法只处理作为独立块出现的公式元素。

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

    # -------------------------------------------------------------------------
    # 辅助方法
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_table(table: Tag) -> Optional[TableData]:
        """
        解析表格，支持列数不一致的对齐

        Args:
            table: table 元素

        Returns:
            TableData 对象，解析失败返回 None
        """
        headers = []  # 表头文本列表
        header_bold = []  # 表头加粗标记
        raw_rows_data: list[list[str]] = []  # 原始数据行列表
        raw_rows_bold: list[list[bool]] = []  # 原始加粗标记列表

        # 1. 解析 <thead> 表头（仅当 thead 及其内确实有 tr 时才视为已识别表头）
        thead = table.find("thead")
        header_row = thead.find("tr") if thead else None
        if thead and header_row:
            for th in header_row.find_all(["th", "td"]):
                headers.append(th.get_text(strip=True))
                header_bold.append((th.name == "th") or (th.find(BOLD_TAGS) is not None))

        # 2. 收集所有数据行
        data_rows: list[Tag] = []

        # 优先从 <tbody> 提取
        tbody = table.find("tbody")
        if tbody:
            data_rows = tbody.find_all("tr", recursive=False)

        # 若仍为空，尝试 <tfoot>
        if not data_rows:
            tfoot = table.find("tfoot")
            if tfoot:
                data_rows = tfoot.find_all("tr", recursive=False)

        # 兜底：从 table 直接子级收集
        if not data_rows:
            all_direct_tr = table.find_all("tr", recursive=False)
            if header_row is not None and header_row in all_direct_tr:
                all_direct_tr.remove(header_row)
            data_rows = all_direct_tr

        # 没有显式表头但数据行足够，提升第一行为表头
        if not headers and len(data_rows) >= 2:
            first_tr = data_rows.pop(0)
            for td in first_tr.find_all(["th", "td"]):
                headers.append(td.get_text(strip=True))
                is_bold = (td.name == "th") or (td.find(BOLD_TAGS) is not None)
                header_bold.append(is_bold)

        # 收集数据行（暂存，稍后对齐）
        for tr in data_rows:
            row_data = []
            row_bold = []
            for td in tr.find_all(["th", "td"]):
                row_data.append(td.get_text(strip=True))
                row_bold.append(td.find(BOLD_TAGS) is not None)
            if row_data:
                raw_rows_data.append(row_data)
                raw_rows_bold.append(row_bold)

        if not headers and not raw_rows_data:
            return None

        # 3. 对齐列数：始终以表头与所有数据行的最大列数为准
        max_cols = len(headers)
        for row in raw_rows_data:
            max_cols = max(max_cols, len(row))

        # 对齐表头
        if len(headers) < max_cols:
            headers.extend([""] * (max_cols - len(headers)))
            header_bold.extend([False] * (max_cols - len(header_bold)))

        # 4. 对齐数据行并构建结果
        rows = []
        cell_bold = []
        for i, row in enumerate(raw_rows_data):
            if len(row) < max_cols:
                row.extend([""] * (max_cols - len(row)))
                raw_rows_bold[i].extend([False] * (max_cols - len(raw_rows_bold[i])))
            rows.append(row)
            cell_bold.append(raw_rows_bold[i])

        # 极端情况兜底：表头为空但有数据行
        if not headers and rows:
            headers = rows[0]
            header_bold = cell_bold[0] if cell_bold else [False] * len(headers)
            rows = rows[1:]
            cell_bold = cell_bold[1:] if cell_bold else []

        return TableData(headers=headers, rows=rows, header_bold=header_bold, cell_bold=cell_bold)

    @staticmethod
    def _strip_latex_delimiters(latex: str) -> str:
        """
        去除 LaTeX 公式的边界符（成对匹配）

        Args:
            latex: LaTeX 公式字符串

        Returns:
            去除边界符后的公式
        """
        latex = latex.strip()
        if latex.startswith("\\[") and latex.endswith("\\]"):
            return latex[2:-2]
        elif latex.startswith("$$") and latex.endswith("$$"):
            return latex[2:-2]
        elif latex.startswith("\\(") and latex.endswith("\\)"):
            return latex[2:-2]
        elif latex.startswith("$") and latex.endswith("$"):
            return latex[1:-1]
        return latex
