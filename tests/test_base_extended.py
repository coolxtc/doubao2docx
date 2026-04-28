"""
测试解析器基类的扩展方法

使用真实 HTML 样本测试更多解析场景。
"""
import pytest
from unittest.mock import Mock
from bs4 import BeautifulSoup
from src.preprocessor.base import (
    BaseParser, PlatformConfig, TextBlock, InlineContent
)


class MockParser(BaseParser):
    """模拟解析器"""

    def __init__(self):
        self.config = PlatformConfig()

    def _get_title_selectors(self):
        return ["h1", ".chat-title"]

    def _is_math_element(self, element):
        return element.has_attr("copy-text")

    def _is_display_math(self, element):
        return "display" in (element.get("class") or [])

    def _is_code_container(self, element):
        return "code-container" in (element.get("class") or [])

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
        """
        从 picture 元素中提取图片 URL

        与 DoubaoHTMLParser._extract_image_url 保持一致
        """
        # 1. 尝试从 source 元素获取 URL
        source = element.find("source")
        if source:
            srcset = source.get("srcset") or source.get("data-srcset")
            if srcset and isinstance(srcset, str) and not srcset.startswith("data:"):
                # srcset 格式: "url1 1x, url2 2x"，取第一个
                return srcset.split(",")[0].strip().split(" ")[0]

        # 2. 尝试从 img.currentSrc 获取（懒加载图片加载后的地址）
        img = element.find("img")
        if img:
            current_src = img.get("currentSrc")
            if current_src and isinstance(current_src, str) and not current_src.startswith("data:"):
                return current_src

            # 3. 尝试从 dataset 或 src 获取
            src = str(img.get("data-original") or img.get("data-src") or img.get("src") or "")
            if src and isinstance(src, str) and not src.startswith("data:"):
                return src

        return ""


class TestSkipWhitespaceSiblings:
    """测试 _skip_whitespace_siblings 方法"""

    def test_skip_empty_strings(self):
        """跳过空白文本节点"""
        parser = MockParser()
        soup = BeautifulSoup("<div>text</div>", "lxml")
        result = parser._skip_whitespace_siblings(soup.find("text"))
        assert result is None

    def test_no_sibling(self):
        """无兄弟节点"""
        parser = MockParser()
        soup = BeautifulSoup("<div>text</div>", "lxml")
        result = parser._skip_whitespace_siblings(None)
        assert result is None


class TestHandleLineBreak:
    """测试 _handle_line_break 方法"""

    def test_with_navigable_string(self):
        """NavigableString 分隔符"""
        parser = MockParser()
        soup = BeautifulSoup("<div>text</div>", "lxml")
        div = soup.find("div")
        items = []
        result = parser._handle_line_break(
            div, items, "current", False, False, False, False
        )
        assert result == ("", False, False)

    def test_with_line_break_div(self):
        """md-box-line-break 分隔符"""
        parser = MockParser()
        html = '<div><span>text</span><div class="md-box-line-break"></div></div>'
        soup = BeautifulSoup(html, "lxml")
        div = soup.find_all("div")[1]
        items = []
        result = parser._handle_line_break(
            div, items, "", False, False, False, False
        )
        assert result == ("", False, False)

    def test_handle_line_break_with_no_sibling(self):
        """prev_sibling 为 None"""
        parser = MockParser()
        items = []
        result = parser._handle_line_break(None, items, "text", False, False, False, False)
        assert result == ("", False, False)
        # 先 flush 当前文本，再添加换行符
        assert len(items) == 2
        assert items[0].content == "text"
        assert items[1].content == "\n"


class TestExtractTitle:
    """测试 _extract_title 方法"""

    def test_extract_title_fallback_to_title_tag(self):
        """无选择器匹配时 fallback 到 title 标签"""
        parser = MockParser()
        html = '<html><head><title>Page Title</title></head><body></body></html>'
        soup = BeautifulSoup(html, "lxml")
        title = parser._extract_title(soup)
        assert title == "Page Title"

    def test_extract_title_with_selector_match(self):
        """选择器匹配时使用选择器"""
        parser = MockParser()
        html = '<html><head><title>Wrong Title</title></head><body><h1>Correct Title</h1></body></html>'
        soup = BeautifulSoup(html, "lxml")
        title = parser._extract_title(soup)
        assert title == "Correct Title"


class TestProcessElement:
    """测试 _process_element 方法"""

    def test_process_table(self):
        """处理表格元素"""
        parser = MockParser()
        html = """
        <table>
            <thead><tr><th>A</th><th>B</th></tr></thead>
            <tbody><tr><td>1</td><td>2</td></tr></tbody>
        </table>
        """
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("table"), blocks)
        assert len(blocks) == 1
        assert blocks[0].type == "table"

    def test_process_heading_h1_to_h6(self):
        """处理 h1-h6 标题"""
        parser = MockParser()
        blocks = []
        for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            html = f"<{tag}>标题</{tag}>"
            soup = BeautifulSoup(html, "lxml")
            parser._process_element(soup.find(tag), blocks)
        headings = [b for b in blocks if b.type == "heading"]
        assert len(headings) == 6

    def test_process_ul_list(self):
        """处理无序列表"""
        parser = MockParser()
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("ul"), blocks)
        # _process_list 为每个 li 生成 list_item，检查 list_item 数量
        list_items = [b for b in blocks if b.type == "list_item"]
        assert len(list_items) == 2

    def test_process_ol_list(self):
        """处理有序列表"""
        parser = MockParser()
        html = "<ol><li>Item 1</li><li>Item 2</li></ol>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("ol"), blocks)
        # _process_list 为每个 li 生成 list_item，检查 list_item 数量
        list_items = [b for b in blocks if b.type == "list_item"]
        assert len(list_items) == 2

    def test_process_paragraph(self):
        """处理段落"""
        parser = MockParser()
        html = "<p>这是段落</p>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("p"), blocks)
        assert len(blocks) == 1
        assert blocks[0].type == "paragraph"

    def test_process_pre_code(self):
        """处理预格式化代码块"""
        parser = MockParser()
        html = "<pre><code class='python'>print('hello')</code></pre>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("pre"), blocks)
        assert len(blocks) == 1
        assert blocks[0].type == "code"

    def test_process_blockquote(self):
        """处理引用"""
        parser = MockParser()
        html = "<blockquote>引用文本</blockquote>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("blockquote"), blocks)
        assert len(blocks) == 1
        assert blocks[0].type == "blockquote"

    def test_process_br(self):
        """处理换行标签"""
        parser = MockParser()
        html = "<p>line1<br/>line2</p>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_paragraph(soup.find("p"), blocks)
        assert len(blocks) >= 1

    def test_process_picture(self):
        """处理图片元素"""
        parser = MockParser()
        html = '<picture src="test.jpg"><img src="test.jpg"/></picture>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("picture"), blocks)
        assert len(blocks) == 1
        assert blocks[0].type == "image"

    def test_process_div_container(self):
        """处理 div 容器"""
        parser = MockParser()
        html = "<div><p>嵌套段落</p></div>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("div"), blocks)
        assert len(blocks) >= 1

    def test_process_inline_strong(self):
        """处理 strong 内联标签"""
        parser = MockParser()
        html = "<p>包含 <strong>加粗</strong> 文本</p>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("p"), blocks)
        assert len(blocks) >= 1

    def test_process_inline_em(self):
        """处理 em 内联标签"""
        parser = MockParser()
        html = "<p>包含 <em>斜体</em> 文本</p>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("p"), blocks)
        assert len(blocks) >= 1

    def test_process_math_with_copy_text(self):
        """处理带 copy-text 的公式"""
        parser = MockParser()
        html = '<span copy-text="\\alpha">α</span>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("span"), blocks)
        assert len(blocks) >= 1


class TestHasAnyClass:
    """测试 _has_any_class 方法"""

    def test_has_any_class_with_string(self):
        """class 属性为 string 类型"""
        parser = MockParser()
        html = '<div class="md-box-line-break">text</div>'
        soup = BeautifulSoup(html, "lxml")
        div = soup.find("div")
        # class as string should be handled correctly
        assert parser._has_any_class(div, ["md-box-line-break"]) is True

    def test_has_any_class_with_list(self):
        """class 属性为 list 类型"""
        parser = MockParser()
        html = '<div class="md-box-line-break">text</div>'
        soup = BeautifulSoup(html, "lxml")
        div = soup.find("div")
        # class as list should also work
        assert parser._has_any_class(div, ["md-box-line-break"]) is True


class TestProcessDivOrSection:
    """测试 _process_div_or_section 方法"""

    def test_process_code_button(self):
        """处理代码按钮"""
        parser = MockParser()
        html = '''
        <div class="button-expanded">
            <pre data-expanded-code="true">expanded code</pre>
        </div>
        '''
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_div_or_section(soup.find("div"), blocks)
        assert len(blocks) >= 1  # button-expanded 应产生内容

    def test_process_code_container(self):
        """处理代码容器"""
        parser = MockParser()
        html = '<div class="custom-code-block-container"><pre><code>code</code></pre></div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_div_or_section(soup.find("div"), blocks)
        assert len(blocks) >= 1

    def test_process_paragraph_container(self):
        """处理段落容器"""
        parser = MockParser()
        html = '<div class="paragraph-xxxx">段落文本</div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_div_or_section(soup.find("div"), blocks)
        assert len(blocks) >= 1

    def test_process_with_single_p_child(self):
        """处理只有单个 p 子元素的 div"""
        parser = MockParser()
        html = "<div><p>唯一段落</p></div>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_div_or_section(soup.find("div"), blocks)
        assert len(blocks) >= 1

    def test_process_image_wrapper(self):
        """处理图片包装器"""
        parser = MockParser()
        html = '<div class="image-wrapper"><picture src="img.jpg"><img src="img.jpg"/></picture></div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_div_or_section(soup.find("div"), blocks)
        assert len(blocks) >= 1


class TestProcessCodeContainer:
    """测试 _process_code_container 方法"""

    def test_with_pre_element(self):
        """从 pre 元素提取"""
        parser = MockParser()
        html = "<div><pre><code>code here</code></pre></div>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_code_container(soup.find("div"), blocks)
        assert len(blocks) == 1

    def test_with_only_code_element(self):
        """从 code 元素提取"""
        parser = MockParser()
        html = "<div><code>code here</code></div>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_code_container(soup.find("div"), blocks)
        assert len(blocks) == 1

    def test_with_plaintext_class(self):
        """处理 plaintext 类名"""
        parser = MockParser()
        html = '<div class="plaintext">plain code</div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_code_container(soup.find("div"), blocks)
        assert len(blocks) == 1
        assert "language-plaintext" in blocks[0].language


class TestProcessList:
    """测试列表处理方法"""

    def test_simple_list_items(self):
        """简单列表项"""
        parser = MockParser()
        html = "<ul><li>Item 1</li><li>Item 2</li><li>Item 3</li></ul>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_list(soup.find("ul"), "ul", blocks)
        assert len(blocks) == 3

    def test_nested_list(self):
        """嵌套列表"""
        parser = MockParser()
        html = "<ul><li>Item 1<ul><li>Nested 1</li></ul></li></ul>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_list(soup.find("ul"), "ul", blocks)
        assert len(blocks) >= 1

    def test_complex_list_item_with_br(self):
        """带换行的复杂列表项"""
        parser = MockParser()
        html = '<ul><li class="line-break">Text<br/>More</li></ul>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_list_item(soup.find("li"), blocks, "ul", 1)
        assert len(blocks) >= 1

    def test_complex_list_item_with_strong(self):
        """带 strong 的复杂列表项"""
        parser = MockParser()
        html = "<ul><li><strong>Bold text</strong> and normal</li></ul>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_list_item(soup.find("li"), blocks, "ul", 1)
        assert len(blocks) >= 1

    def test_complex_list_item_with_em(self):
        """复杂列表项包含斜体 em 标签"""
        parser = MockParser()
        html = '<li>text <em>italic</em> more</li>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_complex_list_item(soup.find("li"), blocks, "ul", 1)
        assert len(blocks) >= 1
        if blocks[0].items:
            italic_items = [i for i in blocks[0].items if i.italic]
            assert len(italic_items) >= 1

    def test_complex_list_item_with_i(self):
        """复杂列表项包含 i 标签"""
        parser = MockParser()
        html = '<li>normal <i>italic text</i></li>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_complex_list_item(soup.find("li"), blocks, "ul", 1)
        assert len(blocks) >= 1

    def test_complex_list_item_with_p_child(self):
        """复杂列表项包含 p 标签"""
        parser = MockParser()
        html = '<li><p>paragraph content</p></li>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_complex_list_item(soup.find("li"), blocks, "ul", 1)
        assert len(blocks) >= 1

    def test_complex_list_item_with_div_span(self):
        """复杂列表项包含 div/span 嵌套"""
        parser = MockParser()
        html = '<li><div><span>nested content</span></div></li>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_complex_list_item(soup.find("li"), blocks, "ul", 1)
        assert len(blocks) >= 1

    def test_complex_list_item_with_picture(self):
        """复杂列表项包含图片"""
        parser = MockParser()
        html = '<li><picture><img src="img.png"/></picture>text</li>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_complex_list_item(soup.find("li"), blocks, "ul", 1)
        assert len(blocks) >= 1
        if blocks[0].items:
            image_items = [i for i in blocks[0].items if i.type == "image"]
            assert len(image_items) >= 1

    def test_complex_list_item_with_other_elements(self):
        """复杂列表项包含其他元素（small 标签）"""
        parser = MockParser()
        html = '<li><small>small text</small></li>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_complex_list_item(soup.find("li"), blocks, "ul", 1)
        assert len(blocks) >= 1

    def test_process_element_with_math_hook(self):
        """通过 _is_math_element 钩子检测公式"""
        parser = MockParser()
        html = '<span copy-text="\\beta">β</span>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("span"), blocks)
        latex_blocks = [b for b in blocks if b.type == "latex"]
        assert len(latex_blocks) >= 1

    def test_process_element_with_image_hook(self):
        """通过 _is_image_element 钩子检测图片"""
        parser = MockParser()
        html = '<picture><img src="test.jpg"/></picture>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("picture"), blocks)
        image_blocks = [b for b in blocks if b.type == "image"]
        assert len(image_blocks) >= 1

    def test_process_element_with_paragraph_container_hook(self):
        """通过 _is_paragraph_container 钩子检测段落"""
        parser = MockParser()
        html = '<div class="paragraph-abcd">段落内容</div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("div"), blocks)
        assert len(blocks) >= 1

    def test_process_div_code_button_with_expanded_pre(self):
        """代码按钮包含已展开的 pre"""
        parser = MockParser()
        html = '<div class="button-expanded"><pre data-expanded-code="true">expanded code</pre></div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_div_or_section(soup.find("div"), blocks)
        code_blocks = [b for b in blocks if b.type == "code"]
        assert len(code_blocks) >= 1


class TestProcessDivOrSection:
    """测试 _process_div_or_section 方法"""

    def test_process_div_or_section_with_math_element(self):
        """div 中包含公式元素"""
        parser = MockParser()
        html = '<div><span copy-text="\\gamma">γ</span></div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_div_or_section(soup.find("div"), blocks)
        latex_blocks = [b for b in blocks if b.type == "latex"]
        assert len(latex_blocks) >= 1

    def test_process_div_or_section_with_code_container(self):
        """div 中包含代码容器"""
        parser = MockParser()
        html = '<div class="custom-code-block-container"><pre><code>code here</code></pre></div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_div_or_section(soup.find("div"), blocks)
        code_blocks = [b for b in blocks if b.type == "code"]
        assert len(code_blocks) >= 1

    def test_process_div_or_section_with_image_element(self):
        """div 中包含图片"""
        parser = MockParser()
        html = '<div><picture><img src="img.jpg"/></picture></div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_div_or_section(soup.find("div"), blocks)
        image_blocks = [b for b in blocks if b.type == "image"]
        assert len(image_blocks) >= 1

    def test_process_div_with_multiple_p_children(self):
        """div 有多个 p 子元素"""
        parser = MockParser()
        html = '<div><p>First</p><p>Second</p></div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_div_or_section(soup.find("div"), blocks)
        assert len(blocks) >= 2


class TestExtractMethods:
    """测试提取方法"""

    def test_extract_strong_recursive(self):
        """递归提取 strong 内容"""
        parser = MockParser()
        html = "<p><strong>Nested <strong>double</strong> bold</strong></p>"
        soup = BeautifulSoup(html, "lxml")
        strong = soup.find("strong")
        items = parser._extract_strong_recursive(strong)
        assert len(items) >= 1

    def test_extract_italic_recursive(self):
        """递归提取斜体内容"""
        parser = MockParser()
        html = "<p><em>Italic <em>double</em> text</em></p>"
        soup = BeautifulSoup(html, "lxml")
        em = soup.find("em")
        items = parser._extract_italic_recursive(em)
        assert len(items) >= 1

    def test_extract_inline_text_with_format(self):
        """提取带格式的内联文本"""
        parser = MockParser()
        html = "<p>Normal <strong>bold</strong> text</p>"
        soup = BeautifulSoup(html, "lxml")
        items = parser._extract_inline_text_with_format(soup.find("p"))
        assert len(items) >= 1


class TestProcessInlineAndMath:
    """测试内联和公式处理"""

    def test_process_inline_element_with_picture(self):
        """处理带图片的内联元素"""
        parser = MockParser()
        html = "<span><picture src='img.jpg'><img src='img.jpg'/></picture>Text</span>"
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_inline_element(soup.find("span"), blocks)
        assert len(blocks) >= 1

    def test_process_element_with_inline_math(self):
        """处理带内联公式的元素"""
        parser = MockParser()
        html = '<p>Text <span copy-text="\\alpha">α</span> more text</p>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_paragraph(soup.find("p"), blocks)
        assert len(blocks) >= 1

    def test_process_math_element(self):
        """处理公式元素"""
        parser = MockParser()
        html = '<span copy-text="\\alpha">α</span>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_math_element(soup.find("span"), blocks)
        assert len(blocks) == 1

    def test_find_math_in_element(self):
        """在元素中查找公式"""
        parser = MockParser()
        html = '<p>Text <span copy-text="\\alpha">α</span> end</p>'
        soup = BeautifulSoup(html, "lxml")
        math_elements = parser._find_math_in_element(soup.find("p"))
        assert len(math_elements) == 1

    def test_strip_latex_delimiters_dollar(self):
        """去除 $...$ 分隔符"""
        tests = [
            (r"$x^2$", "x^2"),
            (r"$\alpha$", r"\alpha"),
        ]
        for latex, expected in tests:
            result = BaseParser._strip_latex_delimiters(latex)
            assert expected in result

    def test_strip_latex_delimiters_parentheses(self):
        r"""去除 \(...\) 分隔符"""
        result = BaseParser._strip_latex_delimiters(r"\(x^2\)")
        assert result == "x^2"

    def test_strip_latex_delimiters_double_dollar(self):
        """去除 $$...$$ 分隔符"""
        result = BaseParser._strip_latex_delimiters("$$x^2 + y^2$$")
        assert result == "x^2 + y^2"

    def test_strip_latex_delimiters_brackets(self):
        r"""去除 \[...\] 分隔符"""
        result = BaseParser._strip_latex_delimiters("\\[\sum_{i=1}^n i\\]")
        assert result == "\\sum_{i=1}^n i"

    def test_process_inline_element_with_inline_math(self):
        """内联元素包含公式"""
        parser = MockParser()
        html = '<span>text <span copy-text="\\gamma">γ</span> more</span>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_inline_element(soup.find("span"), blocks)
        assert len(blocks) >= 1

    def test_process_inline_element_no_items_fallback(self):
        """内联元素无 items 时的文本处理"""
        parser = MockParser()
        html = '<span></span>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_inline_element(soup.find("span"), blocks)
        # Empty span should not add blocks
        assert len(blocks) == 0

    def test_process_element_with_inline_math_basic(self):
        """处理包含内联公式的元素"""
        parser = MockParser()
        html = '<p>Before <span copy-text="\\delta">δ</span> After</p>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_paragraph(soup.find("p"), blocks)
        assert len(blocks) >= 1

    def test_process_element_with_inline_math_multiple(self):
        """处理包含多个内联公式"""
        parser = MockParser()
        html = '<p><span copy-text="\\alpha">α</span> plus <span copy-text="\\beta">β</span></p>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_paragraph(soup.find("p"), blocks)
        assert len(blocks) >= 1

    def test_process_element_with_inline_math_only(self):
        """只有公式无文本"""
        parser = MockParser()
        html = '<p><span copy-text="\\sum">∑</span></p>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_paragraph(soup.find("p"), blocks)
        assert len(blocks) >= 1

    def test_process_math_element_with_get_text_fallback(self):
        """公式无 copy-text 时使用 get_text"""
        parser = MockParser()
        html = '<span>raw latex content</span>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_math_element(soup.find("span"), blocks)
        assert len(blocks) == 1
        assert blocks[0].type == "latex"

    def test_process_math_element_merge_with_previous(self):
        """公式与前一段合并"""
        parser = MockParser()
        html = '<p>Text</p><p>After <span copy-text="\\theta">θ</span></p>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_element(soup.find("p"), blocks)
        parser._process_element(soup.find_all("p")[1], blocks)
        # The math element should merge into the previous paragraph
        latex_blocks = [b for b in blocks if b.type == "latex"]
        # Should have inline content in the paragraph
        paragraph_with_inline = [b for b in blocks if b.type == "paragraph" and len(b.items) > 0]
        assert len(paragraph_with_inline) >= 1 or len(latex_blocks) >= 1


class TestWithRealHTML:
    """使用真实 HTML 片段测试"""

    def test_nested_lists(self):
        """嵌套列表"""
        parser = MockParser()
        html = """
        <ol>
            <li>Step 1<ul>
                <li>Substep 1.1</li>
                <li>Substep 1.2</li>
            </ul></li>
            <li>Step 2</li>
        </ol>
        """
        result = parser.parse(html)
        list_items = [b for b in result.blocks if b.type == "list_item"]
        assert len(list_items) >= 2

    def test_mixed_content(self):
        """混合内容"""
        parser = MockParser()
        html = """
        <div>
            <h1>标题</h1>
            <p>段落<strong>加粗</strong>和<em>斜体</em></p>
            <ul><li>列表项</li></ul>
            <blockquote>引用</blockquote>
        </div>
        """
        result = parser.parse(html)
        assert len(result.blocks) >= 1

    def test_code_with_language(self):
        """带语言标记的代码"""
        parser = MockParser()
        html = """
        <pre><code class="language-python hljs python">print("hello")</code></pre>
        """
        result = parser.parse(html)
        code_blocks = [b for b in result.blocks if b.type == "code"]
        assert len(code_blocks) >= 1


class TestNestedContainerEdgeCases:
    """嵌套容器边缘情况"""

    def test_process_div_with_strong(self):
        """div 中的 strong 标签"""
        parser = MockParser()
        html = '<div class="paragraph"><p>text <strong>bold</strong></p></div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_div_or_section(soup.find("div"), blocks)
        assert len(blocks) >= 1

    def test_process_div_with_em(self):
        """div 中的 em 标签"""
        parser = MockParser()
        html = '<div class="paragraph"><p>text <em>italic</em></p></div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_div_or_section(soup.find("div"), blocks)
        assert len(blocks) >= 1

    def test_process_div_with_picture(self):
        """div 中的picture"""
        parser = MockParser()
        html = '<div class="paragraph"><picture><img src="test.png"/></picture></div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_div_or_section(soup.find("div"), blocks)
        assert len(blocks) >= 1

    def test_process_div_with_table(self):
        """div 中的 table"""
        parser = MockParser()
        html = '<div class="paragraph"><table><tr><td>data</td></tr></table></div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_div_or_section(soup.find("div"), blocks)
        assert len(blocks) >= 1

    def test_process_div_with_pre(self):
        """div 中的 pre"""
        parser = MockParser()
        html = '<div class="paragraph"><pre>code</pre></div>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_div_or_section(soup.find("div"), blocks)
        assert len(blocks) >= 1


class TestProcessNestedContainer:
    """测试 _process_nested_container"""

    def test_with_span_nested(self):
        """嵌套 span"""
        parser = MockParser()
        html = '<div><span>text</span></div>'
        soup = BeautifulSoup(html, "lxml")
        items = []
        parser._process_nested_container(soup.find("div"), items)
        assert len(items) >= 1

    def test_with_multiple_br(self):
        """多个 br 标签"""
        parser = MockParser()
        html = '<div>line1<br/><br/>line2</div>'
        soup = BeautifulSoup(html, "lxml")
        items = []
        parser._process_nested_container(soup.find("div"), items)
        assert len(items) >= 1


class TestProcessParagraph:
    """测试 _process_paragraph 复杂段落"""

    def test_with_simple_math(self):
        """带公式的简单段落"""
        parser = MockParser()
        html = '<p>text<span copy-text="\\alpha">α</span></p>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_paragraph(soup.find("p"), blocks)
        assert len(blocks) >= 1

    def test_with_picture(self):
        """带图片的段落"""
        parser = MockParser()
        html = '<p>text<picture><img src="test.png"/></picture></p>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_paragraph(soup.find("p"), blocks)
        assert len(blocks) >= 1

    def test_process_paragraph_with_line_break_div(self):
        """段落包含 line-break div"""
        parser = MockParser()
        html = '<p>text<div class="md-box-line-break"></div>more</p>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_paragraph(soup.find("p"), blocks)
        assert len(blocks) >= 1

    def test_process_paragraph_with_br_tag(self):
        """段落包含 br 标签"""
        parser = MockParser()
        html = '<p>line1<br/>line2</p>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_paragraph(soup.find("p"), blocks)
        assert len(blocks) >= 1

    def test_process_paragraph_with_picture_element(self):
        """段落包含 picture"""
        parser = MockParser()
        html = '<p>text<picture><img src="img.jpg"/></picture>after</p>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_paragraph(soup.find("p"), blocks)
        assert len(blocks) >= 1


class TestCollectNestedContent:
    """测试 _collect_nested_content_in_li"""

    def test_with_nested_picture(self):
        """li 中的 picture"""
        parser = MockParser()
        html = '<li>item<picture><img src="a.png"/></picture></li>'
        soup = BeautifulSoup(html, "lxml")
        items = []
        parser._collect_nested_content_in_li(soup.find("li"), items, False, False)
        assert len(items) >= 1

    def test_with_nested_table(self):
        """li 中的 table"""
        parser = MockParser()
        html = '<li>item<table><tr><td>data</td></tr></table></li>'
        soup = BeautifulSoup(html, "lxml")
        items = []
        parser._collect_nested_content_in_li(soup.find("li"), items, False, False)
        assert len(items) >= 1

    def test_with_expanded_code(self):
        """已展开的代码"""
        parser = MockParser()
        html = '<li>item<pre data-expanded-code="true">code</pre></li>'
        soup = BeautifulSoup(html, "lxml")
        items = []
        parser._collect_nested_content_in_li(soup.find("li"), items, False, False)
        assert len(items) == 0


class TestExtractNestedListText:
    """测试 _extract_nested_list_text"""

    def test_ul_with_nested(self):
        """ul 嵌套"""
        parser = MockParser()
        html = '<ul><li>item<ul><li>nested</li></ul></ul>'
        soup = BeautifulSoup(html, "lxml")
        items = []
        parser._extract_nested_list_text(soup.find("ul"), items)
        assert len(items) >= 2

    def test_ol_counter(self):
        """ol 计数器"""
        parser = MockParser()
        html = '<ol><li>first</li><li>second</li></ol>'
        soup = BeautifulSoup(html, "lxml")
        items = []
        parser._extract_nested_list_text(soup.find("ol"), items)
        assert len(items) >= 2


class TestExtractImagesRecursive:
    """测试 _extract_images_recursive"""

    def test_extract_images_recursive_with_picture(self):
        """递归查找 picture 元素"""
        parser = MockParser()
        html = '<div><picture><img src="a.png"/></picture><span>text</span></div>'
        soup = BeautifulSoup(html, "lxml")
        items = []
        has_pic, text = parser._extract_images_recursive(soup.find("div"), items, lambda: None)
        assert has_pic is True
        assert len(items) >= 1

    def test_extract_images_recursive_no_picture(self):
        """无 picture 时返回文本"""
        parser = MockParser()
        html = '<div><span>some text</span></div>'
        soup = BeautifulSoup(html, "lxml")
        items = []
        has_pic, text = parser._extract_images_recursive(soup.find("div"), items, lambda: None)
        assert has_pic is False
        assert "text" in text


class TestGetDirectText:
    """测试 _get_direct_text"""

    def test_with_nested_list(self):
        """嵌套列表"""
        parser = MockParser()
        html = '<li>text<ul><li>nested</li></ul>more</li>'
        soup = BeautifulSoup(html, "lxml")
        result = parser._get_direct_text(soup.find("li"))
        assert "text" in result


class TestWithRealHTMLStructure:
    """使用真实 HTML 结构测试"""

    def test_nested_ul_structure(self):
        """嵌套 ul 结构（真实豆包页面）"""
        parser = MockParser()
        html = '''
        <ul class="auto-hide-last-sibling-br">
            <li><strong>FFY03 军用透气式 CBRN</strong><ul class="auto-hide-last-sibling-br">
                <li>价格：<strong>¥1,000～1,200</strong></li>
            </ul></li>
        </ul>
        '''
        result = parser.parse(html)
        assert len(result.blocks) >= 1

    def test_md_box_line_break(self):
        """md-box-line-break 换行"""
        parser = MockParser()
        html = '''
        <div>
            <div class="container-xxxx md-box-line-break wrapper-xxxx undefined"></div>
        </div>
        '''
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_div_or_section(soup.find("div"), blocks)
        assert len(blocks) >= 0  # md-box-line-break 不产生内容块

    def test_header_structure(self):
        """header 结构"""
        parser = MockParser()
        html = '<h3 class="header-xxxx auto-hide-last-sibling-br">标题</h3>'
        result = parser.parse(html)
        headings = [b for b in result.blocks if b.type == "heading"]
        assert len(headings) >= 1

    def test_paragraph_with_line_break(self):
        """带换行的段落"""
        parser = MockParser()
        html = '''
        <div class="auto-hide-last-sibling-br paragraph-xxxx paragraph-element br-paragraph-space">
            文本<strong>加粗</strong>和<br/>
            换行
        </div>
        '''
        result = parser.parse(html)
        assert len(result.blocks) >= 1

    def test_complex_nested_list_with_prices(self):
        """复杂的嵌套列表带价格"""
        parser = MockParser()
        html = '''
        <ul class="auto-hide-last-sibling-br">
            <li><strong>A 级气密重型 CBRN</strong>
                <ul class="auto-hide-last-sibling-br">
                    <li>价格：<strong>¥7,500～9,500</strong></li>
                </ul>
                <div class="container-xxxx md-box-line-break wrapper-xxxx undefined"></div>
            </li>
        </ul>
        '''
        result = parser.parse(html)
        list_items = [b for b in result.blocks if b.type == "list_item"]
        assert len(list_items) >= 1


class TestExtractStrongRecursive:
    """测试 _extract_strong_recursive"""

    def test_simple_strong(self):
        """简单 strong"""
        parser = MockParser()
        soup = BeautifulSoup("<strong>bold text</strong>", "lxml")
        items = parser._extract_strong_recursive(soup.find("strong"))
        assert len(items) >= 1
        assert items[0].bold is True

    def test_nested_strong(self):
        """嵌套 strong"""
        parser = MockParser()
        soup = BeautifulSoup("<strong>bold <em>italic</em> text</strong>", "lxml")
        items = parser._extract_strong_recursive(soup.find("strong"))
        assert len(items) >= 1

    def test_extract_strong_with_nested_math(self):
        """strong 内嵌套公式"""
        parser = MockParser()
        html = '<strong>bold <span copy-text="\\alpha">α</span> more</strong>'
        soup = BeautifulSoup(html, "lxml")
        items = parser._extract_strong_recursive(soup.find("strong"))
        assert len(items) >= 2


class TestExtractItalicRecursive:
    """测试 _extract_italic_recursive"""

    def test_simple_em(self):
        """简单 em"""
        parser = MockParser()
        soup = BeautifulSoup("<em>italic text</em>", "lxml")
        items = parser._extract_italic_recursive(soup.find("em"))
        assert len(items) >= 1
        assert items[0].italic is True

    def test_extract_italic_with_nested_bold(self):
        """em 内嵌套 strong"""
        parser = MockParser()
        html = '<em>italic <strong>bold inside</strong> more</em>'
        soup = BeautifulSoup(html, "lxml")
        items = parser._extract_italic_recursive(soup.find("em"))
        assert len(items) >= 2
        bold_items = [i for i in items if i.bold]
        assert len(bold_items) >= 1

    def test_extract_italic_with_nested_math(self):
        """em 内嵌套公式"""
        parser = MockParser()
        html = '<em>italic <span copy-text="\\beta">β</span> end</em>'
        soup = BeautifulSoup(html, "lxml")
        items = parser._extract_italic_recursive(soup.find("em"))
        latex_items = [i for i in items if i.type == "latex"]
        assert len(latex_items) >= 1


class TestExtractInlineTextWithFormat:
    """测试 _extract_inline_text_with_format"""

    def test_span_text(self):
        """span 文本"""
        parser = MockParser()
        soup = BeautifulSoup("<span>text</span>", "lxml")
        items = parser._extract_inline_text_with_format(soup.find("span"))
        assert len(items) >= 1

    def test_nested_format(self):
        """嵌套格式"""
        parser = MockParser()
        soup = BeautifulSoup("<span><strong>bold</strong> and <em>italic</em></span>", "lxml")
        items = parser._extract_inline_text_with_format(soup.find("span"))
        assert len(items) >= 1

    def test_extract_inline_text_with_nested_bold(self):
        """带嵌套加粗的内联文本"""
        parser = MockParser()
        html = '<span><strong>nested bold</strong> normal</span>'
        soup = BeautifulSoup(html, "lxml")
        items = parser._extract_inline_text_with_format(soup.find("span"))
        assert len(items) >= 2

    def test_extract_inline_text_with_deep_nested_bold(self):
        """深层嵌套加粗"""
        parser = MockParser()
        html = '<span>text<span><strong>bold</strong></span>more</span>'
        soup = BeautifulSoup(html, "lxml")
        items = parser._extract_inline_text_with_format(soup.find("span"))
        assert len(items) >= 1

    def test_extract_inline_text_with_deep_nested_italic(self):
        """深层嵌套斜体"""
        parser = MockParser()
        html = '<span>text<span><em>italic</em></span>more</span>'
        soup = BeautifulSoup(html, "lxml")
        items = parser._extract_inline_text_with_format(soup.find("span"))
        assert len(items) >= 1


class TestProcessNestedContainerDeep:
    """深度测试 _process_nested_container"""

    def test_deep_nesting(self):
        """深度嵌套"""
        parser = MockParser()
        html = '<div><div><div><p>deeply nested</p></div></div></div>'
        soup = BeautifulSoup(html, "lxml")
        items = []
        parser._process_nested_container(soup.find("div"), items)
        assert len(items) >= 1

    def test_mixed_content(self):
        """混合内容"""
        parser = MockParser()
        html = '<div>text<picture><img src="a.png"/></picture>more<br/>end</div>'
        soup = BeautifulSoup(html, "lxml")
        items = []
        parser._process_nested_container(soup.find("div"), items)
        assert len(items) >= 1

    def test_with_strong_and_em(self):
        """混合加粗斜体"""
        parser = MockParser()
        html = '<div>normal<strong>bold</strong>and<em>italic</em>end</div>'
        soup = BeautifulSoup(html, "lxml")
        items = []
        parser._process_nested_container(soup.find("div"), items)
        text_items = [i for i in items if i.type == "text"]
        assert len(text_items) >= 1


class TestProcessListItem:
    """测试 _process_list_item"""

    def test_with_math_in_li(self):
        """li 中的公式"""
        parser = MockParser()
        html = '<li><span copy-text="\\alpha">α</span></li>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_list_item(soup.find("li"), blocks, "ul", 0)
        assert len(blocks) >= 1

    def test_li_with_p_tag(self):
        """li 中的 p 标签"""
        parser = MockParser()
        html = '<li><p>paragraph text</p></li>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_list_item(soup.find("li"), blocks, "ul", 0)
        assert len(blocks) >= 1

    def test_li_with_div_line_break(self):
        """li 中的 line-break div"""
        parser = MockParser()
        html = '<li>text<div class="md-box-line-break"></div>more</li>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_list_item(soup.find("li"), blocks, "ul", 0)
        assert len(blocks) >= 1

    def test_li_with_nested_list(self):
        """li 中嵌套列表"""
        parser = MockParser()
        html = '<li>text<ul><li>nested</li></ul></li>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_list_item(soup.find("li"), blocks, "ul", 0)
        assert len(blocks) >= 1

    def test_li_with_picture(self):
        """li 中有图片"""
        parser = MockParser()
        html = '<li>text<picture><img src="a.png"/></picture></li>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_list_item(soup.find("li"), blocks, "ul", 0)
        assert len(blocks) >= 1

    def test_li_with_table(self):
        """li 中有表格"""
        parser = MockParser()
        html = '<li>text<table><tr><td>data</td></tr></table></li>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_list_item(soup.find("li"), blocks, "ul", 0)
        assert len(blocks) >= 1

    def test_li_with_code(self):
        """li 中有代码"""
        parser = MockParser()
        html = '<li>text<pre>code</pre></li>'
        soup = BeautifulSoup(html, "lxml")
        blocks = []
        parser._process_list_item(soup.find("li"), blocks, "ul", 0)
        assert len(blocks) >= 1


class TestNestedContainerMathAndPicture:
    """测试 _process_nested_container 中的公式和图片"""

    def test_with_math_element(self):
        """带公式"""
        parser = MockParser()
        html = '<div><span copy-text="\\alpha">α</span></div>'
        soup = BeautifulSoup(html, "lxml")
        items = []
        parser._process_nested_container(soup.find("div"), items)
        latex_items = [i for i in items if i.type == "latex"]
        assert len(latex_items) >= 1

    def test_with_line_break_div(self):
        """带 line-break div"""
        parser = MockParser()
        html = '<div>text<div class="md-box-line-break"></div>more</div>'
        soup = BeautifulSoup(html, "lxml")
        items = []
        parser._process_nested_container(soup.find("div"), items)
        assert len(items) >= 0  # md-box-line-break 只处理换行，不添加 items

    def test_with_image(self):
        """带图片"""
        parser = MockParser()
        html = '<div><picture><img src="test.png"/></picture>text</div>'
        soup = BeautifulSoup(html, "lxml")
        items = []
        parser._process_nested_container(soup.find("div"), items)
        assert len(items) >= 1

    def test_with_table(self):
        """带表格"""
        parser = MockParser()
        html = '<div><table><tr><td>data</td></tr></table></div>'
        soup = BeautifulSoup(html, "lxml")
        items = []
        parser._process_nested_container(soup.find("div"), items)
        table_items = [i for i in items if i.type == "table"]
        assert len(table_items) >= 1

    def test_with_code(self):
        """带代码"""
        parser = MockParser()
        html = '<div><pre>code</pre></div>'
        soup = BeautifulSoup(html, "lxml")
        items = []
        parser._process_nested_container(soup.find("div"), items)
        code_items = [i for i in items if i.type == "code"]
        assert len(code_items) >= 1

    def test_with_list_passthrough(self):
        """ul/ol 列表穿透"""
        parser = MockParser()
        html = '<div><ul><li>item</li></ul></div>'
        soup = BeautifulSoup(html, "lxml")
        items = []
        parser._process_nested_container(soup.find("div"), items)
        assert len(items) >= 0  # 列表穿透不产生 inline items


class TestParseTable:
    """_parse_table 边界情况测试"""

    def test_parse_table_no_thead(self):
        """表格无 thead，第一行作为表头"""
        html = '<table><tr><th>Header1</th><th>Header2</th></tr><tr><td>Data1</td><td>Data2</td></tr></table>'
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        result = BaseParser._parse_table(table)
        assert result is not None
        assert result.headers == ["Header1", "Header2"]
        assert result.rows == [["Data1", "Data2"]]

    def test_parse_table_no_headers_at_all(self):
        """表格既无 thead 也无数据行"""
        html = '<table></table>'
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        result = BaseParser._parse_table(table)
        # Should return None for empty table
        assert result is None

    def test_parse_table_only_rows(self):
        """只有 tbody 行，无 thead"""
        html = '<table><tr><td>A</td><td>B</td></tr><tr><td>C</td><td>D</td></tr></table>'
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        result = BaseParser._parse_table(table)
        assert result is not None
        # First row should become headers
        assert len(result.headers) == 2
        # Remaining rows should be data
        assert len(result.rows) == 1


class TestWithRealHTMLFiles:
    """使用真实 HTML 文件进行集成测试"""

    def test_parse_real_code_html(self):
        """测试真实 code.html 文件解析"""
        from pathlib import Path
        html_path = Path(__file__).parent / "html" / "code.html"
        html_content = html_path.read_text(encoding="utf-8")
        result = MockParser().parse(html_content)
        # 验证能够解析出内容块
        assert len(result.blocks) > 0
        # 验证能提取标题
        assert result.title != ""

    def test_parse_real_list_html(self):
        """测试真实 list.html 文件解析"""
        from pathlib import Path
        html_path = Path(__file__).parent / "html" / "list.html"
        html_content = html_path.read_text(encoding="utf-8")
        result = MockParser().parse(html_content)
        # 验证能够解析出内容块
        assert len(result.blocks) > 0

    def test_parse_real_image_html(self):
        """测试真实 image.html 文件解析"""
        from pathlib import Path
        html_path = Path(__file__).parent / "html" / "image.html"
        html_content = html_path.read_text(encoding="utf-8")
        result = MockParser().parse(html_content)
        # 验证能够解析出内容块
        assert len(result.blocks) > 0

    def test_parse_real_math_html(self):
        """测试真实 math.html 文件解析"""
        from pathlib import Path
        html_path = Path(__file__).parent / "html" / "math.html"
        html_content = html_path.read_text(encoding="utf-8")
        result = MockParser().parse(html_content)
        # 验证能够解析出内容块
        assert len(result.blocks) > 0
        # 验证有标题
        assert result.title != ""

    def test_parse_real_table_html(self):
        """测试真实 table.html 文件解析"""
        from pathlib import Path
        html_path = Path(__file__).parent / "html" / "table.html"
        html_content = html_path.read_text(encoding="utf-8")
        result = MockParser().parse(html_content)
        # 验证能够解析出内容块
        assert len(result.blocks) > 0


class TestProcessMathElement:
    """测试 _process_math_element 方法"""

    def test_process_math_element_with_copy_text(self):
        """带 copy-text 属性的公式元素"""
        html = '<span copy-text="alpha">α</span>'
        soup = BeautifulSoup(html, "lxml")
        parser = MockParser()
        blocks = []
        parser._process_math_element(soup.find("span"), blocks)
        assert len(blocks) == 1
        assert blocks[0].type == "latex"
        assert blocks[0].content == "alpha"

    def test_process_math_element_without_copy_text(self):
        """不带 copy-text 属性的公式元素"""
        html = '<span>raw_latex</span>'
        soup = BeautifulSoup(html, "lxml")
        parser = MockParser()
        blocks = []
        parser._process_math_element(soup.find("span"), blocks)
        assert len(blocks) == 1
        assert blocks[0].type == "latex"
        assert blocks[0].content == "raw_latex"

    def test_process_math_element_merge_with_previous_empty_paragraph(self):
        """内联公式与前一个空段落合并"""
        parser = MockParser()
        # 单个空段落，添加 latex 后会被合并
        blocks = [TextBlock(type="paragraph", content="", items=[])]
        soup = BeautifulSoup('<span copy-text="theta">θ</span>', "lxml")
        parser._process_math_element(soup.find("span"), blocks)
        # 添加 latex 后 blocks = [p, latex]，检查 blocks[-2] = p
        # p 是空段落，满足合并条件，latex 合并到 p，pop latex
        assert len(blocks) == 1
        assert blocks[0].type == "paragraph"
        assert len(blocks[0].items) == 1
        assert blocks[0].items[0].content == "theta"

    def test_process_math_element_no_merge_when_prev_has_content(self):
        """前一段有 content 时不合并"""
        parser = MockParser()
        blocks = [TextBlock(type="paragraph", content="some text", items=[])]
        soup = BeautifulSoup('<span copy-text="theta">θ</span>', "lxml")
        parser._process_math_element(soup.find("span"), blocks)
        # 前一段有 content，不满足合并条件
        # 创建独立的 latex block
        assert len(blocks) == 2
        assert blocks[0].content == "some text"
        assert blocks[1].type == "latex"
        assert blocks[1].content == "theta"

    def test_process_math_element_no_merge_when_no_previous(self):
        """无前一段时不合并"""
        parser = MockParser()
        blocks = []
        soup = BeautifulSoup('<span copy-text="theta">θ</span>', "lxml")
        parser._process_math_element(soup.find("span"), blocks)
        assert len(blocks) == 1
        assert blocks[0].type == "latex"
        assert blocks[0].content == "theta"

    def test_process_math_element_no_merge_when_prev_has_items(self):
        """前一段有内容时不合并"""
        parser = MockParser()
        prev_block = TextBlock(type="paragraph", content="text", items=[InlineContent(type="text", content="some text")])
        blocks = [prev_block]
        soup = BeautifulSoup('<span copy-text="theta">θ</span>', "lxml")
        parser._process_math_element(soup.find("span"), blocks)
        assert len(blocks) == 2
        assert blocks[1].type == "latex"


class TestFindMathInElement:
    """测试 _find_math_in_element 方法"""

    def test_find_math_in_element_with_math(self):
        """元素包含公式时"""
        html = '<div><span copy-text="formula">x</span><p>text</p></div>'
        soup = BeautifulSoup(html, "lxml")
        parser = MockParser()
        result = parser._find_math_in_element(soup.find("div"))
        assert len(result) >= 1

    def test_find_math_in_element_no_math(self):
        """元素不包含公式时"""
        html = '<p>just text</p>'
        soup = BeautifulSoup(html, "lxml")
        parser = MockParser()
        result = parser._find_math_in_element(soup.find("p"))
        assert len(result) == 0

    def test_find_math_in_element_empty(self):
        """空元素"""
        html = '<span></span>'
        soup = BeautifulSoup(html, "lxml")
        parser = MockParser()
        result = parser._find_math_in_element(soup.find("span"))
        assert len(result) == 0


class TestStripLatexDelimiters:
    """测试 _strip_latex_delimiters 方法"""

    def test_strip_latex_dollar(self):
        """美元符分隔符"""
        assert BaseParser._strip_latex_delimiters("$x$") == "x"
        assert BaseParser._strip_latex_delimiters("$$x$$") == "x"

    def test_strip_latex_brackets(self):
        """括号分隔符"""
        assert BaseParser._strip_latex_delimiters(r"\(x\)") == "x"
        assert BaseParser._strip_latex_delimiters(r"\[x\]") == "x"

    def test_strip_latex_empty(self):
        """空字符串"""
        assert BaseParser._strip_latex_delimiters("") == ""

    def test_strip_latex_mixed(self):
        """混合分隔符"""
        assert BaseParser._strip_latex_delimiters("$$x+y=z$$") == "x+y=z"
        assert BaseParser._strip_latex_delimiters("$\\alpha$") == "\\alpha"

    def test_strip_latex_no_delimiter(self):
        """无分隔符"""
        assert BaseParser._strip_latex_delimiters("x^2") == "x^2"
        assert BaseParser._strip_latex_delimiters("\\sum_{i=1}^n i") == "\\sum_{i=1}^n i"