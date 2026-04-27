"""
测试页面交互操作

注意：需要 Mock Playwright Page 对象。
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch


class TestPageActionsConstants:
    """测试页面交互常量"""

    def test_scroll_to_top_js(self):
        """滚动到顶部 JS"""
        from src.scraper.page_actions import SCROLL_TO_TOP_JS
        assert "window.scrollTo" in SCROLL_TO_TOP_JS
        assert "0, 0" in SCROLL_TO_TOP_JS

    def test_scroll_to_bottom_js(self):
        """滚动到底部 JS"""
        from src.scraper.page_actions import SCROLL_TO_BOTTOM_JS
        assert "window.scrollTo" in SCROLL_TO_BOTTOM_JS
        assert "document.body.scrollHeight" in SCROLL_TO_BOTTOM_JS

    def test_scroll_images_js(self):
        """滚动图片 JS"""
        from src.scraper.page_actions import SCROLL_IMAGES_JS
        assert "picture img" in SCROLL_IMAGES_JS
        assert "scrollIntoView" in SCROLL_IMAGES_JS

    def test_click_expand_buttons_js(self):
        """点击展开按钮 JS"""
        from src.scraper.page_actions import CLICK_EXPAND_BUTTONS_JS
        assert "已生成代码" in CLICK_EXPAND_BUTTONS_JS

    def test_inject_expanded_code_js(self):
        """注入展开代码 JS"""
        from src.scraper.page_actions import INJECT_EXPANDED_CODE_JS
        assert "data-expanded-code" in INJECT_EXPANDED_CODE_JS


class TestPageActions:
    """测试 PageActions 类"""

    @pytest.fixture
    def mock_config(self):
        """Mock 配置"""
        mock = Mock()
        mock.scroll_wait_ms = 500
        return mock

    def test_init(self, mock_config):
        """初始化"""
        from src.scraper.page_actions import PageActions
        actions = PageActions(mock_config)
        assert actions.config == mock_config

    def test_init_default(self):
        """使用默认配置"""
        from src.scraper.page_actions import PageActions
        from src.config import CrawlerConfig
        config = CrawlerConfig(30000, 30000, 500, 0.25, [])
        actions = PageActions(config)
        assert actions.config.scroll_wait_ms == 500

    @pytest.mark.asyncio
    async def test_scroll_all_calls_evaluate(self, mock_config):
        """scroll_all 应调用多次 evaluate"""
        from src.scraper.page_actions import PageActions
        actions = PageActions(mock_config)

        page = AsyncMock()
        page.evaluate = AsyncMock()
        page.query_selector_all = AsyncMock(return_value=[])
        page.wait_for_timeout = AsyncMock()

        await actions.scroll_all(page)
        assert page.evaluate.call_count >= 4

    @pytest.mark.asyncio
    async def test_scroll_all_with_progress_callback(self, mock_config):
        """验证进度回调被正确调用"""
        from src.scraper.page_actions import PageActions
        actions = PageActions(mock_config)

        page = AsyncMock()
        page.evaluate = AsyncMock()
        page.query_selector_all = AsyncMock(return_value=[])
        page.wait_for_timeout = AsyncMock()

        callback = Mock()

        await actions.scroll_all(page, progress_callback=callback)

        # 验证调用次数
        assert callback.call_count == 2

        # 验证调用参数
        callback.assert_any_call("加载图片")
        callback.assert_any_call("展开代码")

    @pytest.mark.asyncio
    async def test_scroll_all_with_images(self, mock_config):
        """scroll_all 处理图片"""
        from src.scraper.page_actions import PageActions
        actions = PageActions(mock_config)

        page = AsyncMock()
        page.evaluate = AsyncMock()
        img = AsyncMock()
        img.scroll_into_view_if_needed = AsyncMock()
        page.query_selector_all = AsyncMock(return_value=[img])
        page.wait_for_timeout = AsyncMock()

        await actions.scroll_all(page)
        assert page.query_selector_all.called


class TestPageActionsEdgeCases:
    """边界情况和异常处理"""

    @pytest.fixture
    def mock_config(self):
        mock = Mock()
        mock.scroll_wait_ms = 500
        return mock

    @pytest.fixture
    def actions(self, mock_config):
        from src.scraper.page_actions import PageActions
        return PageActions(mock_config)

    @pytest.mark.asyncio
    async def test_scroll_all_empty_images(self, actions, mock_config):
        """空图片列表 - 不应抛出异常"""
        page = AsyncMock()
        page.evaluate = AsyncMock()
        page.query_selector_all = AsyncMock(return_value=[])
        page.wait_for_timeout = AsyncMock()

        await actions.scroll_all(page)
        assert page.evaluate.call_count >= 4

    @pytest.mark.asyncio
    async def test_scroll_all_no_callback(self, actions, mock_config):
        """progress_callback 为 None - 不应抛出异常"""
        page = AsyncMock()
        page.evaluate = AsyncMock()
        page.query_selector_all = AsyncMock(return_value=[])
        page.wait_for_timeout = AsyncMock()

        await actions.scroll_all(page, progress_callback=None)

    @pytest.mark.asyncio
    async def test_scroll_all_evaluate_exception(self, actions, mock_config):
        """evaluate 抛出异常 - 应向上传播"""
        page = AsyncMock()
        page.evaluate = AsyncMock(side_effect=Exception("JS error"))
        page.query_selector_all = AsyncMock(return_value=[])
        page.wait_for_timeout = AsyncMock()

        with pytest.raises(Exception):
            await actions.scroll_all(page)

    @pytest.mark.asyncio
    async def test_scroll_all_scroll_into_view_exception(self, actions, mock_config):
        """scroll_into_view_if_needed 异常 - 应向上传播"""
        page = AsyncMock()
        page.evaluate = AsyncMock()
        page.wait_for_timeout = AsyncMock()

        mock_img = AsyncMock()
        mock_img.scroll_into_view_if_needed = AsyncMock(side_effect=Exception("scroll error"))
        page.query_selector_all = AsyncMock(return_value=[mock_img])

        with pytest.raises(Exception):
            await actions.scroll_all(page)

    @pytest.mark.asyncio
    async def test_scroll_all_many_images(self, actions, mock_config):
        """大量图片 - 验证循环执行"""
        page = AsyncMock()
        page.evaluate = AsyncMock()
        page.wait_for_timeout = AsyncMock()

        mock_imgs = [AsyncMock() for _ in range(10)]
        page.query_selector_all = AsyncMock(return_value=mock_imgs)

        await actions.scroll_all(page)

        for img in mock_imgs:
            img.scroll_into_view_if_needed.assert_called()

    @pytest.mark.asyncio
    async def test_scroll_all_scroll_wait_ms_zero(self, mock_config):
        """scroll_wait_ms 为 0 - 仍调用 wait_for_timeout(0)"""
        from src.scraper.page_actions import PageActions
        config = Mock()
        config.scroll_wait_ms = 0
        actions = PageActions(config)
        page = AsyncMock()
        page.evaluate = AsyncMock()
        page.query_selector_all = AsyncMock(return_value=[])

        await actions.scroll_all(page)

        page.wait_for_timeout.assert_called()