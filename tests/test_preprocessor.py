"""
测试 HTML 解析器基类
"""
import pytest
from bs4 import BeautifulSoup
from src.preprocessor.base import (
    BaseParser, PlatformConfig, TextBlock, InlineContent, TableData, ParsedPage
)


class TestPlatformConfig:
    """测试 PlatformConfig 数据类"""

    def test_default_values(self):
        """默认配置值"""
        config = PlatformConfig()
        assert config.name == "doubao"
        assert config.parser == "lxml"
        assert len(config.math_display_classes) == 2

    def test_custom_values(self):
        """自定义配置值"""
        config = PlatformConfig(
            name="custom",
            latex_attr="custom-latex",
            code_container_class="custom-code"
        )
        assert config.name == "custom"
        assert config.latex_attr == "custom-latex"
        assert config.code_container_class == "custom-code"


class TestDataClasses:
    """测试数据类"""

    def test_table_data(self):
        """TableData 数据类"""
        table = TableData(
            headers=["A", "B"],
            rows=[["1", "2"], ["3", "4"]],
            header_bold=[True, False],
            cell_bold=[[False, False], [True, True]]
        )
        assert len(table.headers) == 2
        assert len(table.rows) == 2

    def test_inline_content(self):
        """InlineContent 数据类"""
        content = InlineContent(
            type="text",
            content="Hello",
            bold=True,
            italic=False,
            image_url=None
        )
        assert content.type == "text"
        assert content.bold is True

    def test_text_block(self):
        """TextBlock 数据类"""
        block = TextBlock(
            type="paragraph",
            content="Test content",
            language="en",
            level=1
        )
        assert block.type == "paragraph"
        assert block.level == 1

    def test_parsed_page(self):
        """ParsedPage 数据类"""
        page = ParsedPage(
            title="Test Page",
            blocks=[
                TextBlock(type="paragraph", content="Hello"),
                TextBlock(type="code", content="print('hi')", language="python")
            ],
            latex_fallback_count=0
        )
        assert page.title == "Test Page"
        assert len(page.blocks) == 2


class MockParser(BaseParser):
    """模拟解析器，用于测试基类功能"""

    def __init__(self):
        self.config = PlatformConfig()

    def _get_title_selectors(self):
        return ["h1", ".title"]

    def _is_math_element(self, element):
        return False

    def _is_display_math(self, element):
        return False

    def _is_code_container(self, element):
        return False

    def _is_paragraph_container(self, element):
        return False

    def _is_code_button(self, element):
        return False

    def _extract_latex_content(self, element):
        return ""

    def _is_image_element(self, element):
        return False

    def _extract_image_url(self, element):
        return ""


class TestBaseParser:
    """测试 BaseParser 基类"""

    def test_parse_simple_html(self):
        """解析简单 HTML"""
        parser = MockParser()
        html = "<html><body><p>Hello World</p></body></html>"
        result = parser.parse(html)
        assert isinstance(result, ParsedPage)

    def test_extract_title_with_h1(self):
        """提取 h1 标题"""
        parser = MockParser()
        html = "<html><body><h1>Test Title</h1></body></html>"
        result = parser.parse(html)
        assert result.title == "Test Title"

    def test_extract_title_with_selector(self):
        """使用选择器提取标题"""
        parser = MockParser()
        html = "<html><body><div class='title'>Custom Title</div></body></html>"
        result = parser.parse(html)
        assert result.title == "Custom Title"

    def test_extract_title_fallback_to_title_tag(self):
        """标题标签作为后备"""
        parser = MockParser()
        html = "<html><head><title>Page Title</title></head><body></body></html>"
        result = parser.parse(html)
        assert result.title == "Page Title"

    def test_parse_paragraph(self):
        """解析段落"""
        parser = MockParser()
        html = "<html><body><p>Paragraph content</p></body></html>"
        result = parser.parse(html)
        assert len(result.blocks) >= 1

    def test_parse_heading(self):
        """解析标题"""
        parser = MockParser()
        html = "<html><body><h1>Heading 1</h1><h2>Heading 2</h2></body></html>"
        result = parser.parse(html)
        headings = [b for b in result.blocks if b.type == "heading"]
        assert len(headings) == 2

    def test_parse_code_block(self):
        """解析代码块"""
        parser = MockParser()
        html = "<html><body><pre><code class='python'>print('hello')</code></pre></body></html>"
        result = parser.parse(html)
        code_blocks = [b for b in result.blocks if b.type == "code"]
        assert len(code_blocks) >= 1

    def test_parse_blockquote(self):
        """解析引用"""
        parser = MockParser()
        html = "<html><body><blockquote>Quote text</blockquote></body></html>"
        result = parser.parse(html)
        quotes = [b for b in result.blocks if b.type == "blockquote"]
        assert len(quotes) == 1

    def test_strip_latex_delimiters(self):
        """去除 LaTeX 分隔符"""
        tests = [
            (r"\[x^2\]", "x^2"),
            (r"$$y^2$$", "y^2"),
            (r"\(z^2\)", "z^2"),
            (r"$w^2$", "w^2"),
            ("no delimiters", "no delimiters"),
        ]
        for input_latex, expected in tests:
            result = BaseParser._strip_latex_delimiters(input_latex)
            assert result == expected, f"Failed for {input_latex}"

    def test_has_any_class(self):
        """检查元素类名"""
        parser = MockParser()
        soup = BeautifulSoup("<div class='foo bar'></div>", "lxml")
        div = soup.find("div")
        assert parser._has_any_class(div, ["foo", "baz"]) is True
        assert parser._has_any_class(div, ["baz", "qux"]) is False

    def test_parse_table(self):
        """解析表格"""
        html = """
        <table>
            <thead><tr><th>Header 1</th><th>Header 2</th></tr></thead>
            <tbody>
                <tr><td>Cell 1</td><td>Cell 2</td></tr>
            </tbody>
        </table>
        """
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        result = BaseParser._parse_table(table)
        assert result is not None
        assert result.headers == ["Header 1", "Header 2"]
        assert len(result.rows) == 1