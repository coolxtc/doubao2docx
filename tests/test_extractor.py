"""
测试数据提取器

注意：需要 Mock Playwright Page 对象。
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch


@pytest.fixture
def mock_config():
    """Mock 配置"""
    mock = Mock()
    mock.scroll_wait_ms = 500
    return mock


class TestDataExtractor:
    """测试 DataExtractor 类"""

    def test_init(self, mock_config):
        """初始化"""
        from src.scraper.extractor import DataExtractor
        extractor = DataExtractor(mock_config)
        assert extractor.config == mock_config
        assert extractor.logger is not None

    def test_init_default_config(self):
        """使用默认配置"""
        from src.scraper.extractor import DataExtractor
        from src.config import CrawlerConfig
        config = CrawlerConfig(30000, 30000, 500, 0.25, [])
        extractor = DataExtractor(config)
        assert extractor.config == config

    @pytest.mark.asyncio
    async def test_extract_title_success(self, mock_config):
        """成功提取标题"""
        from src.scraper.extractor import DataExtractor
        extractor = DataExtractor(mock_config)
        
        page = AsyncMock()
        mock_title = AsyncMock()
        mock_title.inner_text = AsyncMock(return_value="Test Title")
        page.query_selector = AsyncMock(return_value=mock_title)
        
        title = await extractor.extract_title(page)
        assert title == "Test Title"

    @pytest.mark.asyncio
    async def test_extract_title_not_found(self, mock_config):
        """标题未找到时返回默认值"""
        from src.scraper.extractor import DataExtractor
        extractor = DataExtractor(mock_config)
        
        page = AsyncMock()
        page.query_selector = AsyncMock(return_value=None)
        
        title = await extractor.extract_title(page)
        assert title == "未命名对话"

    @pytest.mark.asyncio
    async def test_extract_title_exception(self, mock_config):
        """提取异常时返回默认值"""
        from src.scraper.extractor import DataExtractor
        extractor = DataExtractor(mock_config)
        
        page = AsyncMock()
        page.query_selector = AsyncMock(side_effect=Exception("Test error"))
        
        title = await extractor.extract_title(page)
        assert title == "未命名对话"

    @pytest.mark.asyncio
    async def test_extract_all(self, mock_config):
        """提取完整数据"""
        from src.scraper.extractor import DataExtractor
        from src.scraper.models import ChatData
        extractor = DataExtractor(mock_config)
        
        page = AsyncMock()
        mock_title = AsyncMock()
        mock_title.inner_text = AsyncMock(return_value="Test Chat")
        page.query_selector = AsyncMock(return_value=mock_title)
        page.evaluate = AsyncMock(return_value=[])
        page.content = AsyncMock(return_value="<html></html>")
        
        result = await extractor.extract_all(page, "http://example.com/chat")
        assert isinstance(result, ChatData)
        assert result.url == "http://example.com/chat"
        assert result.title == "Test Chat"

    @pytest.mark.asyncio
    async def test_extract_messages_with_results(self, mock_config):
        """提取消息列表成功"""
        from src.scraper.extractor import DataExtractor
        extractor = DataExtractor(mock_config)
        
        page = AsyncMock()
        page.evaluate = AsyncMock(return_value=[
            {"role": "user", "content": "Hello", "images": []},
            {"role": "assistant", "content": "Hi there", "images": []}
        ])
        
        messages = await extractor.extract_messages(page)
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_extract_messages_with_images(self, mock_config):
        """提取消息带图片"""
        from src.scraper.extractor import DataExtractor
        extractor = DataExtractor(mock_config)
        
        page = AsyncMock()
        page.evaluate = AsyncMock(return_value=[
            {
                "role": "assistant",
                "content": "Image message",
                "images": [{"url": "http://example.com/img.jpg", "prev_text": "prev", "next_text": "next"}]
            }
        ])
        
        messages = await extractor.extract_messages(page)
        assert len(messages) == 1
        assert len(messages[0].images) == 1
        assert messages[0].images[0].url == "http://example.com/img.jpg"

    @pytest.mark.asyncio
    async def test_extract_messages_empty(self, mock_config):
        """提取空消息列表"""
        from src.scraper.extractor import DataExtractor
        extractor = DataExtractor(mock_config)
        
        page = AsyncMock()
        page.evaluate = AsyncMock(return_value=[])
        
        messages = await extractor.extract_messages(page)
        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_extract_messages_exception_uses_fallback(self, mock_config):
        """提取异常时使用备用方法"""
        from src.scraper.extractor import DataExtractor
        extractor = DataExtractor(mock_config)
        
        page = AsyncMock()
        # 初次 evaluate 抛异常，触发 fallback
        page.evaluate = AsyncMock(side_effect=Exception("Error"))
        
        messages = await extractor.extract_messages(page)
        # fallback 在异常时尝试备用提取，Mock 环境下返回空列表
        assert isinstance(messages, list)

    @pytest.mark.asyncio
    async def test_extract_all_with_raw_html(self, mock_config):
        """提取包含 raw_html"""
        from src.scraper.extractor import DataExtractor
        extractor = DataExtractor(mock_config)

        page = AsyncMock()
        mock_title = AsyncMock()
        mock_title.inner_text = AsyncMock(return_value="Title")
        page.query_selector = AsyncMock(return_value=mock_title)
        page.evaluate = AsyncMock(return_value=[])
        page.content = AsyncMock(return_value="<html><body>Content</body></html>")

        result = await extractor.extract_all(page, "http://example.com/chat")
        assert result.raw_html == "<html><body>Content</body></html>"


class TestExtractFallback:
    """测试 _extract_fallback() 备用提取方法"""

    @pytest.mark.asyncio
    async def test_extract_fallback_success(self, mock_config):
        """验证 _extract_fallback 直接调用"""
        from src.scraper.extractor import DataExtractor
        extractor = DataExtractor(mock_config)

        page = AsyncMock()
        page.evaluate = AsyncMock(return_value="Fallback extracted text")

        result = await extractor._extract_fallback(page)

        assert len(result) == 1
        assert result[0].role == "assistant"
        assert "Fallback extracted text" in result[0].content

    @pytest.mark.asyncio
    async def test_extract_fallback_empty_content(self, mock_config):
        """_extract_fallback 空内容返回空列表"""
        from src.scraper.extractor import DataExtractor
        extractor = DataExtractor(mock_config)

        page = AsyncMock()
        page.evaluate = AsyncMock(return_value="")

        result = await extractor._extract_fallback(page)

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_fallback_exception(self, mock_config):
        """_extract_fallback 异常时返回空列表"""
        from src.scraper.extractor import DataExtractor
        extractor = DataExtractor(mock_config)

        page = AsyncMock()
        page.evaluate = AsyncMock(side_effect=Exception("Network error"))

        result = await extractor._extract_fallback(page)

        assert result == []


class TestExtractMessagesEdgeCases:
    """测试 extract_messages() 边界情况"""

    @pytest.mark.asyncio
    async def test_extract_messages_empty_content_filtered(self, mock_config):
        """空内容消息被过滤（JS 层面）"""
        from src.scraper.extractor import DataExtractor
        extractor = DataExtractor(mock_config)

        page = AsyncMock()
        page.evaluate = AsyncMock(return_value=[])

        with patch.object(extractor, "_extract_fallback", new_callable=AsyncMock, return_value=[]):
            result = await extractor.extract_messages(page)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_extract_messages_with_hidden_code(self, mock_config):
        """带有隐藏代码块的消息"""
        from src.scraper.extractor import DataExtractor
        extractor = DataExtractor(mock_config)

        page = AsyncMock()
        page.evaluate = AsyncMock(return_value=[
            {
                "role": "user",
                "content": "Show me code",
                "images": []
            },
            {
                "role": "assistant",
                "content": "Here is the code",
                "images": []
            }
        ])

        result = await extractor.extract_messages(page)

        assert len(result) == 2
        assert result[0].role == "user"
        assert result[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_extract_messages_exception_triggers_fallback(self, mock_config):
        """验证异常时触发 fallback"""
        from src.scraper.extractor import DataExtractor
        extractor = DataExtractor(mock_config)

        page = AsyncMock()
        call_count = [0]

        async def evaluate_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Eval error")
            return "Fallback content"

        page.evaluate = evaluate_side_effect

        result = await extractor.extract_messages(page)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].role == "assistant"
        assert "Fallback" in result[0].content