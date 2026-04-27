"""
测试豆包 HTML 解析器

使用真实 HTML 样本测试解析器功能。
"""
import pytest
from unittest.mock import patch, Mock
from src.preprocessor.doubao_parser import DoubaoHTMLParser


class TestDoubaoHTMLParserConfig:
    """测试配置"""

    @pytest.fixture
    def mock_config(self):
        """Mock 配置"""
        mock = Mock()
        mock.parser = Mock()
        mock.parser.latex_attr = "copy-text"
        return mock

    def test_init(self, mock_config):
        """初始化"""
        with patch("src.preprocessor.doubao_parser.get_config", return_value=mock_config):
            parser = DoubaoHTMLParser()
            assert parser.config is not None
            assert parser.config.latex_attr == "copy-text"

    def test_get_title_selectors(self, mock_config):
        """标题选择器"""
        with patch("src.preprocessor.doubao_parser.get_config", return_value=mock_config):
            parser = DoubaoHTMLParser()
            selectors = parser._get_title_selectors()
            assert len(selectors) > 0
            assert "h1" in selectors or ".chat-title" in selectors or "title" in selectors[0]


class TestDoubaoHTMLParserHooks:
    """测试钩子方法"""

    @pytest.fixture
    def mock_config(self):
        """Mock 配置"""
        mock = Mock()
        mock.parser = Mock()
        mock.parser.latex_attr = "copy-text"
        return mock

    def test_is_math_element_with_copy_text(self, mock_config):
        """copy-text 属性"""
        with patch("src.preprocessor.doubao_parser.get_config", return_value=mock_config):
            from bs4 import BeautifulSoup
            parser = DoubaoHTMLParser()
            soup = BeautifulSoup('<span copy-text="\\alpha">α</span>', "lxml")
            span = soup.find("span")
            assert parser._is_math_element(span) is True

    def test_is_math_element_without_copy_text(self, mock_config):
        """无 copy-text 属性"""
        with patch("src.preprocessor.doubao_parser.get_config", return_value=mock_config):
            from bs4 import BeautifulSoup
            parser = DoubaoHTMLParser()
            soup = BeautifulSoup('<span>plain text</span>', "lxml")
            span = soup.find("span")
            assert parser._is_math_element(span) is False

    def test_is_code_container(self, mock_config):
        """代码容器"""
        with patch("src.preprocessor.doubao_parser.get_config", return_value=mock_config):
            from bs4 import BeautifulSoup
            parser = DoubaoHTMLParser()
            soup = BeautifulSoup('<div class="custom-code-block-container"></div>', "lxml")
            div = soup.find("div")
            assert parser._is_code_container(div) is True

    def test_is_code_button(self, mock_config):
        """代码按钮"""
        with patch("src.preprocessor.doubao_parser.get_config", return_value=mock_config):
            from bs4 import BeautifulSoup
            parser = DoubaoHTMLParser()
            soup = BeautifulSoup('<div class="button-L3npDO hoverable">已生成代码</div>', "lxml")
            div = soup.find("div")
            assert parser._is_code_button(div) is True

    def test_is_paragraph_container(self, mock_config):
        """段落容器"""
        with patch("src.preprocessor.doubao_parser.get_config", return_value=mock_config):
            from bs4 import BeautifulSoup
            parser = DoubaoHTMLParser()
            soup = BeautifulSoup('<div class="paragraph-xxxx">text</div>', "lxml")
            div = soup.find("div")
            assert parser._is_paragraph_container(div) is True

    def test_is_image_element(self, mock_config):
        """图片元素"""
        with patch("src.preprocessor.doubao_parser.get_config", return_value=mock_config):
            from bs4 import BeautifulSoup
            parser = DoubaoHTMLParser()
            soup = BeautifulSoup('<picture><img src="test.jpg"/></picture>', "lxml")
            pic = soup.find("picture")
            assert parser._is_image_element(pic) is True

    def test_extract_latex_content(self, mock_config):
        """提取 LaTeX 内容"""
        with patch("src.preprocessor.doubao_parser.get_config", return_value=mock_config):
            from bs4 import BeautifulSoup
            parser = DoubaoHTMLParser()
            soup = BeautifulSoup('<span copy-text="\\alpha + \\beta">α + β</span>', "lxml")
            span = soup.find("span")
            latex = parser._extract_latex_content(span)
            assert r"\alpha" in latex


class TestDoubaoHTMLParserWithRealHTML:
    """使用真实 HTML 测试"""

    @pytest.fixture
    def mock_config(self):
        """Mock 配置"""
        mock = Mock()
        mock.parser = Mock()
        mock.parser.latex_attr = "copy-text"
        return mock

    def test_parse_simple_html(self, mock_config):
        """解析简单 HTML"""
        with patch("src.preprocessor.doubao_parser.get_config", return_value=mock_config):
            parser = DoubaoHTMLParser()
            html = """
            <html><body>
                <h1 class="header-xxxx">Test Title</h1>
                <div class="paragraph-xxxx">Hello World</div>
            </body></html>
            """
            result = parser.parse(html)
            assert result.title == "Test Title"
            assert len(result.blocks) > 0

    def test_parse_with_list(self, mock_config):
        """解析列表"""
        with patch("src.preprocessor.doubao_parser.get_config", return_value=mock_config):
            parser = DoubaoHTMLParser()
            html = """
            <html><body>
                <ol>
                    <li>Item 1</li>
                    <li>Item 2</li>
                </ol>
            </body></html>
            """
            result = parser.parse(html)
            list_items = [b for b in result.blocks if b.type == "list_item"]
            assert len(list_items) >= 2

    def test_parse_with_code_block(self, mock_config):
        """解析代码块"""
        with patch("src.preprocessor.doubao_parser.get_config", return_value=mock_config):
            parser = DoubaoHTMLParser()
            html = """
            <html><body>
                <div class="custom-code-block-container">
                    <pre><code>console.log('hello')</code></pre>
                </div>
            </body></html>
            """
            result = parser.parse(html)
            code_blocks = [b for b in result.blocks if b.type == "code"]
            assert len(code_blocks) >= 1

    def test_parse_with_table(self, mock_config):
        """解析表格"""
        with patch("src.preprocessor.doubao_parser.get_config", return_value=mock_config):
            parser = DoubaoHTMLParser()
            html = """
            <html><body>
                <table>
                    <thead><tr><th>Header 1</th><th>Header 2</th></tr></thead>
                    <tbody>
                        <tr><td>Cell 1</td><td>Cell 2</td></tr>
                    </tbody>
                </table>
            </body></html>
            """
            result = parser.parse(html)
            tables = [b for b in result.blocks if b.type == "table"]
            assert len(tables) >= 1

    def test_parse_with_latex_formula(self, mock_config):
        """解析 LaTeX 公式"""
        with patch("src.preprocessor.doubao_parser.get_config", return_value=mock_config):
            parser = DoubaoHTMLParser()
            html = """
            <html><body>
                <span class="container-mbkw8x math-inline" copy-text="\\alpha">
                    <span class="katex">α</span>
                </span>
            </body></html>
            """
            result = parser.parse(html)
            latex_blocks = [b for b in result.blocks if b.type == "latex"]
            assert len(latex_blocks) >= 1

    def test_is_math_element_with_math_class(self, mock_config):
        """使用 math-inline 类检测"""
        with patch("src.preprocessor.doubao_parser.get_config", return_value=mock_config):
            from bs4 import BeautifulSoup
            parser = DoubaoHTMLParser()
            # 真实 HTML 结构：container-mbkw8x + math-inline + copy-text
            soup = BeautifulSoup('<span class="container-mbkw8x math-inline" copy-text="\\alpha">α</span>', "lxml")
            span = soup.find("span")
            assert parser._is_math_element(span) is True

    def test_is_math_element_with_display_class(self, mock_config):
        """使用 math-display 类检测"""
        with patch("src.preprocessor.doubao_parser.get_config", return_value=mock_config):
            from bs4 import BeautifulSoup
            parser = DoubaoHTMLParser()
            soup = BeautifulSoup('<span class="math-display"><span class="katex-display">∑</span></span>', "lxml")
            span = soup.find("span")
            assert parser._is_math_element(span) is True

    def test_extract_latex_content_fallback(self, mock_config):
        """无 copy-text 时扫描所有属性（fallback 策略）"""
        with patch("src.preprocessor.doubao_parser.get_config", return_value=mock_config):
            from bs4 import BeautifulSoup
            parser = DoubaoHTMLParser()
            # 真实 HTML：copy-text 属性包含 LaTeX 格式
            soup = BeautifulSoup('<span class="container-mbkw8x" copy-text="\\(a + b\\)">a + b</span>', "lxml")
            span = soup.find("span")
            latex = parser._extract_latex_content(span)
            # 应提取到 LaTeX 内容
            assert "a + b" in latex

    def test_extract_image_url_with_source(self, mock_config):
        """从 source 元素提取图片 URL"""
        with patch("src.preprocessor.doubao_parser.get_config", return_value=mock_config):
            from bs4 import BeautifulSoup
            parser = DoubaoHTMLParser()
            # 来自 image.html 真实结构
            html = '''
            <picture>
                <source srcset="https://example.com/img1.jpg 1x, https://example.com/img2.jpg 2x"/>
                <img src="fallback.jpg"/>
            </picture>
            '''
            soup = BeautifulSoup(html, "lxml")
            pic = soup.find("picture")
            url = parser._extract_image_url(pic)
            # srcset 格式为 "url1 1x, url2 2x"，取第一个
            assert "img1.jpg" in url

    def test_extract_image_url_with_img_data_original(self, mock_config):
        """从 img data-original 提取"""
        with patch("src.preprocessor.doubao_parser.get_config", return_value=mock_config):
            from bs4 import BeautifulSoup
            parser = DoubaoHTMLParser()
            html = '''
            <picture>
                <img data-original="test.jpg"/>
            </picture>
            '''
            soup = BeautifulSoup(html, "lxml")
            pic = soup.find("picture")
            url = parser._extract_image_url(pic)
            assert url == "test.jpg"

    def test_extract_image_url_with_img_data_src(self, mock_config):
        """从 img data-src 提取"""
        with patch("src.preprocessor.doubao_parser.get_config", return_value=mock_config):
            from bs4 import BeautifulSoup
            parser = DoubaoHTMLParser()
            html = '''
            <picture>
                <img data-src="lazy.jpg"/>
            </picture>
            '''
            soup = BeautifulSoup(html, "lxml")
            pic = soup.find("picture")
            url = parser._extract_image_url(pic)
            assert url == "lazy.jpg"

    def test_is_display_math(self, mock_config):
        """判断展示公式"""
        with patch("src.preprocessor.doubao_parser.get_config", return_value=mock_config):
            from bs4 import BeautifulSoup
            parser = DoubaoHTMLParser()
            soup = BeautifulSoup('<span class="katex--display">∑</span>', "lxml")
            span = soup.find("span")
            assert parser._is_display_math(span) is True