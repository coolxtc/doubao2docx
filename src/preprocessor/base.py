"""
解析器基类模块

定义解析器的抽象基类和平台配置，支持多平台扩展。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any, Union, Callable

from bs4 import BeautifulSoup, Tag, NavigableString

from ..exceptions import ParseError


# =============================================================================
# PlatformConfig - 平台配置
# =============================================================================

@dataclass
class PlatformConfig:
    """平台配置数据类 - 集中管理各平台的差异配置"""
    name: str = "doubao"
    latex_attr: str = "data-custom-copy-text"
    math_display_classes: list[str] = field(default_factory=lambda: ["math-block", "katex--display"])
    line_break_classes: list[str] = field(default_factory=lambda: ["md-box-line-break", "line-break"])
    code_container_class: str = "custom-code-block-container"
    code_button_pattern: str = "button-"
    code_expanded_attr: str = "data-expanded-code"
    message_item_selector: str = "[class*='message-item']"
    user_message_class: str = "justify-end"
    heading_selectors: str = "h1, .chat-title, [class*='title']"
    paragraph_prefix: str = "paragraph-"
    parser: str = "lxml"
    picture_container_class: str = "picture"
    image_wrapper_class: str = "image-wrapper"


# =============================================================================
# 数据类型 - 与平台无关，可直接复用
# =============================================================================

@dataclass
class TableData:
    """表格数据 - 存储表格的行列信息"""
    headers: list[str]
    rows: list[list[str]]
    header_bold: list[bool] = field(default_factory=list)
    cell_bold: list[list[bool]] = field(default_factory=list)


@dataclass
class InlineContent:
    type: str
    content: str
    is_display: bool = False
    bold: bool = False
    italic: bool = False
    image_url: Optional[str] = None
    data: Any = None
    list_marker: Optional[str] = None  # 列表标记："•" 用于无序列表
    level: int = 0  # 嵌套层级（0 表示无嵌套或顶层）


@dataclass 
class TextBlock:
    type: str
    content: str
    language: Optional[str] = None
    data: Any = None
    inline: bool = False
    items: list[InlineContent] = field(default_factory=list)
    level: int = 0


@dataclass
class ParsedPage:
    """解析后的页面 - 包含整个文档的解析结果"""
    title: str = ""
    blocks: list[TextBlock] = field(default_factory=list)


# =============================================================================
# BaseParser - 解析器抽象基类
# =============================================================================

class BaseParser(ABC):
    """解析器抽象基类 - 定义统一接口"""
    
    # 子类必须设置此属性
    config: PlatformConfig
    
    # -------------------------------------------------------------------------
    # 模板方法 - 提供解析流程骨架
    # -------------------------------------------------------------------------
    
    def parse(self, html: str) -> ParsedPage:
        """解析 HTML 页面 - 模板方法入口
        
        Args:
            html: HTML 字符串
            
        Returns:
            ParsedPage: 包含 title 和 blocks 的解析结果
        """
        return self._parse_impl(html)
    
    def _parse_impl(self, html: str) -> ParsedPage:
        """解析实现 - 可被子类覆盖
        
        默认实现提供了完整的解析流程骨架。
        如果子类需要完全自定义解析逻辑，可以覆盖此方法。
        
        Args:
            html: HTML 字符串
            
        Returns:
            ParsedPage: 解析结果
        """
        soup = BeautifulSoup(html, self.config.parser)
        
        # 提取标题
        title = self._extract_title(soup)
        
        # 获取内容容器（优先用 body，没有就用整个文档）
        container = soup.body if soup.body else soup
        
        # 提取所有内容块
        blocks = self._extract_blocks(container)
        
        return ParsedPage(title=title, blocks=blocks)
    
    # -------------------------------------------------------------------------
    # 抽象钩子方法 - 子类必须实现
    # -------------------------------------------------------------------------
    
    @abstractmethod
    def _get_title_selectors(self) -> list[str]:
        """获取标题选择器列表
        
        返回用于查找页面标题的 CSS 选择器列表。
        基类使用第一个匹配的选择器。
        
        Returns:
            CSS 选择器字符串列表，如 ["h1", ".title", "[class*='title']"]
        """
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
    # 通用方法 - 不依赖平台特定逻辑
    # -------------------------------------------------------------------------
    
    def _has_any_class(self, element: Tag, class_names: list[str]) -> bool:
        """检查元素是否包含指定类名中的任意一个

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
    
    def _skip_whitespace_siblings(self, prev_sibling) -> Any:
        """跳过连续的空白文本兄弟节点"""
        while prev_sibling is not None and isinstance(prev_sibling, NavigableString) and not str(prev_sibling).strip():
            prev_sibling = prev_sibling.previous_sibling
        return prev_sibling
    
    def _handle_line_break(self, prev_sibling: Any, items: list[InlineContent], 
                           current_text: str, current_bold: bool, current_italic: bool,
                           parent_bold: bool, parent_italic: bool,
                           flush_fn: Optional[Callable[..., Any]] = None) -> tuple[str, bool, bool]:
        """处理 div.line-break 换行符"""
        prev = self._skip_whitespace_siblings(prev_sibling)
        
        # 修复：跳过空白的 md-box-line-break div（豆包页面中常见的空换行容器）
        if isinstance(prev, Tag):
            if (prev.name == "div" and self._has_any_class(prev, self.config.line_break_classes) 
                and not prev.get_text(strip=True)):
                return "", parent_bold, parent_italic
        
        if isinstance(prev, NavigableString):
            return "", parent_bold, parent_italic
        elif isinstance(prev, Tag) and prev.name in ("ul", "ol"):
            return "", parent_bold, parent_italic
        elif isinstance(prev, Tag) and prev.name in ("div", "span"):
            return "", parent_bold, parent_italic
        else:
            if flush_fn:
                flush_fn()
            else:
                stripped = current_text.strip()
                if stripped:
                    items.append(InlineContent(
                        type="text", 
                        content=stripped, 
                        bold=current_bold,
                        italic=current_italic
                    ))
            items.append(InlineContent(type="text", content="\n"))
            return "", parent_bold, parent_italic
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """提取标题"""
        # 尝试使用选择器
        for selector in self._get_title_selectors():
            tag = soup.select_one(selector)
            if tag:
                return tag.get_text(strip=True)
        
        # 备选：<title> 标签
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)
        
        return ""
    
    def _extract_blocks(self, container: Tag) -> list[TextBlock]:
        """从容器中提取所有内容块"""
        blocks = []
        
        for child in container.children:
            # NavigableString 是文本节点
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    blocks.append(TextBlock(type="paragraph", content=text))
            # Tag 是 HTML 标签
            elif isinstance(child, Tag):
                self._process_element(child, blocks)
        
        return blocks
    
    def _process_element(self, element: Tag, blocks: list[TextBlock]) -> None:
        """处理单个元素 - 根据标签类型分发处理"""
        tag = element.name
        
        # 表格
        if tag == "table":
            table_data = self._parse_table(element)
            if table_data:
                blocks.append(TextBlock(type="table", content="", data=table_data))
            return
        
        # 标题 (h1-h6)
        if tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            text = element.get_text(strip=True)
            if text:
                level = int(tag[1]) if len(tag) == 2 else 1
                blocks.append(TextBlock(type="heading", content=text, language=str(level)))
            return
        
        # 无序列表
        if tag == "ul":
            self._process_list(element, "ul", blocks, 0)
            return
        
        # 有序列表
        if tag == "ol":
            self._process_list(element, "ol", blocks, 0)
            return
        
        # 段落
        if tag == "p":
            self._process_paragraph(element, blocks)
            return
        
        # 预格式化代码块
        if tag == "pre":
            if element.get(self.config.code_expanded_attr):
                return
            code = element.get_text("\n", strip=True)
            lang = ""
            code_elem = element.find("code")
            if code_elem:
                lang = code_elem.get("class") or []
                lang = " ".join([c for c in lang if c != "hljs"]) if lang else ""
            blocks.append(TextBlock(type="code", content=code, language=lang or "text"))
            return
        
        # 引用
        if tag == "blockquote":
            text = element.get_text(strip=True)
            if text:
                blocks.append(TextBlock(type="blockquote", content=text))
            return
        
        # 换行标签
        if tag == "br":
            if blocks and blocks[-1].type == "paragraph":
                blocks[-1].content += "\n"
            return
        
        # picture 图片标签
        if tag == "picture":
            url = self._extract_image_url(element)
            if url:
                blocks.append(TextBlock(type="image", content=url))
            return
        
        # div 或 section 容器
        if tag == "div" or tag == "section":
            self._process_div_or_section(element, blocks)
            return
        
        # 内联标签（strong, em, span, a, b, i, u, small, del, mark）
        inline_tags = {"strong", "em", "span", "a", "b", "i", "u", "small", "del", "mark"}
        if tag in inline_tags:
            
            if self._is_math_element(element):
                self._process_math_element(element, blocks)
                return
            self._process_inline_element(element, blocks)
            return

        # 使用钩子判断是否为公式元素
        if self._is_math_element(element):
            self._process_math_element(element, blocks)
            return

        # 使用钩子判断是否为图片元素
        if self._is_image_element(element):
            url = self._extract_image_url(element)
            if url:
                blocks.append(TextBlock(type="image", content=url))
            return

        if self._is_paragraph_container(element):
            self._process_paragraph(element, blocks)
            return

        # 其他情况：提取文本并追加到上一个段落
        text = element.get_text(strip=True)
        if text:
            if blocks and blocks[-1].type == "paragraph":
                blocks[-1].content += " " + text
            else:
                blocks.append(TextBlock(type="paragraph", content=text))

    def _process_div_or_section(self, element: Tag, blocks: list[TextBlock]) -> None:
        """处理 div 或 section 元素"""
        if self._is_code_button(element):
            expanded_pre = element.find("pre", attrs={self.config.code_expanded_attr: "true"})
            if expanded_pre:
                code = expanded_pre.get_text("\n", strip=True)
                blocks.append(TextBlock(type="code", content=code, language="language-plaintext"))
            return

        if self._is_math_element(element):
            self._process_math_element(element, blocks)
            return

        if self._is_code_container(element):
            self._process_code_container(element, blocks)
            return

        if self._is_image_element(element):
            url = self._extract_image_url(element)
            if url:
                blocks.append(TextBlock(type="image", content=url))
            return

        if self._is_paragraph_container(element):
            self._process_paragraph(element, blocks)
            return

        p_child = None
        for child in element.children:
            if isinstance(child, Tag) and child.name == "p":
                if p_child is None:
                    p_child = child
                else:
                    p_child = None
                    break

        if p_child:
            self._process_element(p_child, blocks)
        else:
            # 检查是否包含图片包装器
            classes = element.get("class") or []
            class_str = " ".join(c for c in classes) if isinstance(classes, list) else str(classes)
            if self.config.image_wrapper_class in class_str:
                pics = element.find_all("picture")
                for pic in pics:
                    url = self._extract_image_url(pic)
                    if url:
                        blocks.append(TextBlock(type="image", content=url))
                return

            sub_blocks = self._extract_blocks(element)
            blocks.extend(sub_blocks)

    def _process_code_container(self, element: Tag, blocks: list[TextBlock]) -> None:
        """处理代码块容器"""
        code_elem = element.find("code")
        pre_elem = element.find("pre")
        
        if pre_elem:
            code_content = pre_elem.get_text("\n", strip=True)
        elif code_elem:
            code_content = code_elem.get_text("\n", strip=True)
        else:
            code_content = element.get_text("\n", strip=True)
            if code_content.startswith("plaintext"):
                code_content = code_content[len("plaintext"):].lstrip("\n")
        
        language = "text"
        classes = element.get("class") or []
        if "plaintext" in classes:
            language = "language-plaintext"
        
        if code_content:
            blocks.append(TextBlock(type="code", content=code_content, language=language))
    
    def _process_list(self, element: Tag, list_type: str, blocks: list[TextBlock], level: int = 0) -> None:
        """处理列表元素（ul 或 ol）"""
        list_items = element.find_all("li", recursive=False)
        for i, li in enumerate(list_items):
            self._process_list_item(li, blocks, list_type, i + 1, level)
    
    def _process_list_item(self, li: Tag, blocks: list[TextBlock], list_type: str = "ul", index: int = 1, level: int = 0) -> None:
        """处理单个列表项 - 智能判断简单或复杂类型"""
        has_nested_list = li.find(["ul", "ol"], recursive=False)
        has_br = li.find("br") is not None or any(
            isinstance(x, str) and "line-break" in x
            for x in (li.get("class") or [])
        )
        has_strong = li.find("strong") or li.find("b")
        has_math = self._find_math_in_element(li)
        has_em = li.find("em") or li.find("i")
        has_picture = li.find("picture") is not None
        has_table = li.find("table") is not None
        has_pre = li.find("pre") is not None

        if has_br or has_strong or has_math or has_em or has_nested_list or has_picture or has_table or has_pre:
            self._process_complex_list_item(li, blocks, list_type, level)
            return

        text = li.get_text(strip=True)
        if text:
            blocks.append(TextBlock(type="list_item", content=text, language=list_type, level=level))
    
    def _process_complex_list_item(self, li: Tag, blocks: list[TextBlock], list_type: str, level: int = 0) -> None:
        """处理复杂的列表项 - 包含内联样式、公式或嵌套列表"""
        items: list[InlineContent] = []
        current_text = ""
        current_bold = False
        current_italic = False
        
        def flush():
            nonlocal current_text, current_bold, current_italic
            stripped = current_text.strip()
            if stripped:
                items.append(InlineContent(
                    type="text", 
                    content=stripped, 
                    bold=current_bold,
                    italic=current_italic
                ))
            current_text = ""
            current_bold = False
            current_italic = False
        
        for child in li.children:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    current_text += text
            elif isinstance(child, Tag):
                if self._is_math_element(child):
                    flush()
                    latex = self._extract_latex_content(child)
                    is_display = self._is_display_math(child)
                    items.append(InlineContent(type="latex", content=latex, is_display=is_display))
                elif child.name in ("strong", "b"):
                    flush()
                    bold_items = self._extract_strong_recursive(child)
                    for bi in bold_items:
                        items.append(bi)
                elif child.name in ("em", "i"):
                    flush()
                    italic_items = self._extract_italic_recursive(child)
                    for ii in italic_items:
                        items.append(ii)
                elif child.name == "p":
                    # 段落内部可能包含多种内容，递归处理
                    self._process_nested_container(child, items, current_bold, current_italic)
                elif child.name == "div" and self._has_any_class(child, self.config.line_break_classes):
                    current_text, current_bold, current_italic = self._handle_line_break(
                        child.previousSibling, items, current_text, current_bold, current_italic, current_bold, current_italic
                    )
                elif child.name == "br":
                    flush()
                    items.append(InlineContent(type="text", content="\n"))
                elif child.name in ("div", "span"):
                    self._process_nested_container(child, items, current_bold, current_italic)
                elif child.name == "picture":
                    flush()
                    url = self._extract_image_url(child)
                    if url:
                        items.append(InlineContent(type="image", content="", image_url=url))
                elif child.name == "table":
                    flush()
                    table_data = self._parse_table(child)
                    if table_data:
                        items.append(InlineContent(type="table", content="", data=table_data, bold=current_bold, italic=current_italic))
                elif child.name == "pre":
                    if not child.get(self.config.code_expanded_attr):
                        flush()
                        code_content = child.get_text("\n", strip=True)
                        items.append(InlineContent(type="code", content=code_content, bold=current_bold, italic=current_italic))
                elif child.name in ("ul", "ol"):
                    flush()
                    items.append(InlineContent(type="text", content="\n", bold=current_bold, italic=current_italic))
                    self._extract_nested_list_text(child, items, current_bold, current_italic, level + 1)
                else:
                    # 其他元素，尝试提取文本
                    sub_text = child.get_text(strip=False)
                    if sub_text:
                        current_text += sub_text
        
        flush()
        
        # 添加列表项到 blocks
        if items:
            valid_items = [item for item in items if item.content.strip() or item.content == "\n" or item.type in ("latex", "image", "table", "code")]
            if valid_items:
                blocks.append(TextBlock(type="list_item", content="", language=list_type, items=valid_items, level=level))

    def _extract_nested_list_text(self, element: Tag, items: list[InlineContent], bold: bool = False, italic: bool = False, level: int = 1) -> None:
        """提取嵌套列表的文本内容作为 InlineContent"""
        counter = 1
        li_elements = element.find_all("li", recursive=False)
        for idx, child in enumerate(li_elements):
            direct_text = self._get_direct_text(child)
            list_marker = "•" if element.name == "ul" else None
            has_nested_list = child.find(["ul", "ol"], recursive=False) is not None

            if direct_text:
                if element.name == "ul":
                    items.append(InlineContent(type="text", content=direct_text, bold=bold, italic=italic, list_marker=list_marker, level=level))
                else:
                    items.append(InlineContent(type="text", content=f"{counter}. {direct_text}", bold=bold, italic=italic, level=level))

            if element.name == "ol" and (direct_text or has_nested_list):
                counter += 1

            nested_items = []
            self._collect_nested_content_in_li(child, nested_items, bold, italic)
            for ni in nested_items:
                ni.list_marker = list_marker
                ni.level = level
            items.extend(nested_items)

            nested = child.find(["ul", "ol"], recursive=False)
            if nested:
                self._extract_nested_list_text(nested, items, bold, italic, level + 1)

    def _get_direct_text(self, element: Tag) -> str:
        """获取元素的直接文本（排除嵌套的 ul/ol）"""
        texts = []
        for child in element.children:
            if isinstance(child, str):
                text = str(child).strip()
                if text:
                    texts.append(text)
            elif hasattr(child, 'name') and child.name in ('ul', 'ol'):
                continue
            elif hasattr(child, 'children'):
                texts.append(self._get_direct_text(child))
        return ''.join(texts).strip()

    def _collect_nested_content_in_li(self, li: Tag, items: list[InlineContent], bold: bool, italic: bool) -> None:
        """收集列表项中的深层嵌套内容块（图片、表格、代码）"""
        for pic in li.find_all("picture"):
            url = self._extract_image_url(pic)
            if url:
                items.append(InlineContent(type="image", content="", image_url=url))

        for table in li.find_all("table", recursive=False):
            table_data = self._parse_table(table)
            if table_data:
                items.append(InlineContent(type="table", content="", data=table_data, bold=bold, italic=italic))

        for pre in li.find_all("pre", recursive=False):
            if pre.get(self.config.code_expanded_attr):
                continue
            code_content = pre.get_text("\n", strip=True)
            lang = ""
            code_elem = pre.find("code")
            if code_elem:
                lang = code_elem.get("class") or []
                lang = " ".join([c for c in lang if c != "hljs"]) if lang else ""
            items.append(InlineContent(type="code", content=code_content, bold=bold, italic=italic))

    def _process_nested_container(self, element: Tag, items: list[InlineContent], 
                                   parent_bold: bool = False, parent_italic: bool = False) -> None:
        """递归处理嵌套容器 - 支持样式状态传递"""
        current_text = ""
        current_bold = parent_bold
        current_italic = parent_italic
        
        def flush():
            nonlocal current_text, current_bold, current_italic
            stripped = current_text.strip()
            if stripped:
                items.append(InlineContent(
                    type="text", 
                    content=stripped, 
                    bold=current_bold,
                    italic=current_italic
                ))
            current_text = ""
            current_bold = parent_bold
            current_italic = parent_italic
        
        for child in element.children:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    current_text += text
            elif isinstance(child, Tag):
                if self._is_math_element(child):
                    flush()
                    latex = self._extract_latex_content(child)
                    is_display = self._is_display_math(child)
                    items.append(InlineContent(type="latex", content=latex, is_display=is_display))
                elif child.name == "div" and self._has_any_class(child, self.config.line_break_classes):
                    current_text, current_bold, current_italic = self._handle_line_break(
                        child.previousSibling, items, current_text, current_bold, current_italic, 
                        parent_bold, parent_italic, flush
                    )
                elif child.name == "br":
                    flush()
                    items.append(InlineContent(type="text", content="\n"))
                elif child.name in ("strong", "b"):
                    bold_items = self._extract_strong_recursive(child)
                    if current_text.strip():
                        flush()
                    for bi in bold_items:
                        bi.italic = current_italic  # 继承父级斜体
                        items.append(bi)
                elif child.name in ("em", "i"):
                    italic_items = self._extract_italic_recursive(child)
                    if current_text.strip():
                        flush()
                    for ii in italic_items:
                        ii.bold = current_bold  # 继承父级加粗
                        items.append(ii)
                elif child.name in ("div", "span"):
                    self._process_nested_container(child, items, current_bold, current_italic)
                elif child.name == "picture":
                    flush()
                    url = self._extract_image_url(child)
                    if url:
                        items.append(InlineContent(type="image", content="", image_url=url))
                elif child.name == "table":
                    flush()
                    table_data = self._parse_table(child)
                    if table_data:
                        items.append(InlineContent(type="table", content="", data=table_data, bold=current_bold, italic=current_italic))
                elif child.name == "pre":
                    if not child.get(self.config.code_expanded_attr):
                        flush()
                        code_content = child.get_text("\n", strip=True)
                        items.append(InlineContent(type="code", content=code_content, bold=current_bold, italic=current_italic))
                elif child.name in ("ul", "ol"):
                    pass
                elif child.name == "p":
                    self._process_nested_container(child, items, current_bold, current_italic)
                else:
                    sub_text = child.get_text(strip=False)
                    if sub_text:
                        current_text += sub_text

        flush()
    
    def _process_paragraph(self, element: Tag, blocks: list[TextBlock]) -> None:
        """处理段落元素 - 区分简单和复杂段落"""
        math_elements = self._find_math_in_element(element)
        has_strong = element.find("strong") or element.find("b")
        has_picture = element.find("picture")
        
        if not math_elements and not has_strong and not has_picture:
            text = element.get_text(strip=True)
            if text:
                blocks.append(TextBlock(type="paragraph", content=text))
            return
        
        items: list[InlineContent] = []
        current_text = ""
        current_bold = False
        current_italic = False
        
        def flush():
            nonlocal current_text, current_bold, current_italic
            if current_text.strip():
                items.append(InlineContent(
                    type="text", 
                    content=current_text, 
                    bold=current_bold,
                    italic=current_italic
                ))
            current_text = ""
            current_bold = False
            current_italic = False
        
        for child in element.children:
            if isinstance(child, NavigableString):
                current_text += str(child)
            elif isinstance(child, Tag):
                if self._is_math_element(child):
                    flush()
                    latex = self._extract_latex_content(child)
                    is_display = self._is_display_math(child)
                    items.append(InlineContent(type="latex", content=latex, is_display=is_display))
                elif child.name in ("strong", "b"):
                    bold_items = self._extract_strong_recursive(child)
                    if current_text.strip():
                        flush()
                    for bi in bold_items:
                        items.append(bi)
                elif child.name in ("em", "i"):
                    italic_items = self._extract_italic_recursive(child)
                    if current_text.strip():
                        flush()
                    for ii in italic_items:
                        items.append(ii)
                elif child.name == "div" and self._has_any_class(child, self.config.line_break_classes):
                    flush()
                    items.append(InlineContent(type="text", content="\n"))
                elif child.name == "br":
                    flush()
                    items.append(InlineContent(type="text", content="\n"))
                elif child.name == "picture":
                    flush()
                    url = self._extract_image_url(child)
                    if url:
                        items.append(InlineContent(type="image", content="", image_url=url))
                elif child.name in ("div", "span"):
                    has_pic, text = self._extract_images_recursive(child, items, flush)
                    if not has_pic and text:
                        current_text += text
                else:
                    sub_text = child.get_text(strip=False)
                    if sub_text:
                        current_text += sub_text
        
        flush()

        blocks.append(TextBlock(type="paragraph", content="", items=items))
    
    def _extract_images_recursive(self, element: Tag, items: list[InlineContent], flush_func: Callable[..., Any]) -> tuple[bool, str]:
        """递归查找嵌套的 picture 并提取图片，返回 (has_picture, text)"""
        pics = element.find_all("picture")
        if pics:
            for pic in pics:
                flush_func()
                url = self._extract_image_url(pic)
                if url:
                    items.append(InlineContent(type="image", content="", image_url=url))
            return True, ""
        else:
            sub_text = element.get_text(strip=False)
            return False, sub_text
    
    def _extract_strong_recursive(self, element: Tag) -> list[InlineContent]:
        """递归提取 strong/b 内的内容 - 保留嵌套加粗"""
        items = []
        for child in element.children:
            if isinstance(child, NavigableString):
                text = str(child)
                if text:
                    items.append(InlineContent(type="text", content=text, bold=True))
            elif isinstance(child, Tag):
                # 嵌套的加粗
                if child.name in ("strong", "b"):
                    items.extend(self._extract_strong_recursive(child))
                # 嵌套的公式 - 使用钩子判断
                elif self._is_math_element(child):
                    latex = self._extract_latex_content(child)
                    is_display = self._is_display_math(child)
                    items.append(InlineContent(type="latex", content=latex, is_display=is_display))
                # 其他内容
                else:
                    text = child.get_text(strip=False)
                    if text:
                        items.append(InlineContent(type="text", content=text, bold=True))
        return items
    
    def _extract_italic_recursive(self, element: Tag) -> list[InlineContent]:
        """递归提取斜体/强调内容 - 支持嵌套结构"""
        items = []
        for child in element.children:
            if isinstance(child, NavigableString):
                text = str(child)
                if text:
                    items.append(InlineContent(type="text", content=text, italic=True))
            elif isinstance(child, Tag):
                if child.name in ("em", "i"):
                    items.extend(self._extract_italic_recursive(child))
                elif child.name in ("strong", "b"):
                    bold_items = self._extract_strong_recursive(child)
                    for bi in bold_items:
                        bi.italic = True
                        items.append(bi)
                elif self._is_math_element(child):
                    latex = self._extract_latex_content(child)
                    is_display = self._is_display_math(child)
                    items.append(InlineContent(type="latex", content=latex, is_display=is_display))
                else:
                    text = child.get_text(strip=False)
                    if text:
                        items.append(InlineContent(type="text", content=text, italic=True))
        return items
    
    def _extract_inline_text_with_format(self, element: Tag, in_bold: bool = False) -> list[InlineContent]:
        """提取内联元素的文本 - 保留加粗格式"""
        items: list[InlineContent] = []
        current_text = ""
        
        def flush(bold: bool = False):
            nonlocal current_text
            if current_text.strip():
                items.append(InlineContent(type="text", content=current_text.strip(), bold=bold))
            current_text = ""
        
        for child in element.children:
            if isinstance(child, NavigableString):
                current_text += str(child)
            elif isinstance(child, Tag):
                if child.name in ("strong", "b"):
                    bold_text = child.get_text(strip=True)
                    if bold_text:
                        if current_text.strip():
                            items.append(InlineContent(type="text", content=current_text.strip(), bold=in_bold))
                            current_text = ""
                        items.append(InlineContent(type="text", content=bold_text, bold=True))
                else:
                    if child.find("strong") or child.find("b"):
                        bold_items = self._extract_strong_recursive(child)
                        if current_text.strip():
                            items.append(InlineContent(type="text", content=current_text.strip(), bold=in_bold))
                            current_text = ""
                        for bi in bold_items:
                            items.append(bi)
                    elif child.find("em") or child.find("i"):
                        italic_items = self._extract_italic_recursive(child)
                        if current_text.strip():
                            items.append(InlineContent(type="text", content=current_text.strip(), bold=in_bold))
                            current_text = ""
                        for ii in italic_items:
                            items.append(ii)
                    else:
                        sub_text = child.get_text(strip=False)
                        if sub_text:
                            current_text += sub_text
        
        if current_text.strip():
            items.append(InlineContent(type="text", content=current_text.strip(), bold=in_bold))
        
        return items
    
    def _process_inline_element(self, element: Tag, blocks: list[TextBlock]) -> None:
        """处理内联元素（如 strong, em, span 等）"""
        # 先处理嵌套的 picture 元素
        pics = element.find_all("picture")
        for pic in pics:
            url = self._extract_image_url(pic)
            if url:
                blocks.append(TextBlock(type="image", content=url))

        math_in_children = self._find_math_in_element(element)
        if math_in_children:
            self._process_element_with_inline_math(element, blocks)
        else:
            bold = element.name in ("strong", "b")
            items = self._extract_inline_text_with_format(element)
            if items:
                blocks.append(TextBlock(type="paragraph", content="", items=items))
            else:
                text = element.get_text(strip=True)
                if text:
                    blocks.append(TextBlock(type="paragraph", content=text, language="bold" if bold else None))
    
    def _process_element_with_inline_math(self, element: Tag, blocks: list[TextBlock]) -> None:
        """处理包含公式的内联元素"""
        math_elements = self._find_math_in_element(element)
        
        if not math_elements:
            text = element.get_text(strip=True)
            if text and blocks and blocks[-1].type == "paragraph":
                blocks[-1].content += " " + text
            elif text:
                blocks.append(TextBlock(type="paragraph", content=text))
            return
        
        math_ids = set(id(el) for el in math_elements)
        text_parts = []
        
        for child in element.children:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    text_parts.append(text)
            elif isinstance(child, Tag):
                if id(child) in math_ids:
                    text_so_far = " ".join(text_parts).strip()
                    if text_so_far:
                        blocks.append(TextBlock(type="paragraph", content=text_so_far))
                        text_parts.clear()
                    self._process_math_element(child, blocks)
                else:
                    sub_text = child.get_text(strip=True)
                    if sub_text:
                        text_parts.append(sub_text)
        
        if text_parts:
            combined = " ".join(text_parts).strip()
            if combined:
                blocks.append(TextBlock(type="paragraph", content=combined))
    
    def _process_math_element(self, element: Tag, blocks: list[TextBlock]) -> None:
        """解析数学公式元素"""
        # 使用钩子提取 LaTeX 内容
        latex = self._extract_latex_content(element)
        
        if not latex:
            latex = element.get_text(strip=True)
        
        latex = self._strip_latex_delimiters(latex)
        # 使用钩子判断是否为展示公式
        is_display = self._is_display_math(element)
        
        blocks.append(TextBlock(
            type="latex",
            content=latex,
            language="display" if is_display else "inline"
        ))
        
        if len(blocks) >= 2:
            prev_block = blocks[-2]
            if prev_block.type == "paragraph" and not prev_block.items:
                prev_block.items.append(InlineContent(type="latex", content=latex, is_display=is_display))
                blocks.pop()
    
    # -------------------------------------------------------------------------
    # 辅助方法 - 提供通用功能，供钩子方法或子类使用
    # -------------------------------------------------------------------------
    
    def _find_math_in_element(self, element: Tag) -> list[Tag]:
        """在元素中查找所有公式元素"""
        math_elements = []
        for child in element.find_all(recursive=False):
            if self._is_math_element(child):
                math_elements.append(child)
        return math_elements
    
    @staticmethod
    def _parse_table(table: Tag) -> Optional[TableData]:
        """解析表格 - 提取表头和数据行"""
        headers = []
        rows = []
        header_bold = []
        cell_bold = []
        
        # 提取表头
        thead = table.find("thead")
        if thead:
            header_row = thead.find("tr")
            if header_row:
                headers = []
                header_bold = []
                for th in header_row.find_all(["th", "td"]):
                    headers.append(th.get_text(strip=True))
                    header_bold.append(th.find("strong") is not None or th.find("b") is not None)
        
        # 提取数据行
        tbody = table.find("tbody")
        if not tbody:
            tbody = table
        
        for row in tbody.find_all("tr"):
            row_data = []
            row_bold = []
            for td in row.find_all(["td", "th"]):
                row_data.append(td.get_text(strip=True))
                row_bold.append(td.find("strong") is not None or td.find("b") is not None)
            if row_data:
                rows.append(row_data)
                cell_bold.append(row_bold)
        
        # 处理没有 thead 的情况（第一行作为表头）
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
        """去除 LaTeX 公式的边界符"""
        latex = latex.strip()
        if latex.startswith("\\(") and latex.endswith("\\)"):
            return latex[2:-2]
        elif latex.startswith("$") and latex.endswith("$"):
            return latex[1:-1]
        return latex
