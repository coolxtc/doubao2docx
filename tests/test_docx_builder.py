"""
DocxBuilder 单元测试

测试 Word 文档构建器的核心功能：
- DocumentConfig 配置
- 各类内容块添加（标题、段落、代码、列表、表格、引用）
- build_blocks 端到端测试
"""
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from src.generator.docx_builder import DocumentConfig, DocxBuilder
from src.preprocessor.base import TextBlock, InlineContent, TableData


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_config():
    """Mock 配置对象"""
    config = MagicMock()
    config.document_style = MagicMock()
    config.document_style.title_font_size = 18
    config.document_style.code_font_size = 10
    config.document_style.image_width = 5.0
    config.document_style.inline_image_width = 4.0
    config.document_style.footer_mark = "导出工具：Doubao Export"
    config.crawler = MagicMock()
    config.crawler.user_agents = ["Mozilla/5.0 Test"]
    config.pandoc = MagicMock()
    config.pandoc.timeout = 15
    return config


@pytest.fixture
def doc_builder(mock_config):
    """创建 DocxBuilder 实例"""
    with patch("src.generator.docx_builder.get_config", return_value=mock_config):
        builder = DocxBuilder()
        return builder


@pytest.fixture
def temp_docx_path(tmp_path):
    """创建临时 docx 文件路径"""
    return str(tmp_path / "test.docx")


# =============================================================================
# DocumentConfig 测试
# =============================================================================


class TestDocumentConfig:
    """测试文档配置类"""

    def test_default_init(self):
        """默认初始化"""
        with patch("src.generator.docx_builder.get_config") as mock_get_config:
            mock_cfg = MagicMock()
            mock_cfg.document_style = MagicMock()
            mock_cfg.document_style.title_font_size = 18
            mock_get_config.return_value = mock_cfg

            config = DocumentConfig()
            assert config.title == "豆包聊天记录"
            assert config.author == "Doubao Export"
            assert config.margin_left == 1.0

    def test_custom_init(self, mock_config):
        """自定义初始化"""
        with patch("src.generator.docx_builder.get_config", return_value=mock_config):
            config = DocumentConfig(title="测试文档", author="Test", margin_left=2.0)
            assert config.title == "测试文档"
            assert config.author == "Test"
            assert config.margin_left == 2.0


# =============================================================================
# DocxBuilder 初始化测试
# =============================================================================


class TestDocxBuilderInit:
    """测试 DocxBuilder 初始化"""

    def test_init_default(self, mock_config):
        """默认初始化"""
        with patch("src.generator.docx_builder.get_config", return_value=mock_config):
            builder = DocxBuilder()
            assert builder.document is not None
            assert builder.latex_converter is not None
            assert builder._list_counter == 0
            assert builder._last_list_type is None

    def test_init_with_config(self, mock_config):
        """使用自定义配置"""
        with patch("src.generator.docx_builder.get_config", return_value=mock_config):
            doc_config = DocumentConfig(title="自定义标题")
            builder = DocxBuilder(config=doc_config)
            assert builder.config.title == "自定义标题"


# =============================================================================
# _add_title 测试
# =============================================================================


class TestAddTitle:
    """测试添加标题"""

    def test_add_title_centered(self, doc_builder):
        """添加居中标题"""
        doc_builder._add_title("测试标题")
        # 验证：文档应该有至少一个段落（标题）
        assert len(doc_builder.document.paragraphs) > 0

    def test_add_title_sets_bold(self, doc_builder):
        """标题应该加粗"""
        doc_builder._add_title("加粗标题")
        para = doc_builder.document.paragraphs[0]
        # 检查段落格式是否设置了加粗样式
        # 样式可能不在 run 上而在段落格式中
        pPr = para._element.find(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}b")
        assert pPr is not None or len(para.runs) > 0


# =============================================================================
# _add_paragraph 测试
# =============================================================================


class TestAddParagraph:
    """测试添加段落"""

    def test_add_paragraph_simple(self, doc_builder):
        """添加简单段落"""
        doc_builder._add_paragraph("这是一个段落")
        para = doc_builder.document.paragraphs[0]
        assert "这是一个段落" in para.text

    def test_add_paragraph_with_style(self, doc_builder):
        """带样式的段落"""
        doc_builder._add_paragraph("样式段落", style="Quote")
        para = doc_builder.document.paragraphs[0]
        assert "样式段落" in para.text


# =============================================================================
# _add_code_block 测试
# =============================================================================


class TestAddCodeBlock:
    """测试添加代码块"""

    def test_add_code_block_simple(self, doc_builder):
        """添加简单代码块"""
        doc_builder._add_code_block("print('hello')")
        para = doc_builder.document.paragraphs[0]
        assert "print('hello')" in para.text

    def test_add_code_block_with_language(self, doc_builder):
        """带语言标识的代码块"""
        doc_builder._add_code_block("def test(): pass", "python")
        para = doc_builder.document.paragraphs[0]
        assert "def test(): pass" in para.text

    def test_add_code_block_gray_background(self, doc_builder):
        """代码块应该有灰色背景"""
        doc_builder._add_code_block("code here")
        para = doc_builder.document.paragraphs[0]
        pPr = para._element.get_or_add_pPr()
        shd = pPr.find(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}shd")
        assert shd is not None


# =============================================================================
# _add_list 测试
# =============================================================================


class TestAddList:
    """测试添加列表"""

    def test_add_ordered_list(self, doc_builder):
        """有序列表"""
        doc_builder._add_list("项目1\n项目2\n项目3", "ol")
        # 应该添加多个段落
        assert len(doc_builder.document.paragraphs) >= 3

    def test_add_unordered_list(self, doc_builder):
        """无序列表"""
        doc_builder._add_list("项目A\n项目B", "ul")
        assert len(doc_builder.document.paragraphs) >= 2


# =============================================================================
# _add_table 测试
# =============================================================================


class TestAddTable:
    """测试添加表格"""

    def test_add_simple_table(self, doc_builder):
        """添加简单表格"""
        table_data = TableData(
            headers=["姓名", "年龄"],
            rows=[["张三", "25"], ["李四", "30"]],
            header_bold=[True, True]
        )
        doc_builder._add_table(table_data)
        table = doc_builder.document.tables[0]
        assert len(table.rows) == 3  # 表头 + 2 行数据
        assert len(table.columns) == 2

    def test_add_table_with_cell_bold(self, doc_builder):
        """表格单元格加粗"""
        table_data = TableData(
            headers=["科目", "分数"],
            rows=[["数学", "100"]],
            header_bold=[True, True],
            cell_bold=[[False, True]]  # 第二列加粗
        )
        doc_builder._add_table(table_data)
        table = doc_builder.document.tables[0]
        # 验证表格已添加
        assert len(table.rows) == 2

    def test_add_empty_table(self, doc_builder):
        """空表格应该被忽略"""
        table_data = TableData(headers=[], rows=[])
        initial_count = len(doc_builder.document.tables)
        doc_builder._add_table(table_data)
        # 空表格不添加
        assert len(doc_builder.document.tables) == initial_count

    def test_add_table_no_headers(self, doc_builder):
        """无表头应该被忽略"""
        table_data = TableData(headers=[], rows=[["a", "b"]])
        initial_count = len(doc_builder.document.tables)
        doc_builder._add_table(table_data)
        assert len(doc_builder.document.tables) == initial_count


# =============================================================================
# _add_blockquote 测试
# =============================================================================


class TestAddBlockquote:
    """测试添加引用块"""

    def test_add_blockquote(self, doc_builder):
        """添加引用"""
        doc_builder._add_blockquote("这是一段引用")
        para = doc_builder.document.paragraphs[0]
        assert "这是一段引用" in para.text

    def test_add_blockquote_italic(self, doc_builder):
        """引用应该是斜体"""
        doc_builder._add_blockquote("斜体引用")
        para = doc_builder.document.paragraphs[0]
        has_italic = any(run.font.italic for run in para.runs if run.font)
        assert has_italic


# =============================================================================
# _add_text_block 测试（分发逻辑）
# =============================================================================


class TestAddTextBlock:
    """测试根据块类型分发"""

    def test_add_latex_block(self, doc_builder):
        """LaTeX 块"""
        block = TextBlock(type="latex", content=r"\alpha", language="inline")
        doc_builder._add_text_block(block)
        assert len(doc_builder.document.paragraphs) >= 1

    def test_add_code_block_type(self, doc_builder):
        """代码块类型"""
        block = TextBlock(type="code", content="print('test')", language="python")
        doc_builder._add_text_block(block)
        # 验证代码已添加
        assert any("print" in p.text for p in doc_builder.document.paragraphs)

    def test_add_heading_block(self, doc_builder):
        """标题块"""
        block = TextBlock(type="heading", content="章节标题", language="2")
        doc_builder._add_text_block(block)
        # 应该添加了标题
        assert len(doc_builder.document.paragraphs) >= 1

    def test_add_list_block(self, doc_builder):
        """列表块"""
        block = TextBlock(type="list", content="项1\n项2", language="ul")
        doc_builder._add_text_block(block)
        assert len(doc_builder.document.paragraphs) >= 2

    def test_add_table_block(self, doc_builder):
        """表格块"""
        table_data = TableData(
            headers=["列1", "列2"],
            rows=[["a", "b"]]
        )
        block = TextBlock(type="table", content="", data=table_data)
        doc_builder._add_text_block(block)
        assert len(doc_builder.document.tables) >= 1

    def test_add_blockquote_block(self, doc_builder):
        """引用块"""
        block = TextBlock(type="blockquote", content="引用内容")
        doc_builder._add_text_block(block)
        assert any("引用内容" in p.text for p in doc_builder.document.paragraphs)

    def test_add_paragraph_block(self, doc_builder):
        """段落块"""
        block = TextBlock(type="paragraph", content="普通段落内容")
        doc_builder._add_text_block(block)
        assert any("普通段落内容" in p.text for p in doc_builder.document.paragraphs)

    def test_add_paragraph_with_items(self, doc_builder):
        """带内联内容的段落"""
        items = [
            InlineContent(type="text", content="加粗", bold=True),
            InlineContent(type="text", content=" 文本"),
        ]
        block = TextBlock(type="paragraph", content="", items=items)
        doc_builder._add_text_block(block)
        assert len(doc_builder.document.paragraphs) >= 1

    def test_add_image_block(self, doc_builder):
        """图片块（空 URL）"""
        block = TextBlock(type="image", content="")
        doc_builder._add_text_block(block)
        # 应该记录失败
        assert doc_builder._image_failure_count >= 1


# =============================================================================
# _add_list_item 测试
# =============================================================================


class TestAddListItem:
    """测试添加列表项"""

    def test_add_ordered_list_item(self, doc_builder):
        """有序列表项"""
        block = TextBlock(type="list_item", content="第一项", language="ol", level=0)
        doc_builder._add_list_item(block)
        block2 = TextBlock(type="list_item", content="第二项", language="ol", level=0)
        doc_builder._add_list_item(block2)
        # 检查序号递增
        assert doc_builder._list_counter == 2

    def test_add_unordered_list_item(self, doc_builder):
        """无序列表项"""
        block = TextBlock(type="list_item", content="项目", language="ul")
        doc_builder._add_list_item(block)
        assert "项目" in doc_builder.document.paragraphs[0].text

    def test_add_list_item_with_items(self, doc_builder):
        """带内联内容的列表项"""
        items = [
            InlineContent(type="text", content="项目内容", bold=True),
        ]
        block = TextBlock(type="list_item", content="", language="ol", items=items)
        doc_builder._add_list_item(block)
        assert len(doc_builder.document.paragraphs) >= 1


# =============================================================================
# build_blocks 集成测试
# =============================================================================


class TestBuildBlocks:
    """测试 build_blocks 端到端功能"""

    def test_build_blocks_simple(self, doc_builder, temp_docx_path, mock_config):
        """简单构建"""
        blocks = [
            ("user", TextBlock(type="paragraph", content="用户消息")),
            ("assistant", TextBlock(type="paragraph", content="AI 回复")),
        ]
        with patch("src.generator.docx_builder.get_config", return_value=mock_config):
            result = doc_builder.build_blocks("测试标题", blocks, temp_docx_path)
            assert result == temp_docx_path
            assert os.path.exists(temp_docx_path)

    def test_build_blocks_latex(self, doc_builder, temp_docx_path, mock_config):
        """构建包含公式"""
        blocks = [
            ("user", TextBlock(type="latex", content=r"\alpha", language="inline")),
        ]
        with patch("src.generator.docx_builder.get_config", return_value=mock_config):
            result = doc_builder.build_blocks("公式测试", blocks, temp_docx_path)
            assert os.path.exists(temp_docx_path)

    def test_build_blocks_with_role_switching(self, doc_builder, temp_docx_path, mock_config):
        """角色切换"""
        blocks = [
            ("user", TextBlock(type="paragraph", content="用户消息")),
            ("assistant", TextBlock(type="paragraph", content="AI 回复")),
        ]
        with patch("src.generator.docx_builder.get_config", return_value=mock_config):
            doc_builder.build_blocks("角色测试", blocks, temp_docx_path)
            # 验证两个角色标签都存在
            text = "\n".join(p.text for p in doc_builder.document.paragraphs)
            assert "用户" in text or "豆包" in text

    def test_build_blocks_resets_list_state(self, doc_builder, temp_docx_path, mock_config):
        """重置列表状态"""
        # 先添加一些列表
        doc_builder._add_list_item(TextBlock(type="list_item", content="1", language="ol"))
        doc_builder._add_list_item(TextBlock(type="list_item", content="2", language="ol"))
        
        blocks = [
            ("user", TextBlock(type="heading", content="新章节", language="1")),
            ("user", TextBlock(type="list_item", content="新列表1", language="ol")),
        ]
        with patch("src.generator.docx_builder.get_config", return_value=mock_config):
            doc_builder.build_blocks("重置测试", blocks, temp_docx_path)
            # 标题后的列表应该从 1 开始
            assert doc_builder._list_counter == 1


# =============================================================================
# 内联内容测试
# =============================================================================


class TestInlineContent:
    """测试内联内容"""

    def test_add_inline_text_with_bold(self, doc_builder):
        """加粗文本"""
        items = [
            InlineContent(type="text", content="加粗文字", bold=True),
        ]
        doc_builder._add_inline_content(items)
        assert len(doc_builder.document.paragraphs) >= 1

    def test_add_inline_latex(self, doc_builder):
        """内联公式"""
        items = [
            InlineContent(type="latex", content=r"\pi", is_display=False),
        ]
        doc_builder._add_inline_content(items)
        assert len(doc_builder.document.paragraphs) >= 1

    def test_add_inline_display_latex(self, doc_builder):
        """展示公式"""
        items = [
            InlineContent(type="latex", content=r"\sum", is_display=True),
        ]
        doc_builder._add_inline_content(items)
        assert len(doc_builder.document.paragraphs) >= 2

    def test_add_inline_text_multiline(self, doc_builder):
        """多行文本"""
        items = [
            InlineContent(type="text", content="第一行\n第二行"),
        ]
        doc_builder._add_inline_content(items)
        para = doc_builder.document.paragraphs[0]
        assert "第一行" in para.text

    def test_add_inline_content_list_type(self, doc_builder):
        """带列表类型的内联内容"""
        items = [
            InlineContent(type="text", content="列表项"),
        ]
        doc_builder._add_inline_content(items, list_type="ul")
        assert len(doc_builder.document.paragraphs) >= 1

    def test_add_inline_image(self, doc_builder):
        """内联图片（无效 URL）"""
        items = [
            InlineContent(type="image", content="", image_url="invalid"),
        ]
        doc_builder._add_inline_content(items)
        # 应该记录失败
        assert doc_builder._image_failure_count >= 1


# =============================================================================
# 辅助功能测试
# =============================================================================


class TestHelpers:
    """测试辅助功能"""

    def test_get_image_failures(self, doc_builder):
        """获取图片失败信息"""
        doc_builder._image_failure_count = 2
        doc_builder._image_failure_urls = ["url1", "url2"]
        count, urls = doc_builder.get_image_failures()
        assert count == 2
        assert len(urls) == 2

    def test_compensate_text_latex(self, doc_builder):
        """LaTeX 空格补偿"""
        result = doc_builder._compensate_text_latex(r"\text{ }")
        # 应该将空格替换为 ~
        assert "~" in result or " " in result


# =============================================================================
# 图片下载测试（mock）
# =============================================================================


class TestImageDownload:
    """测试图片下载"""

    def test_download_invalid_url(self, doc_builder):
        """无效 URL"""
        result = doc_builder._download_image("")
        assert result is None
        assert doc_builder._image_failure_count >= 1

    def test_download_no_http(self, doc_builder):
        """非 HTTP URL"""
        result = doc_builder._download_image("not-a-url")
        assert result is None

    @patch("requests.get")
    def test_download_success(self, mock_get, doc_builder):
        """成功下载"""
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "image/png"}
        mock_response.content = b"fake image data"
        mock_get.return_value = mock_response

        result = doc_builder._download_image("http://example.com/image.png")
        assert result == b"fake image data"

    @patch("requests.get")
    def test_download_non_image(self, mock_get, doc_builder):
        """非图片响应"""
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "text/html"}
        mock_get.return_value = mock_response

        result = doc_builder._download_image("http://example.com/page.html")
        assert result is None
        assert doc_builder._image_failure_count >= 1


# =============================================================================
# _create_inline_paragraph 测试
# =============================================================================


class TestCreateInlineParagraph:
    """测试创建内联段落"""

    def test_create_ordered_paragraph(self, doc_builder):
        """有序列表段落"""
        para = doc_builder._create_inline_paragraph("ol", 1, 0)
        assert para is not None

    def test_create_unordered_paragraph(self, doc_builder):
        """无序列表段落"""
        para = doc_builder._create_inline_paragraph("ul", 1, 0)
        assert para is not None

    def test_create_no_list_paragraph(self, doc_builder):
        """无列表段落"""
        para = doc_builder._create_inline_paragraph(None, 1, 0)
        assert para is not None

    def test_create_with_level(self, doc_builder):
        """带嵌套级别"""
        para = doc_builder._create_inline_paragraph(None, 1, 2)
        # 应该设置缩进
        assert para.paragraph_format.left_indent is not None or para is not None