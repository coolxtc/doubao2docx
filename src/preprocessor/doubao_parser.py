"""
豆包HTML解析器

这个模块用于解析豆包（一个 AI 助手）生成的 HTML 文档。
它可以将 HTML 格式的内容转换为结构化的 Python 对象，方便后续处理。

主要功能：
- 提取文档标题
- 解析数学公式（LaTeX 格式）
- 解析表格数据
- 解析标题（h1-h6）
- 解析有序/无序列表
- 解析代码块
- 解析引用内容
- 解析普通段落

使用示例：
    parser = DoubaoHTMLParser()
    result = parser.parse(html_string)
    print(result.title)  # 文档标题
    for block in result.blocks:
        print(block.type, block.content)  # 内容块类型和文本

核心概念：
- BeautifulSoup：Python 最流行的 HTML/XML 解析库
- Tag：HTML 标签对象
- NavigableString：文本节点（不是标签的文本）
- dataclass：自动生成 __init__、__repr__ 等方法的数据类
"""

from dataclasses import dataclass, field
from typing import Optional, Any, Union

# BeautifulSoup: 用于解析 HTML 文档
# Tag: 代表一个 HTML 标签（如 <div>、<p> 等）
# NavigableString: 代表标签内的文本内容
from bs4 import BeautifulSoup, Tag, NavigableString


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


def _parse_math_display_flag(element: Union[Tag, dict]) -> bool:
    """解析数学公式的 display 标志
    
    判断公式是"行内公式"还是"展示公式"（独占一行的公式）。
    展示公式通常更大、更醒目。
    
    Args:
        element: BeautifulSoup Tag 或包含 class 的字典
        
    Returns:
        True if display mode (展示公式), False if inline (行内公式)
    """
    class_str = " ".join(element.get("class", []))
    return "math-block" in class_str or "katex--display" in class_str


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
    """内联内容项（文本或公式）- 用于段落内的细粒度内容
    
    一个段落可能同时包含普通文字、加粗文字、公式等。
    这个类用来表示段落内的这些"小片段"。
    
    属性：
        type: 内容类型，"text" 或 "latex"
        content: 具体内容
        is_display: 是否是展示公式（仅对 latex 类型有效）
        bold: 是否加粗
    """
    type: str  # "text" 或 "latex"
    content: str
    is_display: bool = False
    bold: bool = False


@dataclass 
class TextBlock:
    """文本块 - 代表文档中的一个内容块
    
    这是解析结果的基本单位，每个 TextBlock 代表一种类型的内容。
    
    属性：
        type: 块类型，可选：
            - "paragraph": 普通段落
            - "heading": 标题
            - "code": 代码块
            - "latex": 数学公式
            - "table": 表格
            - "blockquote": 引用
            - "list_item": 列表项
        content: 块的文本内容（对于纯文本块）
        language: 附加信息，如代码块的语言、标题级别等
        data: 附加数据，如表格数据
        inline: 是否是内联块
        items: 内联内容列表（用于包含多种格式的段落）
    """
    type: str
    content: str
    language: Optional[str] = None
    data: Any = None
    inline: bool = False
    items: list[InlineContent] = field(default_factory=list)


@dataclass
class ParsedPage:
    """解析后的页面 - 包含整个文档的解析结果
    
    属性：
        title: 文档标题
        blocks: 内容块列表
    """
    title: str = ""
    blocks: list[TextBlock] = field(default_factory=list)


class DoubaoHTMLParser:
    """豆包HTML解析器 - 将 HTML 转换为结构化数据
    
    这是核心解析类，使用 BeautifulSoup 解析 HTML 文档。
    
    支持解析的内容类型：
    - 数学公式：通过 data-custom-copy-text 属性识别
    - 表格：<table> 标签
    - 标题：<h1> 到 <h6> 标签
    - 列表：<ul>（无序）和 <ol>（有序）标签
    - 代码块：<pre> 和 <code> 标签
    - 引用：<blockquote> 标签
    - 段落：<p> 标签
    
    工作原理：
    1. 使用 BeautifulSoup 解析 HTML
    2. 遍历文档的各个元素
    3. 根据元素类型调用相应的处理方法
    4. 将解析结果转换为 TextBlock 对象
    5. 返回包含标题和内容块的 ParsedPage 对象
    """
    
    def parse(self, html: str) -> ParsedPage:
        """解析豆包HTML页面 - 主方法
        
        Args:
            html: HTML 字符串
            
        Returns:
            ParsedPage: 包含 title 和 blocks 的解析结果
        """
        # 使用 lxml 解析器（更快更容错）
        soup = BeautifulSoup(html, "lxml")
        
        # 提取标题
        title = self._extract_title(soup)
        
        # 获取内容容器（优先用 body，没有就用整个文档）
        container = soup.body if soup.body else soup
        
        # 提取所有内容块
        blocks = self._extract_blocks(container)
        
        return ParsedPage(title=title, blocks=blocks)

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """提取标题
        
        尝试多种方式：
        1. <title> 标签
        2. <h1> 标签
        """
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)
        
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        
        return ""

    def _extract_blocks(self, container: Tag) -> list[TextBlock]:
        """从容器中提取所有内容块
        
        遍历容器的直接子元素，处理每个元素。
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

    def _is_line_break_div(self, element: Tag) -> bool:
        """检查是否是换行div"""
        classes = element.get("class", [])
        return "md-box-line-break" in classes

    def _process_element(self, element: Tag, blocks: list[TextBlock]) -> None:
        """处理单个元素 - 根据标签类型分发处理
        
        这是主要的分发逻辑，根据 HTML 标签名调用不同的处理方法。
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
            self._process_list(element, "ul", blocks)
            return
        
        # 有序列表
        if tag == "ol":
            self._process_list(element, "ol", blocks)
            return
        
        # 段落
        if tag == "p":
            self._process_paragraph(element, blocks)
            return
        
        # 预格式化代码块
        if tag == "pre":
            # 爬虫注入的 expanded-code pre 会被 code-block-container 处理，这里跳过
            if element.get("data-expanded-code"):
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
            classes = element.get("class", [])
            
            # 跳过按钮元素（但先处理其中的 hidden pre）
            if any("button-" in cls for cls in classes):
                # 检查是否有爬虫注入的 hidden pre
                expanded_pre = element.find("pre", attrs={"data-expanded-code": "true"})
                if expanded_pre:
                    code = expanded_pre.get_text("\n", strip=True)
                    blocks.append(TextBlock(type="code", content=code, language="language-plaintext"))
                return
            
            # 检查是否是代码块容器
            is_code_container = any("custom-code-block-container" in cls for cls in classes)
            
            if is_code_container:
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
                if "plaintext" in classes:
                    language = "language-plaintext"
                if code_content:
                    blocks.append(TextBlock(type="code", content=code_content, language=language))
                return
            
            # 检查是否是段落容器
            is_paragraph_container = any(
                cls.startswith("paragraph-") for cls in classes
            )
            
            if is_paragraph_container:
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
            return
        
        # 带有数学公式属性的元素（豆包用 data-custom-copy-text 存储公式）
        if element.has_attr("data-custom-copy-text"):
            blocks.append(self._parse_math_element(element))
            return
        
        # 内联标签（strong, em, span, a, b, i, u, small, del, mark）
        inline_tags = {"strong", "em", "span", "a", "b", "i", "u", "small", "del", "mark"}
        if tag in inline_tags:
            # 检查子元素中是否有公式
            math_in_children = element.find_all(attrs={"data-custom-copy-text": True})
            if math_in_children:
                self._process_element_with_inline_math(element, blocks)
            else:
                bold = tag in ("strong", "b")
                items = self._extract_inline_text_with_format(element)
                if items:
                    blocks.append(TextBlock(type="paragraph", content="", items=items))
                else:
                    text = element.get_text(strip=True)
                    if text:
                        blocks.append(TextBlock(type="paragraph", content=text, language="bold" if bold else None))
            return
        
        # 其他情况：提取文本并追加到上一个段落
        text = element.get_text(strip=True)
        if text:
            if blocks and blocks[-1].type == "paragraph":
                blocks[-1].content += " " + text
            else:
                blocks.append(TextBlock(type="paragraph", content=text))

    def _process_list(self, element: Tag, list_type: str, blocks: list[TextBlock]) -> None:
        """处理列表元素 - 遍历所有列表项"""
        list_items = element.find_all("li", recursive=False)
        for i, li in enumerate(list_items):
            self._process_list_item(li, blocks, list_type, i + 1)

    def _process_paragraph(self, element: Tag, blocks: list[TextBlock]) -> None:
        """处理段落元素 - 保留内联元素和公式
        
        段落可能包含：
        - 普通文本
        - 加粗文本（strong, b）
        - 数学公式（data-custom-copy-text）
        - 换行（br, div.line-break）
        
        我们需要将这些"小片段"都解析出来，保持原始格式。
        """
        # 查找段落中的数学公式元素
        math_elements = element.find_all(attrs={"data-custom-copy-text": True})
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
                # 数学公式
                if child.has_attr("data-custom-copy-text"):
                    flush()
                    latex = child.get("data-custom-copy-text", "")
                    is_display = _parse_math_display_flag(child)
                    items.append(InlineContent(type="latex", content=latex, is_display=is_display))
                # 加粗
                elif child.name in ("strong", "b"):
                    bold_items = self._extract_strong_recursive(child)
                    if current_text.strip():
                        flush()
                    for bi in bold_items:
                        items.append(bi)
                # 换行div
                elif self._is_line_break_div(child):
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
                # 嵌套的公式
                elif child.has_attr("data-custom-copy-text"):
                    latex = child.get("data-custom-copy-text", "")
                    is_display = _parse_math_display_flag(child)
                    items.append(InlineContent(type="latex", content=latex, is_display=is_display))
                # 其他内容
                else:
                    text = child.get_text(strip=False)
                    if text:
                        items.append(InlineContent(type="text", content=text, bold=True))
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
                    sub_text = child.get_text(strip=True)
                    if sub_text:
                        current_text += sub_text
        
        if current_text.strip():
            items.append(InlineContent(type="text", content=current_text.strip(), bold=in_bold))
        
        return items

    def _parse_table(self, table: Tag) -> Optional[TableData]:
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

    def _process_list_item(self, li: Tag, blocks: list[TextBlock], list_type: str = "ul", index: int = 1) -> None:
        """处理列表项 - 保留内联元素和公式"""
        has_br = li.find("br") or li.find(class_=lambda x: x and any("line-break" in c for c in x))
        
        if has_br:
            # 有换行的列表项
            items: list[InlineContent] = []
            current_text = ""
            current_bold = False
            
            def flush_text():
                nonlocal current_text, current_bold
                if current_text.strip():
                    items.append(InlineContent(type="text", content=current_text.strip(), bold=current_bold))
                current_text = ""
                current_bold = False
            
            for child in li.children:
                if isinstance(child, NavigableString):
                    current_text += str(child)
                elif isinstance(child, Tag):
                    if child.name == "br":
                        flush_text()
                        items.append(InlineContent(type="text", content="\n"))
                    elif child.name == "div" and any("line-break" in c for c in child.get("class", [])):
                        flush_text()
                        items.append(InlineContent(type="text", content="\n"))
                    elif child.name in ("strong", "b"):
                        bold_items = self._extract_strong_recursive(child)
                        if current_text.strip():
                            flush_text()
                        for bi in bold_items:
                            items.append(bi)
                    else:
                        sub_text = child.get_text(strip=False)
                        if sub_text:
                            current_text += sub_text
            
            flush_text()
            
            if items:
                blocks.append(TextBlock(type="list_item", content="", language=list_type, items=items))
            return
        
        has_strong = li.find("strong") or li.find("b")
        has_math = li.find(attrs={"data-custom-copy-text": True})
        
        # 简单的列表项
        if not has_strong and not has_math:
            text = li.get_text(strip=True)
            if text:
                blocks.append(TextBlock(type="list_item", content=text, language=list_type))
            return
        
        # 复杂的列表项（有格式或公式）
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
                current_text += str(child)
            elif isinstance(child, Tag):
                if child.has_attr("data-custom-copy-text"):
                    flush()
                    latex = child.get("data-custom-copy-text", "")
                    is_display = _parse_math_display_flag(child)
                    items.append(InlineContent(type="latex", content=latex, is_display=is_display))
                elif child.name == "div" and any("line-break" in c for c in child.get("class", [])):
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
                else:
                    sub_text = child.get_text(strip=False)
                    if sub_text:
                        current_text += sub_text
        
        flush()
        
        if items:
            blocks.append(TextBlock(type="list_item", content="", language=list_type, items=items))

    def _process_element_with_inline_math(self, element: Tag, blocks: list[TextBlock]) -> None:
        """处理包含公式的内联元素（如 strong, em 等）"""
        math_elements = element.find_all(attrs={"data-custom-copy-text": True})
        
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
                    blocks.append(self._parse_math_element(child))
                else:
                    sub_text = child.get_text(strip=True)
                    if sub_text:
                        text_parts.append(sub_text)
        
        if text_parts:
            combined = " ".join(text_parts).strip()
            if combined:
                blocks.append(TextBlock(type="paragraph", content=combined))

    def _parse_math_element(self, element: Tag) -> TextBlock:
        """解析数学公式元素"""
        # 优先从 data-custom-copy-text 获取 LaTeX
        latex = element.get("data-custom-copy-text", "")
        
        if not latex:
            latex = element.get_text(strip=True)
        
        # 去除边界符
        latex = _strip_latex_delimiters(latex)
        
        # 判断是行内还是展示公式
        is_display = _parse_math_display_flag(element)
        
        return TextBlock(
            type="latex",
            content=latex,
            language="display" if is_display else "inline"
        )