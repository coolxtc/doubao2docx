"""
测试豆包爬虫核心类
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch


class TestDoubaoSpiderInit:
    """测试爬虫初始化"""

    @pytest.fixture
    def mock_config(self):
        """Mock 配置"""
        mock = Mock()
        mock.crawler = Mock()
        mock.crawler.user_agents = ["Mozilla/5.0"]
        mock.crawler.page_load_timeout = 30000
        return mock

    def test_init_with_defaults(self, mock_config):
        """默认初始化"""
        with patch("src.scraper.crawler.get_config", return_value=mock_config):
            from src.scraper.crawler import DoubaoSpider
            spider = DoubaoSpider()
            assert spider.anti_detect_level == "medium"
            assert spider.tag == ""
            assert spider.progress_callback is None

    def test_init_with_custom_params(self, mock_config):
        """自定义参数初始化"""
        with patch("src.scraper.crawler.get_config", return_value=mock_config):
            from src.scraper.crawler import DoubaoSpider
            spider = DoubaoSpider(
                anti_detect_level="high",
                tag="test",
            )
            assert spider.anti_detect_level == "high"
            assert spider.tag == "test"

    def test_init_with_external_page(self, mock_config):
        """外部页面初始化"""
        with patch("src.scraper.crawler.get_config", return_value=mock_config):
            from src.scraper.crawler import DoubaoSpider
            external_page = AsyncMock()
            spider = DoubaoSpider(external_page=external_page)
            assert spider._external_page == external_page
            assert spider._owns_browser is False


class TestDoubaoSpiderURLValidation:
    """测试 URL 验证"""

    @pytest.fixture
    def mock_config(self):
        """Mock 配置"""
        mock = Mock()
        mock.crawler = Mock()
        mock.crawler.user_agents = []
        return mock

    def test_validate_valid_url(self, mock_config):
        """验证有效 URL"""
        with patch("src.scraper.crawler.get_config", return_value=mock_config):
            from src.scraper.crawler import DoubaoSpider
            spider = DoubaoSpider()
            assert spider._validate_url("https://www.doubao.com/thread/abc123") is True

    def test_validate_valid_url_http(self, mock_config):
        """验证有效 HTTP URL"""
        with patch("src.scraper.crawler.get_config", return_value=mock_config):
            from src.scraper.crawler import DoubaoSpider
            spider = DoubaoSpider()
            assert spider._validate_url("http://www.doubao.com/thread/abc123") is True

    def test_validate_invalid_url(self, mock_config):
        """验证无效 URL"""
        with patch("src.scraper.crawler.get_config", return_value=mock_config):
            from src.scraper.crawler import DoubaoSpider
            spider = DoubaoSpider()
            assert spider._validate_url("https://example.com/thread/abc123") is False
            assert spider._validate_url("not-a-url") is False


class TestDoubaoSpiderProgress:
    """测试进度回调"""

    @pytest.fixture
    def mock_config(self):
        """Mock 配置"""
        mock = Mock()
        mock.crawler = Mock()
        mock.crawler.user_agents = []
        return mock

    def test_report_progress_with_callback(self, mock_config):
        """带回调的报告进度"""
        with patch("src.scraper.crawler.get_config", return_value=mock_config):
            from src.scraper.crawler import DoubaoSpider
            callback = Mock()
            spider = DoubaoSpider(progress_callback=callback)
            spider._report_progress("加载中")
            callback.assert_called_once_with("加载中")

    def test_report_progress_without_callback(self, mock_config):
        """无回调的报告进度不应抛异常"""
        with patch("src.scraper.crawler.get_config", return_value=mock_config):
            from src.scraper.crawler import DoubaoSpider
            spider = DoubaoSpider()
            spider._report_progress("加载中")
            assert spider.progress_callback is None


class TestDoubaoSpiderAsync:
    """测试异步方法"""

    @pytest.fixture
    def mock_config(self):
        """Mock 配置"""
        mock = Mock()
        mock.crawler = Mock()
        mock.crawler.user_agents = []
        return mock

    @pytest.mark.asyncio
    async def test_start_with_external_page(self, mock_config):
        """外部页面的 start"""
        with patch("src.scraper.crawler.get_config", return_value=mock_config):
            from src.scraper.crawler import DoubaoSpider
            external_page = AsyncMock()
            spider = DoubaoSpider(external_page=external_page)
            await spider.start()
            assert spider.page_actions is not None
            assert spider.extractor is not None

    @pytest.mark.asyncio
    async def test_close_without_browser(self, mock_config):
        """关闭无浏览器实例"""
        with patch("src.scraper.crawler.get_config", return_value=mock_config):
            from src.scraper.crawler import DoubaoSpider
            spider = DoubaoSpider()
            await spider.close()


class TestDoubaoSpiderFetch:
    """测试爬取方法"""

    @pytest.fixture
    def mock_config(self):
        """Mock 配置"""
        mock = Mock()
        mock.crawler = Mock()
        mock.crawler.user_agents = []
        mock.crawler.page_load_timeout = 30000
        return mock

    @pytest.mark.asyncio
    async def test_fetch_invalid_url_raises(self, mock_config):
        """无效 URL 抛出异常"""
        with patch("src.scraper.crawler.get_config", return_value=mock_config):
            from src.scraper.crawler import DoubaoSpider
            spider = DoubaoSpider()
            with pytest.raises(Exception):
                await spider.fetch("not-a-valid-url")

    @pytest.mark.asyncio
    async def test_fetch_success_flow(self, mock_config):
        """
        测试成功爬取流程
        
        Mock BrowserManager, page, page_actions, extractor，
        验证成功返回 ChatData。
        """
        from src.scraper.crawler import DoubaoSpider
        from src.scraper.models import ChatData, ChatMessage
        
        with patch("src.scraper.crawler.get_config", return_value=mock_config):
            spider = DoubaoSpider()
            
            # Mock BrowserManager
            mock_browser_mgr = AsyncMock()
            mock_page = AsyncMock()
            mock_browser_mgr.new_page = AsyncMock(return_value=mock_page)
            mock_page.goto = AsyncMock()
            mock_page.url = "https://www.doubao.com/thread/abc123"
            mock_page.close = AsyncMock()
            spider.browser_mgr = mock_browser_mgr
            spider._owns_browser = True
            
            # Mock page_actions
            spider.page_actions = Mock()
            spider.page_actions.scroll_all = AsyncMock()
            
            # Mock extractor 返回 ChatData
            expected_data = ChatData(
                url="https://www.doubao.com/thread/abc123",
                title="测试标题",
                messages=[ChatMessage(role="user", content="你好")]
            )
            spider.extractor = Mock()
            spider.extractor.extract_all = AsyncMock(return_value=expected_data)
            
            # 执行爬取
            result = await spider.fetch("https://www.doubao.com/thread/abc123")
            
            # 验证结果
            assert isinstance(result, ChatData)
            assert result.url == "https://www.doubao.com/thread/abc123"
            assert result.title == "测试标题"
            # 验证 goto 被调用
            mock_page.goto.assert_called_once()
            # 验证页面关闭
            mock_page.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_external_page(self, mock_config):
        """
        测试外部页面模式
        
        传入 external_page 时，复用页面资源，但仍会 goto 到目标 URL。
        """
        from src.scraper.crawler import DoubaoSpider
        from src.scraper.models import ChatData
        
        with patch("src.scraper.crawler.get_config", return_value=mock_config):
            # 创建外部页面 mock
            external_page = AsyncMock()
            external_page.url = "https://www.doubao.com/thread/abc123"
            
            spider = DoubaoSpider(external_page=external_page)
            
            # Mock extractor
            expected_data = ChatData(url="https://www.doubao.com/thread/abc123", title="外部页面")
            spider.extractor = Mock()
            spider.extractor.extract_all = AsyncMock(return_value=expected_data)
            
            # Mock page_actions
            spider.page_actions = Mock()
            spider.page_actions.scroll_all = AsyncMock()
            
            # 执行爬取
            result = await spider.fetch("https://www.doubao.com/thread/abc123")
            
            # 验证使用外部页面，但仍会 goto 到目标 URL
            external_page.goto.assert_called_once()
            assert result.title == "外部页面"

    @pytest.mark.asyncio
    async def test_fetch_retry_on_crawler_error(self, mock_config):
        """
        测试 CrawlerError 触发重试
        
        Mock page.goto 抛出 CrawlerError，
        验证重试被触发（goto 被调用多次）。
        """
        from src.scraper.crawler import DoubaoSpider
        from src.exceptions import CrawlerError
        
        with patch("src.scraper.crawler.get_config", return_value=mock_config):
            spider = DoubaoSpider()
            
            # Mock BrowserManager
            mock_browser_mgr = AsyncMock()
            mock_page = AsyncMock()
            mock_browser_mgr.new_page = AsyncMock(return_value=mock_page)
            spider.browser_mgr = mock_browser_mgr
            spider._owns_browser = True
            
            # 第一次抛出 CrawlerError，第二次成功
            mock_page.goto = AsyncMock(side_effect=[
                CrawlerError("临时错误"),
                None  # 第二次成功
            ])
            mock_page.url = "https://www.doubao.com/thread/abc123"
            mock_page.wait_for_timeout = AsyncMock()
            mock_page.close = AsyncMock()
            
            # Mock page_actions
            spider.page_actions = Mock()
            spider.page_actions.scroll_all = AsyncMock()
            
            # Mock extractor
            from src.scraper.models import ChatData
            spider.extractor = Mock()
            spider.extractor.extract_all = AsyncMock(return_value=ChatData(url="https://www.doubao.com/thread/abc123"))
            
            # Mock sleep 避免实际等待
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await spider.fetch("https://www.doubao.com/thread/abc123", max_retries=3)
            
            # 验证重试：goto 被调用 2 次
            assert mock_page.goto.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_max_retries_exceeded(self, mock_config):
        """
        测试达到最大重试次数
        
        Mock page.goto 始终抛出 CrawlerError，
        验证最终抛出 CrawlerError。
        """
        from src.scraper.crawler import DoubaoSpider
        from src.exceptions import CrawlerError
        
        with patch("src.scraper.crawler.get_config", return_value=mock_config):
            spider = DoubaoSpider()
            
            # Mock BrowserManager
            mock_browser_mgr = AsyncMock()
            mock_page = AsyncMock()
            mock_browser_mgr.new_page = AsyncMock(return_value=mock_page)
            spider.browser_mgr = mock_browser_mgr
            spider._owns_browser = True
            
            # 始终抛出 CrawlerError
            mock_page.goto = AsyncMock(side_effect=CrawlerError("持续错误"))
            mock_page.wait_for_timeout = AsyncMock()
            
            spider.page_actions = Mock()
            spider.extractor = Mock()
            
            # Mock sleep 避免实际等待
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(CrawlerError):
                    await spider.fetch("https://www.doubao.com/thread/abc123", max_retries=3)
            
            # 验证重试 3 次
            assert mock_page.goto.call_count == 3

    @pytest.mark.asyncio
    async def test_fetch_login_page_redirect(self, mock_config):
        """
        测试登录页重定向检测
        
        Mock page.goto 返回重定向到登录页的 URL，
        验证抛出 CrawlerError。
        """
        from src.scraper.crawler import DoubaoSpider
        from src.exceptions import CrawlerError
        
        with patch("src.scraper.crawler.get_config", return_value=mock_config):
            spider = DoubaoSpider()
            
            # Mock BrowserManager
            mock_browser_mgr = AsyncMock()
            mock_page = AsyncMock()
            mock_browser_mgr.new_page = AsyncMock(return_value=mock_page)
            spider.browser_mgr = mock_browser_mgr
            spider._owns_browser = True
            
            # 模拟重定向到登录页
            mock_page.goto = AsyncMock()
            mock_page.url = "https://www.doubao.com/login"
            mock_page.close = AsyncMock()
            
            spider.page_actions = Mock()
            spider.extractor = Mock()
            
            # 验证抛出登录页错误
            with pytest.raises(CrawlerError) as exc_info:
                await spider.fetch("https://www.doubao.com/thread/abc123")
            
            assert "登录" in str(exc_info.value) or "重定向" in str(exc_info.value)


class TestDoubaoSpiderBrowserLifecycle:
    """测试浏览器生命周期管理"""

    @pytest.fixture
    def mock_config(self):
        """Mock 配置"""
        mock = Mock()
        mock.crawler = Mock()
        mock.crawler.user_agents = []
        mock.crawler.page_load_timeout = 30000
        return mock

    @pytest.mark.asyncio
    async def test_start_normal_browser(self, mock_config):
        """
        测试正常启动浏览器
        
        验证 BrowserManager 被创建和启动。
        """
        from src.scraper.crawler import DoubaoSpider
        from src.scraper.browser import BrowserManager
        
        with patch("src.scraper.crawler.get_config", return_value=mock_config):
            spider = DoubaoSpider()
            
            # Mock BrowserManager
            mock_browser_mgr = AsyncMock(spec=BrowserManager)
            with patch("src.scraper.crawler.BrowserManager", return_value=mock_browser_mgr):
                await spider.start()
            
            # 验证 BrowserManager 被创建
            assert spider.browser_mgr is not None
            # 验证 start 被调用
            mock_browser_mgr.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_with_browser(self, mock_config):
        """
        测试有浏览器时正确关闭
        
        先启动浏览器，再关闭，验证 close 被调用。
        """
        from src.scraper.crawler import DoubaoSpider
        from src.scraper.browser import BrowserManager
        
        with patch("src.scraper.crawler.get_config", return_value=mock_config):
            spider = DoubaoSpider()
            
            # Mock BrowserManager
            mock_browser_mgr = AsyncMock(spec=BrowserManager)
            with patch("src.scraper.crawler.BrowserManager", return_value=mock_browser_mgr):
                await spider.start()
                await spider.close()
            
            # 验证 close 被调用
            mock_browser_mgr.close.assert_called_once()
            # 验证 browser_mgr 被清空
            assert spider.browser_mgr is None


class TestDoubaoSpiderContextManager:
    """测试上下文管理器"""

    @pytest.fixture
    def mock_config(self):
        """Mock 配置"""
        mock = Mock()
        mock.crawler = Mock()
        mock.crawler.user_agents = []
        return mock

    @pytest.mark.asyncio
    async def test_aenter_returns_self(self, mock_config):
        """验证 __aenter__ 返回 self 并初始化组件"""
        from src.scraper.crawler import DoubaoSpider
        from src.scraper.browser import BrowserManager

        with patch("src.scraper.crawler.get_config", return_value=mock_config):
            spider = DoubaoSpider()

            # Mock BrowserManager 避免启动真实浏览器
            mock_browser_mgr = AsyncMock(spec=BrowserManager)
            with patch("src.scraper.crawler.BrowserManager", return_value=mock_browser_mgr):
                result = await spider.__aenter__()

                # 验证返回值是 spider 自身
                assert result is spider
                # 验证 page_actions 和 extractor 已初始化
                assert spider.page_actions is not None
                assert spider.extractor is not None
                # 验证 BrowserManager.start 被调用
                mock_browser_mgr.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_aexit_calls_close(self, mock_config):
        """验证 __aexit__ 调用 close()"""
        from src.scraper.crawler import DoubaoSpider

        with patch("src.scraper.crawler.get_config", return_value=mock_config):
            spider = DoubaoSpider()

            # Mock browser_mgr
            mock_browser_mgr = AsyncMock()
            spider.browser_mgr = mock_browser_mgr
            spider._owns_browser = True  # 确保 close() 会执行

            # 调用 __aexit__
            await spider.__aexit__(None, None, None)

            # 验证 close() 被调用
            mock_browser_mgr.close.assert_called_once()


class TestDoubaoSpiderPattern:
    """测试 URL 模式常量"""

    def test_url_pattern_is_valid_regex(self):
        """URL 模式是正则表达式"""
        from src.scraper.crawler import DoubaoSpider
        import re
        pattern = DoubaoSpider.DOUBAO_URL_PATTERN
        assert re.match(pattern, "https://www.doubao.com/thread/abc123")
        assert re.match(pattern, "http://doubao.com/thread/xyz-123")
        assert not re.match(pattern, "https://example.com/thread/123")