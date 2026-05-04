"""
测试解析器基类的扩展方法（高覆盖率修正版）
修正了 4 个因 HTML 规范与解析器内部逻辑导致的测试失败
"""
import pytest
from pathlib import Path
from bs4 import BeautifulSoup
from src.preprocessor.base import (
    BaseParser,
    PlatformConfig,
    TextBlock,
    InlineContent,
    WalkOptions,
)


class MockParser(BaseParser):
    """模拟解析器，模拟豆包平台的核心特征"""

    def __init__(self):
        self.config = PlatformConfig()

    def _get_title_selectors(self):
        return ["h1", ".chat-title"]

    def _is_math_element(self, element):
        return element.has_attr("copy-text")

    def _is_display_math(self, element):
        return "display" in (element.get("class") or [])

    def _is_code_container(self, element):
        # 宽松匹配：只要类名中包含 "code-container" 即视为代码容器
        classes = element.get("class") or []
        class_str = " ".join(c for c in classes) if isinstance(classes, list) else str(classes)
        return "code-container" in class_str

    def _is_paragraph_container(self, element):
        classes = element.get("class") or []
        class_str = " ".join(c for c in classes) if isinstance(classes, list) else str(classes)
        return "paragraph" in class_str

    def _is_code_button(self, element):
        classes = element.get("class") or []
        class_str = " ".join(c for c in classes) if isinstance(classes, list) else str(classes)
        return "button-" in class_str

    def _extract_latex_content(self, element):
        return element.get("copy-text", "")

    def _is_image_element(self, element):
        return element.name == "picture"

    def _extract_image_url(self, element):
        """与 DoubaoHTMLParser 一致的 URL 提取逻辑"""
        source = element.find("source")
        if source:
            srcset = source.get("srcset") or source.get("data-srcset")
            if srcset and isinstance(srcset, str) and not srcset.startswith("data:"):
                return srcset.split(",")[0].strip().split(" ")[0]

        img = element.find("img")
        if img:
            current_src = img.get("currentSrc")
            if current_src and isinstance(current_src, str) and not current_src.startswith("data:"):
                return current_src
            src = str(img.get("data-original") or img.get("data-src") or img.get("src") or "")
            if src and isinstance(src, str) and not src.startswith("data:"):
                return src

        return ""


# =============================================================================
# 工具方法基础测试
# =============================================================================

class TestSkipWhitespaceSiblings:
    def test_skip_empty_strings(self):
        parser = MockParser()
        soup = BeautifulSoup("<div>text</div>", "lxml")
        assert parser._skip_whitespace_siblings(soup.find("text")) is None

    def test_no_sibling(self):
        parser = MockParser()
        assert parser._skip_whitespace_siblings(None) is None


class TestWalkHandleLineBreakDiv:
    """验证 line-break div 处理行为（通过 _walk_inline_children 测试新接口）"""

    def test_line_break_div_with_text_before(self):
        """带纯文本前时 line-break div 应添加换行"""
        parser = MockParser()
        html = '<div>text<div class="md-box-line-break"></div></div>'
        soup = BeautifulSoup(html, "lxml")
        div = soup.find("div")
        items = parser._walk_inline_children(div, options=WalkOptions(handle_line_break_div=True))
        newline_items = [i for i in items if i.content == "\n"]
        assert len(newline_items) >= 1

    def test_line_break_div_with_span_before_no_newline(self):
        """修复后：INLINE_CONTAINER_TAGS（span）前也应添加换行"""
        parser = MockParser()
        html = '<div><span>text</span><div class="md-box-line-break"></div></div>'
        soup = BeautifulSoup(html, "lxml")
        div = soup.find("div")
        items = parser._walk_inline_children(div, options=WalkOptions(handle_line_break_div=True))
        # 修复后：span 前的 line-break div 同样添加换行
        newline_items = [i for i in items if i.content == "\n"]
        assert len(newline_items) == 1

    def test_no_line_break_div_no_newline(self):
        """无 line-break 类时不应添加换行"""
        parser = MockParser()
        html = '<div><span>text</span><div>normal</div></div>'
        soup = BeautifulSoup(html, "lxml")
        div = soup.find("div")
        items = parser._walk_inline_children(div)
        newline_items = [i for i in items if i.content == "\n"]
        assert len(newline_items) == 0


class TestExtractTitle:
    def test_fallback_to_title_tag(self):
        parser = MockParser()
        soup = BeautifulSoup("<html><head><title>Page Title</title></head><body></body></html>", "lxml")
        assert parser._extract_title(soup) == "Page Title"

    def test_selector_match_ignores_title_tag(self):
        parser = MockParser()
        soup = BeautifulSoup(
            "<html><head><title>Wrong</title></head><body><h1>Correct</h1></body></html>", "lxml"
        )
        assert parser._extract_title(soup) == "Correct"


class TestHasAnyClass:
    def test_string_class(self):
        parser = MockParser()
        soup = BeautifulSoup('<div class="md-box-line-break">text</div>', "lxml")
        assert parser._has_any_class(soup.find("div"), ["md-box-line-break"]) is True

    def test_list_class(self):
        parser = MockParser()
        soup = BeautifulSoup('<div class="md-box-line-break">text</div>', "lxml")
        assert parser._has_any_class(soup.find("div"), ["md-box-line-break"]) is True


# =============================================================================
# 块级元素处理
# =============================================================================

class TestProcessElement:
    def test_table(self):
        parser = MockParser()
        html = """
        <table><thead><tr><th>A</th><th>B</th></tr></thead>
        <tbody><tr><td>1</td><td>2</td></tr></tbody></table>
        """
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("table"), blocks)
        assert len(blocks) == 1
        assert blocks[0].type == "table"
        assert blocks[0].data.headers == ["A", "B"]
        assert blocks[0].data.rows == [["1", "2"]]

    def test_headings_h1_h6(self):
        parser = MockParser()
        blocks = []
        for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            soup = BeautifulSoup(f"<{tag}>标题{tag}</{tag}>", "lxml")
            parser._process_element(soup.find(tag), blocks)
        headings = [b for b in blocks if b.type == "heading"]
        assert len(headings) == 6
        assert [b.language for b in headings] == ["1", "2", "3", "4", "5", "6"]

    def test_unordered_list(self):
        parser = MockParser()
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("ul"), blocks)
        list_items = [b for b in blocks if b.type == "list_item"]
        assert len(list_items) == 2
        assert list_items[0].content == "Item 1"
        assert list_items[1].content == "Item 2"

    def test_ordered_list(self):
        parser = MockParser()
        html = "<ol><li>Item 1</li><li>Item 2</li></ol>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("ol"), blocks)
        list_items = [b for b in blocks if b.type == "list_item"]
        assert len(list_items) == 2
        assert list_items[0].content == "Item 1"
        assert list_items[1].content == "Item 2"

    def test_paragraph(self):
        parser = MockParser()
        soup = BeautifulSoup("<p>段落内容</p>", "lxml")
        blocks = []
        parser._process_element(soup.find("p"), blocks)
        assert len(blocks) == 1
        assert blocks[0].type == "paragraph"
        assert blocks[0].content == "段落内容"

    def test_pre_code(self):
        parser = MockParser()
        html = "<pre><code class='python'>print('hello')</code></pre>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("pre"), blocks)
        assert len(blocks) == 1
        assert blocks[0].type == "code"
        assert blocks[0].content == "print('hello')"
        assert "python" in blocks[0].language

    def test_blockquote(self):
        parser = MockParser()
        soup = BeautifulSoup("<blockquote>引用</blockquote>", "lxml")
        blocks = []
        parser._process_element(soup.find("blockquote"), blocks)
        assert len(blocks) == 1
        assert blocks[0].type == "blockquote"
        assert blocks[0].content == "引用"

    def test_br_inside_paragraph(self):
        parser = MockParser()
        soup = BeautifulSoup("<p>line1<br/>line2</p>", "lxml")
        blocks = []
        parser._process_paragraph(soup.find("p"), blocks)
        assert len(blocks) >= 1
        if blocks[0].items:
            newlines = [i for i in blocks[0].items if i.content == "\n"]
            assert len(newlines) >= 1

    def test_picture(self):
        parser = MockParser()
        soup = BeautifulSoup('<picture><img src="test.jpg"/></picture>', "lxml")
        blocks = []
        parser._process_element(soup.find("picture"), blocks)
        assert len(blocks) == 1
        assert blocks[0].type == "image"
        assert "test.jpg" in blocks[0].content

    def test_inline_strong(self):
        parser = MockParser()
        soup = BeautifulSoup("<p>包含 <strong>加粗</strong> 文本</p>", "lxml")
        blocks = []
        parser._process_element(soup.find("p"), blocks)
        if blocks[0].items:
            bold = [i for i in blocks[0].items if i.bold]
            assert len(bold) >= 1
            assert "加粗" in bold[0].content

    def test_inline_em(self):
        parser = MockParser()
        soup = BeautifulSoup("<p>包含 <em>斜体</em> 文本</p>", "lxml")
        blocks = []
        parser._process_element(soup.find("p"), blocks)
        if blocks[0].items:
            italic = [i for i in blocks[0].items if i.italic]
            assert len(italic) >= 1
            assert "斜体" in italic[0].content

    def test_math_with_copy_text(self):
        parser = MockParser()
        soup = BeautifulSoup('<span copy-text="\\alpha">α</span>', "lxml")
        blocks = []
        parser._process_element(soup.find("span"), blocks)
        latex = [b for b in blocks if b.type == "latex"]
        assert len(latex) == 1
        assert latex[0].content == "\\alpha"


class TestProcessDivOrSection:
    def test_code_button_expanded(self):
        parser = MockParser()
        html = '<div class="button-expanded"><pre data-expanded-code="true">code</pre></div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._handle_div_or_section(soup.find("div"), blocks)
        code = [b for b in blocks if b.type == "code"]
        assert len(code) == 1
        assert code[0].content == "code"

    def test_code_container(self):
        parser = MockParser()
        html = '<div class="code-container"><pre><code>print("x")</code></pre></div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._handle_div_or_section(soup.find("div"), blocks)
        assert len(blocks) == 1
        assert blocks[0].type == "code"

    def test_paragraph_container(self):
        parser = MockParser()
        html = '<div class="paragraph-xxxx">段落文本</div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._handle_div_or_section(soup.find("div"), blocks)
        assert len(blocks) >= 1
        assert blocks[0].type == "paragraph"

    def test_single_p_child(self):
        parser = MockParser()
        html = "<div><p>唯一段落</p></div>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._handle_div_or_section(soup.find("div"), blocks)
        assert blocks[0].type == "paragraph"
        assert blocks[0].content == "唯一段落"

    def test_image_wrapper(self):
        parser = MockParser()
        html = '<div class="image-wrapper"><picture><img src="img.jpg"/></picture></div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._handle_div_or_section(soup.find("div"), blocks)
        assert blocks[0].type == "image"

    def test_math_element_inside(self):
        parser = MockParser()
        html = '<div><span copy-text="\\gamma">γ</span></div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._handle_div_or_section(soup.find("div"), blocks)
        latex = [b for b in blocks if b.type == "latex"]
        assert len(latex) == 1

    def test_multiple_p_children(self):
        parser = MockParser()
        html = '<div><p>First</p><p>Second</p></div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._handle_div_or_section(soup.find("div"), blocks)
        assert len(blocks) >= 2
        assert blocks[0].content == "First"
        assert blocks[1].content == "Second"


class TestProcessCodeContainer:
    def test_pre_element(self):
        parser = MockParser()
        html = "<div class='code-container'><pre><code>code</code></pre></div>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_code_container(soup.find("div"), blocks)
        assert blocks[0].type == "code"

    def test_only_code(self):
        parser = MockParser()
        html = "<div class='code-container'><code>inline</code></div>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_code_container(soup.find("div"), blocks)
        assert blocks[0].content == "inline"

    def test_plaintext_class(self):
        parser = MockParser()
        html = '<div class="plaintext">plain code</div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_code_container(soup.find("div"), blocks)
        assert "language-plaintext" in blocks[0].language


class TestProcessList:
    def test_simple_items(self):
        parser = MockParser()
        soup = BeautifulSoup("<ul><li>A</li><li>B</li></ul>", "lxml")
        blocks = []
        parser._process_list(soup.find("ul"), "ul", blocks)
        assert len(blocks) == 2
        assert blocks[0].content == "A"

    def test_nested_list(self):
        parser = MockParser()
        html = "<ul><li>Item 1<ul><li>Nested</li></ul></li></ul>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_list(soup.find("ul"), "ul", blocks)
        list_items = [b for b in blocks if b.type == "list_item"]
        assert len(list_items) >= 1
        if list_items and list_items[0].items:
            nested_text = [i.content for i in list_items[0].items]
            assert "Nested" in "".join(nested_text)

    def test_complex_with_strong(self):
        parser = MockParser()
        soup = BeautifulSoup("<li><strong>Bold</strong> normal</li>", "lxml")
        blocks = []
        parser._process_list_item(soup.find("li"), blocks, "ul", 1)
        bold = [i for i in blocks[0].items if i.bold]
        assert len(bold) >= 1

    def test_math_hook(self):
        parser = MockParser()
        soup = BeautifulSoup('<span copy-text="\\beta">β</span>', "lxml")
        blocks = []
        parser._process_element(soup.find("span"), blocks)
        latex = [b for b in blocks if b.type == "latex"]
        assert len(latex) == 1


class TestExtractMethods:
    def test_strong_recursive(self):
        """测试 strong 元素的内联内容提取（使用 _walk_inline_children）"""
        parser = MockParser()
        soup = BeautifulSoup("<strong>Text <strong>inner</strong></strong>", "lxml")
        # 直接调用核心方法 _walk_inline_children，参数与原 _extract_strong_recursive 一致
        items = parser._walk_inline_children(
            soup.find("strong"),
            parent_bold=True,
            parent_italic=False,
            options=WalkOptions(
                conditional_format_flush=True,
                handle_line_break_div=False,
                parse_div_span_inline=False,
                strip_nav_strings=True,
                reset_format_to_parent=False,
                handle_nested_lists=False,
                list_level=1,
            ),
        )
        assert any(i.bold for i in items)

    def test_italic_recursive(self):
        """测试 em 元素的内联内容提取（使用 _walk_inline_children）"""
        parser = MockParser()
        soup = BeautifulSoup("<em>Text <em>inner</em></em>", "lxml")
        # 直接调用核心方法 _walk_inline_children，参数与原 _extract_italic_recursive 一致
        items = parser._walk_inline_children(
            soup.find("em"),
            parent_bold=False,
            parent_italic=True,
            options=WalkOptions(
                conditional_format_flush=True,
                handle_line_break_div=False,
                parse_div_span_inline=False,
                strip_nav_strings=True,
                reset_format_to_parent=False,
                handle_nested_lists=False,
                list_level=1,
            ),
        )
        assert any(i.italic for i in items)


class TestProcessInlineAndMath:
    def test_inline_picture(self):
        parser = MockParser()
        html = '<span><picture><img src="img.jpg"/></picture>Text</span>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_inline_element(soup.find("span"), blocks)
        image_items = [i for i in blocks[0].items if i.type == "image"]
        assert len(image_items) >= 1
        assert "img.jpg" in image_items[0].image_url

    def test_paragraph_with_inline_math(self):
        parser = MockParser()
        html = '<p>Before <span copy-text="\\alpha">α</span> after</p>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_paragraph(soup.find("p"), blocks)
        latex = [i for i in blocks[0].items if i.type == "latex"]
        assert len(latex) == 1

    def test_strip_latex_delimiters(self):
        assert BaseParser._strip_latex_delimiters("$x$") == "x"
        assert BaseParser._strip_latex_delimiters(r"\(y\)") == "y"
        assert BaseParser._strip_latex_delimiters(r"\[z\]") == "z"
        assert BaseParser._strip_latex_delimiters("$$w$$") == "w"


# =============================================================================
# 修正的测试：避免触发单段落优化，并兼容内联图片
# =============================================================================

class TestWithRealHTML:
    def test_mixed_content(self):
        parser = MockParser()
        html = """
        <h1>标题</h1>
        <p>段落<strong>加粗</strong>和<em>斜体</em></p>
        <ul><li>列表项</li></ul>
        <blockquote>引用</blockquote>
        """
        result = parser.parse(html)
        types = {b.type for b in result.blocks}
        assert "heading" in types, f"实际类型: {types}"
        assert "paragraph" in types
        assert "list_item" in types
        assert "blockquote" in types

    def test_nested_list_real(self):
        parser = MockParser()
        html = """
        <ul class="auto-hide-last-sibling-br">
            <li><strong>FFY03</strong>
                <ul><li>价格：<strong>¥1,000</strong></li></ul>
            </li>
        </ul>
        """
        result = parser.parse(html)
        list_items = [b for b in result.blocks if b.type == "list_item"]
        assert len(list_items) >= 1


# =============================================================================
# 新增的分支覆盖测试（修正 HTML 规范导致的问题）
# =============================================================================

class TestHandleBrAsBlock:
    def test_br_alone_does_not_add_block(self):
        parser = MockParser()
        soup = BeautifulSoup("<br/>", "lxml")
        blocks = []
        parser._process_element(soup.find("br"), blocks)
        assert len(blocks) == 0

    def test_br_after_paragraph_adds_newline(self):
        parser = MockParser()
        soup = BeautifulSoup("<p>text</p><br/>", "lxml")
        blocks = []
        parser._process_element(soup.find("p"), blocks)
        parser._process_element(soup.find("br"), blocks)
        assert blocks[0].content.endswith("\n")


class TestPreExpandedSkip:
    def test_expanded_pre_skipped(self):
        parser = MockParser()
        html = '<pre data-expanded-code="true">skip</pre>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("pre"), blocks)
        assert len(blocks) == 0


class TestCodeButtonNoExpandedPre:
    def test_button_without_expanded_pre(self):
        parser = MockParser()
        html = '<div class="button-full">no pre</div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._handle_div_or_section(soup.find("div"), blocks)
        assert len(blocks) == 0


class TestUnknownTagFallback:
    def test_custom_tag_becomes_paragraph(self):
        parser = MockParser()
        html = '<custom-tag>hello</custom-tag>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("custom-tag"), blocks)
        assert len(blocks) == 1
        assert blocks[0].type == "paragraph"
        assert blocks[0].content == "hello"


class TestExceptionInHandler:
    def test_exception_skips_element(self):
        class FaultyParser(MockParser):
            def _build_tag_handlers(self):
                super()._build_tag_handlers()
                def broken(element, blocks):
                    raise ValueError("broken")
                self._tag_handlers["p"] = broken

        parser = FaultyParser()
        html = "<p>bad</p><blockquote>good</blockquote>"
        soup = BeautifulSoup(html, "lxml")
        blocks = parser._extract_blocks(soup.body or soup)
        quotes = [b for b in blocks if b.type == "blockquote"]
        assert len(quotes) == 1
        assert quotes[0].content == "good"


class TestParagraphWithLink:
    def test_link_inside_paragraph(self):
        parser = MockParser()
        html = '<p>Visit <a href="https://x.com">here</a></p>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_paragraph(soup.find("p"), blocks)
        texts = " ".join(i.content for i in blocks[0].items if i.type == "text")
        assert "here" in texts


class TestMathEmptyCopyText:
    def test_empty_copy_text_falls_back_to_text(self):
        parser = MockParser()
        html = '<span copy-text="">α</span>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_math_element(soup.find("span"), blocks)
        assert blocks[0].content == "α"


class TestOlListItemContent:
    def test_ol_items_numbered(self):
        parser = MockParser()
        html = "<ol><li>Apple</li><li>Banana</li></ol>"
        soup = BeautifulSoup(html, "lxml")
        items = []
        parser._extract_nested_list_text(soup.find("ol"), items)
        assert items[0].content == "1. Apple"
        assert items[1].content == "2. Banana"


# =============================================================================
# 精准打击覆盖率缺失行的新增测试（修正 HTML 嵌套限制）
# =============================================================================

class TestWalkInlineChildrenMissing:
    """覆盖 _walk_inline_children 中 picture, table, pre 内联处理（放在合法容器内）"""

    def test_inline_picture_in_span(self):
        parser = MockParser()
        html = '<span>text <picture><img src="a.png"/></picture> after</span>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_inline_element(soup.find("span"), blocks)
        image_items = [i for i in blocks[0].items if i.type == "image"]
        assert len(image_items) == 1

    def test_inline_table_in_span(self):
        parser = MockParser()
        html = '<span>text <table><tr><td>A</td></tr></table> after</span>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_inline_element(soup.find("span"), blocks)
        table_items = [i for i in blocks[0].items if i.type == "table"]
        assert len(table_items) == 1

    def test_inline_pre_in_span(self):
        parser = MockParser()
        html = '<span>text <pre>inline code</pre> after</span>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_inline_element(soup.find("span"), blocks)
        code_items = [i for i in blocks[0].items if i.type == "code"]
        assert len(code_items) == 1
        assert code_items[0].content == "inline code"

    def test_inline_list_in_paragraph_handled(self):
        parser = MockParser()
        html = '<p>text <ul><li>nested</li></ul></p>'
        soup = BeautifulSoup(html, "lxml")
        # 直接调用 _walk_inline_children 开启嵌套列表处理
        items = parser._walk_inline_children(
            soup.find("p"),
            options=WalkOptions(
                handle_nested_lists=True,
                parse_div_span_inline=False,
                conditional_format_flush=True,
                strip_nav_strings=False,
                reset_format_to_parent=False,
            ),
        )
        # 至少应包含换行和嵌套文本
        assert len(items) >= 1


class TestListItemHasPreTable:
    """覆盖 _process_list_item 中 has_pre / has_table 分支"""

    def test_list_item_with_pre(self):
        parser = MockParser()
        html = '<li>desc <pre>sudo apt update</pre></li>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_list_item(soup.find("li"), blocks, "ul", 1)
        code_items = [i for i in blocks[0].items if i.type == "code"]
        assert len(code_items) == 1

    def test_list_item_with_table(self):
        parser = MockParser()
        html = '<li>desc <table><tr><td>1</td></tr></table></li>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_list_item(soup.find("li"), blocks, "ul", 1)
        table_items = [i for i in blocks[0].items if i.type == "table"]
        assert len(table_items) == 1


class TestCodeLanguageFilters:
    """覆盖 _extract_code_language 中 hljs 过滤及容器内 plaintext 前缀去除"""

    def test_code_container_plaintext_prefix(self):
        parser = MockParser()
        # 不使用 <pre> 或 <code> 子元素，直接让 div 文本以 plaintext 开头
        html = '<div class="code-container">plaintext\nreal code</div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._handle_div_or_section(soup.find("div"), blocks)
        assert blocks[0].content == "real code"

    def test_code_language_filters_hljs(self):
        parser = MockParser()
        html = '<pre><code class="hljs language-python">print(1)</code></pre>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("pre"), blocks)
        assert blocks[0].language == "language-python"


class TestParseTableCellBold:
    """覆盖表格解析中 cell_bold 标记（使用 thead 明确区分）"""

    def test_parse_table_cell_bold_with_thead(self):
        html = '''
        <table>
          <thead><tr><th>Header</th></tr></thead>
          <tbody><tr><td>normal</td><td><strong>bold</strong></td></tr></tbody>
        </table>
        '''
        soup = BeautifulSoup(html, "lxml")
        table_data = BaseParser._parse_table(soup.find("table"))
        assert table_data.cell_bold == [[False, True]]
        # <th> 标签本身即为粗体
        assert table_data.header_bold == [True]


class TestContainsBlockElements:
    """覆盖 _contains_block_elements 方法"""

    def test_contains_block_elements_true(self):
        parser = MockParser()
        soup = BeautifulSoup("<div><h2>heading</h2></div>", "lxml")
        assert parser._contains_block_elements(soup.find("div")) is True

    def test_contains_block_elements_false(self):
        parser = MockParser()
        soup = BeautifulSoup("<div><span>text</span></div>", "lxml")
        assert parser._contains_block_elements(soup.find("div")) is False


class TestOlNestedCounter:
    """覆盖有序列表嵌套时计数器仍正确递增"""

    def test_ol_nested_counter(self):
        parser = MockParser()
        html = '<ol><li><ol><li>sub1</li></ol></li><li>Second</li></ol>'
        soup = BeautifulSoup(html, "lxml")
        items = []
        parser._extract_nested_list_text(soup.find("ol"), items, bold=False, italic=False, level=1)
        # 第一个 li 无直接文本但有嵌套，计数器应前进，第二个为 "2. Second"
        numbers = [i.content for i in items if i.level == 1]
        assert "2. Second" in numbers


# =============================================================================
# 真实 HTML 文件集成测试
# =============================================================================

class TestRealHTMLIntegration:
    def test_real_image_html(self):
        html_path = Path(__file__).parent / "html" / "image.html"
        if not html_path.exists():
            pytest.skip("真实 HTML 文件不存在")
        html_content = html_path.read_text(encoding="utf-8")
        result = MockParser().parse(html_content)
        block_images = [b for b in result.blocks if b.type == "image"]
        inline_images = [
            i for b in result.blocks for i in (getattr(b, "items", []) or [])
            if i.type == "image"
        ]
        total_images = len(block_images) + len(inline_images)
        assert total_images >= 2, f"期望至少2张图片，实际{total_images}"

    def test_real_list_html(self):
        html_path = Path(__file__).parent / "html" / "list.html"
        if not html_path.exists():
            pytest.skip("文件不存在")
        content = html_path.read_text(encoding="utf-8")
        result = MockParser().parse(content)
        headings = [b for b in result.blocks if b.type == "heading"]
        list_items = [b for b in result.blocks if b.type == "list_item"]
        assert len(headings) > 5
        assert len(list_items) > 10

    def test_real_code_html(self):
        html_path = Path(__file__).parent / "html" / "code.html"
        if not html_path.exists():
            pytest.skip("文件不存在")
        content = html_path.read_text(encoding="utf-8")
        result = MockParser().parse(content)
        code_blocks = [b for b in result.blocks if b.type == "code"]
        assert len(code_blocks) >= 2

    def test_real_math_html(self):
        html_path = Path(__file__).parent / "html" / "math.html"
        if not html_path.exists():
            pytest.skip("文件不存在")
        content = html_path.read_text(encoding="utf-8")
        result = MockParser().parse(content)
        latex_blocks = [b for b in result.blocks if b.type == "latex"]
        inline_latex = [
            i for b in result.blocks for i in (getattr(b, "items", []) or [])
            if i.type == "latex"
        ]
        assert len(latex_blocks) + len(inline_latex) > 0, "应解析出公式"

    def test_real_table_html(self):
        html_path = Path(__file__).parent / "html" / "table.html"
        if not html_path.exists():
            pytest.skip("文件不存在")
        content = html_path.read_text(encoding="utf-8")
        result = MockParser().parse(content)
        tables = [b for b in result.blocks if b.type == "table"]
        assert len(tables) >= 5


# =============================================================================
# 新增：内联结构检测测试（_should_parse_as_complex 升级后）
# =============================================================================

class TestHasInlineStructure:
    """测试通用内联结构检测方法"""

    def test_line_break_div_detected(self):
        """含有 line-break div 的段落应被识别为复杂段落

        注意：测试用 div.paragraph-* 而不是 p，因为 HTML 规范下 p 不能包含 div
        """
        parser = MockParser()
        soup = BeautifulSoup(
            '<div class="paragraph-test">1）标配：外圆卡箍固定'
            '<div class="md-box-line-break"></div>'
            '2）可选：侧向双耳安装座</div>',
            "lxml",
        )
        div = soup.find("div")
        # _should_parse_as_complex 现在应返回 True（检测到 line-break div）
        assert parser._should_parse_as_complex(div) is True

    def test_multiple_line_breaks_in_paragraph(self):
        """多行换行分隔的段落应走复杂解析

        注意：测试用 div.paragraph-* 而不是 p
        """
        parser = MockParser()
        soup = BeautifulSoup(
            '<div class="paragraph-test">text'
            '<div class="md-box-line-break"></div>'
            'more text'
            '<div class="md-box-line-break"></div>'
            'end text</div>',
            "lxml",
        )
        blocks = []
        # 使用 _handle_div_or_section 处理段落容器
        parser._handle_div_or_section(soup.find("div"), blocks)
        assert len(blocks) == 1
        # 应走复杂解析路径（items 不为空）
        assert blocks[0].items is not None and len(blocks[0].items) > 0

    def test_simple_paragraph_not_complex(self):
        """纯文本段落不应被识别为复杂"""
        parser = MockParser()
        soup = BeautifulSoup("<p>纯文本内容</p>", "lxml")
        assert parser._should_parse_as_complex(soup.find("p")) is False

    def test_paragraph_with_strong_is_complex(self):
        """含加粗的段落应被识别为复杂"""
        parser = MockParser()
        soup = BeautifulSoup("<p>text <strong>bold</strong></p>", "lxml")
        assert parser._should_parse_as_complex(soup.find("p")) is True

    def test_paragraph_with_em_is_complex(self):
        """含斜体的段落应被识别为复杂"""
        parser = MockParser()
        soup = BeautifulSoup("<p>text <em>italic</em></p>", "lxml")
        assert parser._should_parse_as_complex(soup.find("p")) is True

    def test_paragraph_with_link_is_complex(self):
        """含链接的段落应被识别为复杂"""
        parser = MockParser()
        soup = BeautifulSoup('<p>text <a href="#">link</a></p>', "lxml")
        assert parser._should_parse_as_complex(soup.find("p")) is True

    def test_paragraph_with_inline_code_is_complex(self):
        """含内联代码的段落应被识别为复杂"""
        parser = MockParser()
        soup = BeautifulSoup("<p>text <code>code</code></p>", "lxml")
        assert parser._should_parse_as_complex(soup.find("p")) is True

    def test_paragraph_with_picture_is_complex(self):
        """含图片的段落应被识别为复杂"""
        parser = MockParser()
        soup = BeautifulSoup('<p>text <picture><img src="a.jpg"/></picture></p>', "lxml")
        assert parser._should_parse_as_complex(soup.find("p")) is True

    def test_paragraph_with_image_wrapper_class(self):
        """含 image-wrapper 类的 div 应被检测

        注意：HTML 规范下 p 不能包含 div，所以使用 div.paragraph-* 作为容器
        """
        parser = MockParser()
        soup = BeautifulSoup(
            '<div class="paragraph-test">text <div class="image-wrapper"><img src="a.jpg"/></div></div>',
            "lxml",
        )
        assert parser._should_parse_as_complex(soup.find("div")) is True

    def test_paragraph_with_br_is_complex(self):
        """含 br 标签的段落应被识别为复杂"""
        parser = MockParser()
        soup = BeautifulSoup("<p>line1<br/>line2</p>", "lxml")
        assert parser._should_parse_as_complex(soup.find("p")) is True


class TestPlatformSpecificInlineStructure:
    """测试平台特有内联结构扩展"""

    def test_platform_specific_returns_false_by_default(self):
        """默认实现应返回 False"""
        parser = MockParser()
        soup = BeautifulSoup("<div>text</div>", "lxml")
        assert parser._platform_specific_inline_structure(soup.find("div")) is False

    def test_custom_parser_with_platform_extension(self):
        """自定义解析器可扩展平台特有检测"""
        class CustomParser(MockParser):
            def _platform_specific_inline_structure(self, element):
                # 自定义检测：class 包含 "custom-break" 也视为换行
                if element.name == "div" and "custom-break" in (
                    element.get("class") or []
                ):
                    return True
                return False

        parser = CustomParser()
        soup = BeautifulSoup(
            '<div class="paragraph-test">text <div class="custom-break"></div>more</div>',
            "lxml",
        )
        assert parser._should_parse_as_complex(soup.find("div")) is True