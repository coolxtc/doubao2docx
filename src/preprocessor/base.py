"""
解析器基类模块

定义解析器的抽象基类和平台配置，支持多平台扩展。

核心概念：
- PlatformConfig: 平台配置数据类，包含各平台的差异配置
- BaseParser: 解析器抽象基类，定义统一接口和抽象钩子方法

扩展新平台：
1. 继承 BaseParser
2. 实现所有 @abstractmethod 钩子方法
3. 在 __init__.py 中导出
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any, Union

from bs4 import BeautifulSoup, Tag, NavigableString

from ..exceptions import ParseError


# =============================================================================
# PlatformConfig - 平台配置
# =============================================================================

@dataclass
class PlatformConfig:
    """平台配置数据类 - 集中管理各平台的差异配置
    
    这个类将平台特定的配置集中管理，使得添加新平台时只需配置即可，
    无需修改解析器核心代码。
    
    属性说明：
        name: 平台名称标识
        latex_attr: LaTeX 公式存储的属性名
        math_display_classes: 展示公式（独占一行的大公式）的 CSS 类名列表
        line_break_classes: 换行 div 的 CSS 类名列表
        code_container_class: 代码块容器的 CSS 类名
        code_button_pattern: 代码展开按钮的前缀（用于检测）
        code_expanded_attr: 标记已展开代码的属性名
        message_item_selector: 消息容器的 CSS 选择器
        user_message_class: 用户消息的 CSS 类名（用于区分消息类型）
        heading_selectors: 标题元素的 CSS 选择器（逗号分隔）
        paragraph_prefix: 段落容器的 CSS 类名前缀
        parser: BeautifulSoup 使用的解析器（lxml, html.parser 等）
    """
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


# =============================================================================
# 数据类型 - 与平台无关，可直接复用
# =============================================================================

@dataclass
class TableData:
    """表格数据 - 存储表格的行列信息
    
    属性：
        headers: 表头行（每列的名称）
        rows: 数据行（每行是一个列表）
        header_bold: 表头是否加粗
        cell_bold: 单元格是否加粗
    """
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
    """解析后的页面 - 包含整个文档的解析结果
    
    属性：
        title: 文档标题
        blocks: 内容块列表
    """
    title: str = ""
    blocks: list[TextBlock] = field(default_factory=list)


# =============================================================================
# BaseParser - 解析器抽象基类
# =============================================================================

class BaseParser(ABC):
    """解析器抽象基类 - 定义统一接口
    
    所有平台解析器都应继承此类，实现所有抽象钩子方法。
    通用逻辑已在基类中实现，平台特定逻辑通过钩子方法注入。
    
    使用方式：
        class MyParser(BaseParser):
            def __init__(self):
                self.config = PlatformConfig(name="myplatform")
            
            # 实现所有抽象钩子方法
            def _is_math_element(self, element) -> bool:
                return element.has_attr(self.config.latex_attr)
            
            def _is_display_math(self, element) -> bool:
                ...
            
            # ... 其他钩子方法
            
            # 可选：覆盖 _parse_impl 完全自定义解析流程
            def _parse_impl(self, html: str) -> ParsedPage:
                # 完全自定义实现
                pass
    """
    
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
        """判断元素是否为公式元素
        
        子类根据平台特定的方式判断元素是否包含数学公式。
        
        Args:
            element: HTML 元素
            
        Returns:
            True 如果元素是公式元素，否则 False
        """
        raise NotImplementedError("子类必须实现 _is_math_element()")
    
    @abstractmethod
    def _is_display_math(self, element: Tag) -> bool:
        """判断元素是否为展示公式
        
        展示公式是独占一行的公式，通常有特殊的样式标记。
        
        Args:
            element: HTML 元素
            
        Returns:
            True 如果是展示公式，否则 False（行内公式）
        """
        raise NotImplementedError("子类必须实现 _is_display_math()")
    
    @abstractmethod
    def _is_code_container(self, element: Tag) -> bool:
        """判断元素是否为代码容器
        
        代码容器是包含代码块的父元素，用于识别完整的代码块结构。
        
        Args:
            element: HTML 元素
            
        Returns:
            True 如果元素是代码容器，否则 False
        """
        raise NotImplementedError("子类必须实现 _is_code_container()")
    
    @abstractmethod
    def _is_paragraph_container(self, element: Tag) -> bool:
        """判断元素是否为段落容器
        
        段落容器是包含段落内容的父元素。
        
        Args:
            element: HTML 元素
            
        Returns:
            True 如果元素是段落容器，否则 False
        """
        raise NotImplementedError("子类必须实现 _is_paragraph_container()")
    
    @abstractmethod
    def _is_code_button(self, element: Tag) -> bool:
        """判断元素是否为代码展开按钮
        
        代码展开按钮是用于展开/折叠代码块的交互元素。
        
        Args:
            element: HTML 元素
            
        Returns:
            True 如果元素是代码按钮，否则 False
        """
        raise NotImplementedError("子类必须实现 _is_code_button()")
    
    @abstractmethod
    def _extract_latex_content(self, element: Tag) -> str:
        """从公式元素中提取 LaTeX 内容
        
        从元素中提取数学公式的 LaTeX 源码。
        
        Args:
            element: 公式元素
            
        Returns:
            LaTeX 公式字符串
        """
        raise NotImplementedError("子类必须实现 _extract_latex_content()")
    
    # -------------------------------------------------------------------------
    # 通用方法 - 不依赖平台特定逻辑
    # -------------------------------------------------------------------------
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """提取标题
        
        使用钩子方法返回的选择器查找标题。
        备选方案：<title> 标签。
        
        Args:
            soup: BeautifulSoup 对象
            
        Returns:
            提取的标题文本
        """
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
        """从容器中提取所有内容块
        
        遍历容器的直接子元素，处理每个元素。
        
        Args:
            container: 内容容器
            
        Returns:
            内容块列表
        """
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
        """处理单个元素 - 根据标签类型分发处理
        
        这是主要的分发逻辑，根据 HTML 标签名调用不同的处理方法。
        
        Args:
            element: HTML 元素
            blocks: 累积的内容块列表
        """
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
                lang = code_elem.get("class", [])
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
        
        # 其他情况：提取文本并追加到上一个段落
        text = element.get_text(strip=True)
        if text:
            if blocks and blocks[-1].type == "paragraph":
                blocks[-1].content += " " + text
            else:
                blocks.append(TextBlock(type="paragraph", content=text))
    
    def _process_div_or_section(self, element: Tag, blocks: list[TextBlock]) -> None:
        """处理 div 或 section 元素
        
        Args:
            element: div 或 section 元素
            blocks: 累积的内容块列表
        """
        # 跳过代码按钮元素
        if self._is_code_button(element):
            # 检查是否有 expanded pre
            expanded_pre = element.find("pre", attrs={self.config.code_expanded_attr: "true"})
            if expanded_pre:
                code = expanded_pre.get_text("\n", strip=True)
                blocks.append(TextBlock(type="code", content=code, language="language-plaintext"))
            return
        
        # 使用钩子判断是否为公式元素
        if self._is_math_element(element):
            self._process_math_element(element, blocks)
            return
        
        # 使用钩子判断是否为代码容器
        if self._is_code_container(element):
            self._process_code_container(element, blocks)
            return
        
        if self._is_paragraph_container(element):
            self._process_paragraph(element, blocks)
            return
        
        # 检查是否整个 div 只有一个直接子元素是 p
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
            sub_blocks = self._extract_blocks(element)
            blocks.extend(sub_blocks)

    def _process_code_container(self, element: Tag, blocks: list[TextBlock]) -> None:
        """处理代码块容器
        
        Args:
            element: 代码容器元素
            blocks: 累积的内容块列表
        """
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
        classes = element.get("class", [])
        if "plaintext" in classes:
            language = "language-plaintext"
        
        if code_content:
            blocks.append(TextBlock(type="code", content=code_content, language=language))
    
    def _process_list(self, element: Tag, list_type: str, blocks: list[TextBlock], level: int = 0) -> None:
        list_items = element.find_all("li", recursive=False)
        for i, li in enumerate(list_items):
            self._process_list_item(li, blocks, list_type, i + 1, level)
    
    def _process_list_item(self, li: Tag, blocks: list[TextBlock], list_type: str = "ul", index: int = 1, level: int = 0) -> None:
        has_nested_list = li.find(["ul", "ol"], recursive=False)
        has_br = li.find("br") or li.find(class_=lambda x: x and any("line-break" in c for c in x))
        has_strong = li.find("strong") or li.find("b")
        has_math = self._find_math_in_element(li)
        has_em = li.find("em") or li.find("i")
        
        if has_br or has_strong or has_math or has_em or has_nested_list:
            self._process_complex_list_item(li, blocks, list_type, level)
            return
        
        text = li.get_text(strip=True)
        if text:
            blocks.append(TextBlock(type="list_item", content=text, language=list_type, level=level))
    
    def _process_complex_list_item(self, li: Tag, blocks: list[TextBlock], list_type: str, level: int = 0) -> None:
        items: list[InlineContent] = []
        current_text = ""
        current_bold = False
        
        def flush():
            nonlocal current_text, current_bold
            if current_text.strip():
                items.append(InlineContent(type="text", content=current_text, bold=current_bold))
            current_text = ""
            current_bold = False
        
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
                    text = child.get_text(strip=True)
                    if text:
                        items.append(InlineContent(type="text", content="\n" + text))
                elif child.name in ("ul", "ol"):
                    break
        
        if items:
            valid_items = [item for item in items if item.content and item.content.strip()]
            if valid_items:
                for item in valid_items:
                    item.content = item.content.replace("\n", " ")
                blocks.append(TextBlock(type="list_item", content="", language=list_type, items=valid_items, level=level))
        
        for child in li.children:
            if isinstance(child, Tag) and child.name in ("ul", "ol"):
                self._process_list(child, child.name, blocks, level + 1)
    
    def _process_nested_container(self, element: Tag, items: list[InlineContent]) -> None:
        """递归处理嵌套容器（div/span）- 提取内部加粗和文本
        
        用于处理列表项中的嵌套div/span元素，保留内部strong标签的加粗格式。
        """
        current_text = ""
        current_bold = False
        
        def flush():
            nonlocal current_text, current_bold
            if current_text.strip():
                items.append(InlineContent(type="text", content=current_text, bold=current_bold))
            current_text = ""
            current_bold = False
        
        for child in element.children:
            if isinstance(child, NavigableString):
                current_text += str(child)
            elif isinstance(child, Tag):
                if self._is_math_element(child):
                    flush()
                    latex = self._extract_latex_content(child)
                    is_display = self._is_display_math(child)
                    items.append(InlineContent(type="latex", content=latex, is_display=is_display))
                elif child.name == "div" and any(c in child.get("class", []) for c in self.config.line_break_classes):
                    flush()
                    items.append(InlineContent(type="text", content="\n"))
                elif child.name == "br":
                    flush()
                    items.append(InlineContent(type="text", content="\n"))
                elif child.name in ("strong", "b"):
                    bold_items = self._extract_strong_recursive(child)
                    if current_text.strip():
                        flush()
                    for bi in bold_items:
                        items.append(bi)
                elif child.name in ("div", "span"):
                    self._process_nested_container(child, items)
                elif child.name in ("ul", "ol"):
                    pass  
                else:
                    sub_text = child.get_text(strip=False)
                    if sub_text:
                        current_text += sub_text
        
        flush()
    
    def _process_element_as_sublist(self, element: Tag, blocks: list[TextBlock], parent_list_type: str, level: int) -> None:
        if element.name in ("ul", "ol"):
            self._process_list(element, element.name, blocks, level + 1)
        elif element.name == "p":
            text = element.get_text(strip=True)
            if text:
                blocks.append(TextBlock(type="list_item", content=text, language=parent_list_type, level=level))
        elif element.name in ("div", "section"):
            self._extract_blocks(element)
    
    def _process_paragraph(self, element: Tag, blocks: list[TextBlock]) -> None:
        """处理段落元素 - 保留内联元素和公式
        
        段落可能包含：
        - 普通文本
        - 加粗文本（strong, b）
        - 数学公式
        - 换行（br, div.line-break）
        
        Args:
            element: 段落元素
            blocks: 累积的内容块列表
        """
        # 使用钩子查找段落中的数学公式元素
        math_elements = self._find_math_in_element(element)
        has_strong = element.find("strong") or element.find("b")
        
        # 如果没有特殊元素，直接提取纯文本
        if not math_elements and not has_strong:
            text = element.get_text(strip=True)
            if text:
                blocks.append(TextBlock(type="paragraph", content=text))
            return
        
        # 有特殊元素，需要逐个处理
        items: list[InlineContent] = []
        current_text = ""
        current_bold = False
        
        def flush():
            nonlocal current_text, current_bold
            if current_text.strip():
                items.append(InlineContent(type="text", content=current_text, bold=current_bold))
            current_text = ""
            current_bold = False
        
        for child in element.children:
            if isinstance(child, NavigableString):
                current_text += str(child)
            elif isinstance(child, Tag):
                # 使用钩子判断是否为公式元素
                if self._is_math_element(child):
                    flush()
                    latex = self._extract_latex_content(child)
                    is_display = self._is_display_math(child)
                    items.append(InlineContent(type="latex", content=latex, is_display=is_display))
                # 加粗
                elif child.name in ("strong", "b"):
                    bold_items = self._extract_strong_recursive(child)
                    if current_text.strip():
                        flush()
                    for bi in bold_items:
                        items.append(bi)
                # 换行 div
                elif child.name == "div" and any(c in child.get("class", []) for c in self.config.line_break_classes):
                    flush()
                    items.append(InlineContent(type="text", content="\n"))
                # 换行标签
                elif child.name == "br":
                    flush()
                    items.append(InlineContent(type="text", content="\n"))
                # 其他标签
                else:
                    sub_text = child.get_text(strip=False)
                    if sub_text:
                        current_text += sub_text
        
        flush()
        
        # 如果公式前有换行，标记为展示公式
        if items:
            for i, item in enumerate(items):
                if item.type == "latex":
                    if i > 0 and items[i-1].type == "text" and items[i-1].content == "\n":
                        item.is_display = True
        
        blocks.append(TextBlock(type="paragraph", content="", items=items))
    
    def _extract_strong_recursive(self, element: Tag) -> list[InlineContent]:
        """递归提取 strong/b 内的内容 - 保留嵌套加粗
        
        Args:
            element: strong 或 b 元素
            
        Returns:
            内联内容列表
        """
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
        """提取内联元素的文本 - 保留加粗格式
        
        Args:
            element: 内联元素
            in_bold: 是否继承父级加粗
            
        Returns:
            内联内容列表
        """
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
        """处理内联元素（如 strong, em, span 等）
        
        Args:
            element: 内联元素
            blocks: 累积的内容块列表
        """
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
        """处理包含公式的内联元素
        
        Args:
            element: 包含公式的内联元素
            blocks: 累积的内容块列表
        """
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
        """解析数学公式元素
        
        Args:
            element: 公式元素
            blocks: 累积的内容块列表
        """
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
            if prev_block.type == "paragraph":
                prev_block.items.append(InlineContent(type="latex", content=latex, is_display=True))
                blocks.pop()
    
    # -------------------------------------------------------------------------
    # 辅助方法 - 提供通用功能，供钩子方法或子类使用
    # -------------------------------------------------------------------------
    
    def _find_math_in_element(self, element: Tag) -> list[Tag]:
        """在元素中查找所有公式元素
        
        使用钩子方法判断每个子元素是否为公式元素。
        
        Args:
            element: 要搜索的父元素
            
        Returns:
            公式元素列表
        """
        math_elements = []
        for child in element.find_all(recursive=False):
            if self._is_math_element(child):
                math_elements.append(child)
        return math_elements
    
    @staticmethod
    def _parse_table(table: Tag) -> Optional[TableData]:
        """解析表格 - 提取表头和数据行
        
        Args:
            table: table 元素
            
        Returns:
            TableData 对象，或 None（无法解析时）
        """
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
        """去除 LaTeX 公式的边界符
        
        LaTeX 公式可能有不同的边界符：
        - \\( ... \\) 行内公式
        - $ ... $ 行内公式（简化写法）
        
        这个函数将这些边界符去掉，只保留公式内容。
        
        Args:
            latex: 可能包含边界符的 LaTeX 公式
            
        Returns:
            去掉边界符后的 LaTeX 公式
        """
        latex = latex.strip()
        if latex.startswith("\\(") and latex.endswith("\\)"):
            return latex[2:-2]
        elif latex.startswith("$") and latex.endswith("$"):
            return latex[1:-1]
        return latex
