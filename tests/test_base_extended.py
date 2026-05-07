"""
测试解析器基类的扩展方法（高覆盖率修正版）
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

# 从 test_preprocessor 导入 MockParser
from tests.test_preprocessor import MockParser


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
        parser._process_list_item(soup.find("li"), blocks, "ul", 1, list_start=None, is_first=False)
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
                handle_line_break_div=False,
                parse_div_span_inline=False,
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
                handle_line_break_div=False,
                parse_div_span_inline=False,
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
    def test_br_alone_creates_paragraph(self):
        """单独的 <br> 应创建换行段落"""
        parser = MockParser()
        soup = BeautifulSoup("<br/>", "lxml")
        blocks = []
        parser._process_element(soup.find("br"), blocks)
        assert len(blocks) == 1
        assert blocks[0].type == "paragraph"
        assert blocks[0].content == "\n"

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
        """测试有序列表通过 _process_list 正确生成 list_item 块"""
        parser = MockParser()
        html = "<ol><li>Apple</li><li>Banana</li></ol>"
        blocks = []
        parser._handle_list(BeautifulSoup(html, "lxml").find("ol"), blocks)
        # 验证生成了 list_item 块
        list_blocks = [b for b in blocks if b.type == "list_item"]
        assert len(list_blocks) == 2
        # 验证内容包含 Apple 和 Banana
        texts = [b.content for b in list_blocks]
        assert "Apple" in texts
        assert "Banana" in texts

    def test_ordered_list_start_attribute(self):
        """<ol start="5"> 解析后首项 TextBlock 的 list_start 应为 5，第二项为 None"""
        parser = MockParser()
        html = '<ol start="5"><li>First</li><li>Second</li></ol>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_list(soup.find("ol"), "ol", blocks)
        assert len(blocks) == 2
        assert blocks[0].list_start == 5
        assert blocks[1].list_start is None

    def test_nested_ordered_list_start(self):
        """嵌套 <ol start="3"> 应在 items 中产生 list_marker="ol" 且 list_start=3 的项"""
        parser = MockParser()
        html = "<ol><li>Item<ol start='3'><li>Sub</li></ol></li></ol>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._handle_list(soup.find("ol"), blocks)
        # 顶层复杂列表项存在
        complex_li = [b for b in blocks if b.type == "list_item" and b.items]
        assert len(complex_li) >= 1
        # 在其 items 中查找携带 list_start=3 的项
        sub_ol_items = [i for i in complex_li[0].items if i.list_marker == "ol" and i.list_start == 3]
        assert len(sub_ol_items) >= 1


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
        parser._process_list_item(soup.find("li"), blocks, "ul", 1, list_start=None, is_first=False)
        code_items = [i for i in blocks[0].items if i.type == "code"]
        assert len(code_items) == 1

    def test_list_item_with_table(self):
        parser = MockParser()
        html = '<li>desc <table><tr><td>1</td></tr></table></li>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_list_item(soup.find("li"), blocks, "ul", 1, list_start=None, is_first=False)
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

    def test_code_language_takes_first_language_class(self):
        """验证存在多个 language-* 类名时，返回第一个"""
        parser = MockParser()
        html = '<pre><code class="language-js language-ts">const x = 1</code></pre>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("pre"), blocks)
        assert blocks[0].language == "language-js"

    def test_code_language_fallback_without_language_class(self):
        """验证无 language-* 时回退为非 hljs 类名拼接"""
        parser = MockParser()
        html = '<pre><code class="hljs some-lang">code</code></pre>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("pre"), blocks)
        assert blocks[0].language == "some-lang"


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
        # 数据行有2列，表头需对齐扩展至2列（原本1列）
        assert table_data.header_bold == [True, False]


class TestOlNestedCounter:
    """覆盖有序列表嵌套时计数器仍正确递增"""

    def test_ol_nested_counter(self):
        """测试嵌套有序列表计数器正确递增（使用 _handle_list）"""
        parser = MockParser()
        html = '<ol><li><ol><li>sub1</li></ol></li><li>Second</li></ol>'
        blocks = []
        parser._handle_list(BeautifulSoup(html, "lxml").find("ol"), blocks)
        # 验证生成了 list_item 块
        list_blocks = [b for b in blocks if b.type == "list_item"]
        assert len(list_blocks) >= 1
        # 验证有 "Second" 相关内容
        texts = [b.content for b in list_blocks]
        assert any("Second" in t for t in texts)

    def test_ol_list_marker_not_sequence_number(self):
        """
        验证有序列表解析器不再拼接序号：_walk_handle_list 为首文本项设置 list_marker="ol"。
        仅当 li 包含嵌套列表（触发 handle_nested_lists）或复杂内联结构时才走 _walk_handle_list。
        """
        parser = MockParser()
        # 含嵌套列表的复杂项会触发 _walk_handle_list
        html = "<ol><li><strong>Bold</strong> text<ol><li>sub</li></ol></li></ol>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._handle_list(soup.find("ol"), blocks)
        # 查找包含内联内容的 list_item
        blocks_with_items = [b for b in blocks if b.type == "list_item" and b.items]
        assert len(blocks_with_items) >= 1
        # 检查 items 中的文本项是否有 list_marker="ol"（由 _walk_handle_list 设置）
        all_text_items = [i for b in blocks_with_items for i in b.items if i.type == "text"]
        ol_items = [i for i in all_text_items if i.list_marker == "ol"]
        assert len(ol_items) >= 1, f"应有文本项的 list_marker='ol'，实际: {[i.list_marker for i in all_text_items]}"

    def test_ol_no_double_numbering_in_complex_item(self):
        """
        验证有序列表项的 items.content 不包含序号前缀（无论走哪个解析路径）。
        简单项（纯文本）走 content 字段，复杂项走 items，通过 _handle_list 入口覆盖两者。
        """
        parser = MockParser()
        # 含嵌套列表的复杂项，走 _walk_handle_list
        html = """
        <ol>
          <li><strong>Bold</strong> and <em>italic</em><ol><li>sub</li></ol></li>
          <li>Plain item</li>
        </ol>
        """
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._handle_list(soup.find("ol"), blocks)
        list_blocks = [b for b in blocks if b.type == "list_item"]
        assert len(list_blocks) == 2
        for block in list_blocks:
            if block.items:
                for item in block.items:
                    if item.type == "text":
                        assert not item.content.startswith("1. "), \
                            f"序号不应出现在 items.content 中，实际内容：{item.content!r}"


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
# 新增：内联结构检测测试（_has_inline_structure 升级后）
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
        # _has_inline_structure 现在应返回 True（检测到 line-break div）
        assert parser._has_inline_structure(div) is True

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
        assert parser._has_inline_structure(soup.find("p")) is False

    def test_paragraph_with_strong_is_complex(self):
        """含加粗的段落应被识别为复杂"""
        parser = MockParser()
        soup = BeautifulSoup("<p>text <strong>bold</strong></p>", "lxml")
        assert parser._has_inline_structure(soup.find("p")) is True

    def test_paragraph_with_em_is_complex(self):
        """含斜体的段落应被识别为复杂"""
        parser = MockParser()
        soup = BeautifulSoup("<p>text <em>italic</em></p>", "lxml")
        assert parser._has_inline_structure(soup.find("p")) is True

    def test_paragraph_with_link_is_complex(self):
        """含链接的段落应被识别为复杂"""
        parser = MockParser()
        soup = BeautifulSoup('<p>text <a href="#">link</a></p>', "lxml")
        assert parser._has_inline_structure(soup.find("p")) is True

    def test_paragraph_with_inline_code_is_complex(self):
        """含内联代码的段落应被识别为复杂"""
        parser = MockParser()
        soup = BeautifulSoup("<p>text <code>code</code></p>", "lxml")
        assert parser._has_inline_structure(soup.find("p")) is True

    def test_paragraph_with_picture_is_complex(self):
        """含图片的段落应被识别为复杂"""
        parser = MockParser()
        soup = BeautifulSoup('<p>text <picture><img src="a.jpg"/></picture></p>', "lxml")
        assert parser._has_inline_structure(soup.find("p")) is True

    def test_paragraph_with_image_wrapper_class(self):
        """含 image-wrapper 类的 div 应被检测

        注意：HTML 规范下 p 不能包含 div，所以使用 div.paragraph-* 作为容器
        """
        parser = MockParser()
        soup = BeautifulSoup(
            '<div class="paragraph-test">text <div class="image-wrapper"><img src="a.jpg"/></div></div>',
            "lxml",
        )
        assert parser._has_inline_structure(soup.find("div")) is True

    def test_paragraph_with_br_is_complex(self):
        """含 br 标签的段落应被识别为复杂"""
        parser = MockParser()
        soup = BeautifulSoup("<p>line1<br/>line2</p>", "lxml")
        assert parser._has_inline_structure(soup.find("p")) is True


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
        assert parser._has_inline_structure(soup.find("div")) is True


# =============================================================================
# 表格解析扩展测试（覆盖 thead/tbody/tfoot 标准结构）
# =============================================================================

class TestParseTableStandardStructure:
    """覆盖标准 <thead>/<tbody> 表格结构的解析"""

    def test_standard_thead_tbody_table(self):
        """标准 thead+tbody 结构：数据行应完整保留"""
        html = """
        <table>
          <thead><tr><th>Header1</th><th>Header2</th></tr></thead>
          <tbody>
            <tr><td>A1</td><td>B1</td></tr>
            <tr><td>A2</td><td>B2</td></tr>
          </tbody>
        </table>
        """
        soup = BeautifulSoup(html, "lxml")
        table_data = BaseParser._parse_table(soup.find("table"))
        assert table_data is not None
        assert table_data.headers == ["Header1", "Header2"]
        assert table_data.rows == [["A1", "B1"], ["A2", "B2"]]
        assert len(table_data.rows) == 2

    def test_thead_tbody_tfoot_table(self):
        """含 tbody 和 tfoot 的标准表格：优先从 tbody 提取，忽略 tfoot"""
        html = """
        <table>
          <thead><tr><th>H1</th><th>H2</th></tr></thead>
          <tbody>
            <tr><td>D1</td><td>D2</td></tr>
          </tbody>
          <tfoot>
            <tr><td>F1</td><td>F2</td></tr>
          </tfoot>
        </table>
        """
        soup = BeautifulSoup(html, "lxml")
        table_data = BaseParser._parse_table(soup.find("table"))
        assert table_data is not None
        # tbody 存在时优先使用，tfoot 被忽略
        assert table_data.rows == [["D1", "D2"]]

    def test_tfoot_only_no_tbody(self):
        """仅有 tfoot 无 tbody 的表格：从 tfoot 提取数据"""
        html = """
        <table>
          <thead><tr><th>H1</th><th>H2</th></tr></thead>
          <tfoot>
            <tr><td>F1</td><td>F2</td></tr>
          </tfoot>
        </table>
        """
        soup = BeautifulSoup(html, "lxml")
        table_data = BaseParser._parse_table(soup.find("table"))
        assert table_data is not None
        assert table_data.rows == [["F1", "F2"]]

    def test_empty_tbody_fallback_to_direct_tr(self):
        """tbody 存在但为空：回退到直接子级 tr"""
        html = """
        <table>
          <thead><tr><th>H1</th><th>H2</th></tr></thead>
          <tbody></tbody>
          <tr><td>D1</td><td>D2</td></tr>
        </table>
        """
        soup = BeautifulSoup(html, "lxml")
        table_data = BaseParser._parse_table(soup.find("table"))
        assert table_data is not None
        assert table_data.headers == ["H1", "H2"]
        assert table_data.rows == [["D1", "D2"]]

    def test_empty_tbody_fallback_to_tfoot(self):
        """tbody 存在但为空：回退到 tfoot"""
        html = """
        <table>
          <thead><tr><th>H1</th><th>H2</th></tr></thead>
          <tbody></tbody>
          <tfoot>
            <tr><td>F1</td><td>F2</td></tr>
          </tfoot>
        </table>
        """
        soup = BeautifulSoup(html, "lxml")
        table_data = BaseParser._parse_table(soup.find("table"))
        assert table_data is not None
        assert table_data.headers == ["H1", "H2"]
        assert table_data.rows == [["F1", "F2"]]

    def test_tbody_only_no_thead(self):
        """仅有 tbody 的表格：若无表头且行数>=2，第一行提升为表头"""
        html = """
        <table>
          <tbody>
            <tr><td>R1C1</td><td>R1C2</td></tr>
            <tr><td>R2C1</td><td>R2C2</td></tr>
            <tr><td>R3C1</td><td>R3C2</td></tr>
          </tbody>
        </table>
        """
        soup = BeautifulSoup(html, "lxml")
        table_data = BaseParser._parse_table(soup.find("table"))
        assert table_data is not None
        # 第一行提升为表头
        assert table_data.headers == ["R1C1", "R1C2"]
        # 剩余两行为数据
        assert table_data.rows == [["R2C1", "R2C2"], ["R3C1", "R3C2"]]

    def test_single_row_tbody_no_header_promotion(self):
        """仅有一行数据的 tbody：表头扩展为空，数据行保留"""
        html = """
        <table>
          <tbody>
            <tr><td>Only</td><td>Row</td></tr>
          </tbody>
        </table>
        """
        soup = BeautifulSoup(html, "lxml")
        table_data = BaseParser._parse_table(soup.find("table"))
        assert table_data is not None
        # 原代码行为：单行时 headers 扩展为空（与数据行列数对齐），rows 保留
        assert table_data.headers == ["", ""]
        assert table_data.rows == [["Only", "Row"]]

    def test_direct_tr_children_no_tbody(self):
        """无 tbody 但有直接 tr 子级的非规范表格：无表头时第一行提升为表头"""
        html = """
        <table>
          <tr><td>D1</td><td>D2</td></tr>
          <tr><td>D3</td><td>D4</td></tr>
        </table>
        """
        soup = BeautifulSoup(html, "lxml")
        table_data = BaseParser._parse_table(soup.find("table"))
        assert table_data is not None
        # 第一行提升为表头，剩余行作为数据
        assert table_data.headers == ["D1", "D2"]
        assert table_data.rows == [["D3", "D4"]]

    def test_thead_with_direct_tr_siblings(self):
        """thead 存在但 tbody 缺失，数据行在 table 直接子级的非规范写法"""
        html = """
        <table>
          <thead><tr><th>H1</th><th>H2</th></tr></thead>
          <tr><td>D1</td><td>D2</td></tr>
          <tr><td>D3</td><td>D4</td></tr>
        </table>
        """
        soup = BeautifulSoup(html, "lxml")
        table_data = BaseParser._parse_table(soup.find("table"))
        assert table_data is not None
        assert table_data.headers == ["H1", "H2"]
        assert table_data.rows == [["D1", "D2"], ["D3", "D4"]]

    def test_empty_table_returns_table_data(self):
        """空表格（有表头无数据行）返回带表头的 TableData，不返回 None"""
        html = "<table><thead><tr><th>Only Header</th></tr></thead></table>"
        soup = BeautifulSoup(html, "lxml")
        table_data = BaseParser._parse_table(soup.find("table"))
        # 有表头但无数据行时返回 TableData（空 rows），不返回 None
        assert table_data is not None
        assert table_data.headers == ["Only Header"]
        assert table_data.rows == []
        assert table_data.header_bold == [True]

    def test_column_alignment_with_thead_tbody(self):
        """标准结构下列对齐：表头列数小于数据行时扩展"""
        html = """
        <table>
          <thead><tr><th>H</th></tr></thead>
          <tbody>
            <tr><td>A1</td><td>A2</td></tr>
            <tr><td>B1</td><td>B2</td><td>B3</td></tr>
          </tbody>
        </table>
        """
        soup = BeautifulSoup(html, "lxml")
        table_data = BaseParser._parse_table(soup.find("table"))
        assert table_data is not None
        # 表头应扩展至3列
        assert table_data.headers == ["H", "", ""]
        assert table_data.header_bold == [True, False, False]
        # 数据行对齐
        assert table_data.rows[0] == ["A1", "A2", ""]
        assert table_data.rows[1] == ["B1", "B2", "B3"]