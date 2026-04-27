"""
BrowserManager 单元测试

使用 mock 模拟 Playwright API，测试浏览器生命周期管理逻辑。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from typing import Any

from src.scraper.browser import BrowserManager


class TestBrowserManagerInit:
    """初始化测试"""

    def test_init_with_default_config(self):
        """默认配置初始化"""
        with patch("src.scraper.browser.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.crawler = MagicMock()
            mock_get_config.return_value = mock_config

            manager = BrowserManager()

            assert manager.anti_detect is not None
            assert manager.browser is None
            assert manager.context is None

    def test_init_with_custom_config(self):
        """自定义配置初始化"""
        with patch("src.scraper.browser.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.crawler = MagicMock()
            mock_get_config.return_value = mock_config

            custom_config = MagicMock()
            manager = BrowserManager(config=custom_config)

            assert manager.config is custom_config


class TestBrowserManagerStart:
    """启动测试"""

    @pytest.mark.asyncio
    async def test_start_success(self):
        """启动成功"""
        mock_playwright = MagicMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_async_playwright = AsyncMock()
        mock_async_playwright.start = AsyncMock(return_value=mock_playwright)

        mock_playwright.chromium = MagicMock()
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        with patch("src.scraper.browser.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.crawler = MagicMock()
            mock_get_config.return_value = mock_config

            with patch("playwright.async_api.async_playwright",
                    return_value=mock_async_playwright):

                manager = BrowserManager()
                await manager.start()

                assert manager.playwright is not None
                assert manager.browser is not None
                assert manager.context is not None

    @pytest.mark.asyncio
    async def test_start_browser_none(self):
        """浏览器启动失败"""
        mock_playwright = MagicMock()
        mock_async_playwright = AsyncMock()
        mock_async_playwright.start = AsyncMock(return_value=mock_playwright)

        mock_playwright.chromium = MagicMock()
        mock_playwright.chromium.launch = AsyncMock(return_value=None)

        with patch("src.scraper.browser.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.crawler = MagicMock()
            mock_get_config.return_value = mock_config

            with patch("playwright.async_api.async_playwright",
                    return_value=mock_async_playwright):

                manager = BrowserManager()

                with pytest.raises(RuntimeError, match="无法启动 Chromium 浏览器"):
                    await manager.start()


class TestBrowserManagerClose:
    """关闭测试"""

    @pytest.mark.asyncio
    async def test_close_all_resources(self):
        """关闭所有资源"""
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()

        with patch("src.scraper.browser.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.crawler = MagicMock()
            mock_get_config.return_value = mock_config

            manager = BrowserManager()
            manager.playwright = mock_playwright
            manager.browser = mock_browser
            manager.context = mock_context

            await manager.close()

            mock_context.close.assert_called_once()
            mock_browser.close.assert_called_once()
            mock_playwright.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_close_error_handling(self):
        """上下文关闭异常处理"""
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_context.close.side_effect = Exception("context error")

        with patch("src.scraper.browser.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.crawler = MagicMock()
            mock_get_config.return_value = mock_config

            manager = BrowserManager()
            manager.playwright = mock_playwright
            manager.browser = mock_browser
            manager.context = mock_context

            # 不应抛出异常
            await manager.close()

    @pytest.mark.asyncio
    async def test_browser_close_error_handling(self):
        """浏览器关闭异常处理"""
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_browser.close.side_effect = Exception("browser error")

        mock_context = AsyncMock()

        with patch("src.scraper.browser.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.crawler = MagicMock()
            mock_get_config.return_value = mock_config

            manager = BrowserManager()
            manager.playwright = mock_playwright
            manager.browser = mock_browser
            manager.context = mock_context

            # 不应抛出异常
            await manager.close()

    @pytest.mark.asyncio
    async def test_playwright_stop_error_handling(self):
        """Playwright 停止异常处理"""
        mock_playwright = AsyncMock()
        mock_playwright.stop.side_effect = Exception("playwright error")

        mock_browser = AsyncMock()
        mock_context = AsyncMock()

        with patch("src.scraper.browser.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.crawler = MagicMock()
            mock_get_config.return_value = mock_config

            manager = BrowserManager()
            manager.playwright = mock_playwright
            manager.browser = mock_browser
            manager.context = mock_context

            # 不应抛出异常
            await manager.close()


class TestBrowserManagerNewPage:
    """创建页面测试"""

    @pytest.mark.asyncio
    async def test_new_page_success(self):
        """创建页面成功"""
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_context.new_page.return_value = mock_page

        with patch("src.scraper.browser.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.crawler = MagicMock()
            mock_get_config.return_value = mock_config

            manager = BrowserManager()
            manager.context = mock_context

            page = await manager.new_page()

            assert page is mock_page
            mock_context.new_page.assert_called_once()

    @pytest.mark.asyncio
    async def test_new_page_no_context(self):
        """无上下文异常"""
        with patch("src.scraper.browser.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.crawler = MagicMock()
            mock_get_config.return_value = mock_config

            manager = BrowserManager()
            manager.context = None

            with pytest.raises(RuntimeError, match="Browser context not initialized"):
                await manager.new_page()


class TestBrowserManagerContextManager:
    """异步上下文管理器协议测试"""

    @pytest.mark.asyncio
    async def test_async_context_manager_protocol(self):
        """异步上下文管理器协议"""
        mock_playwright = MagicMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_async_playwright = AsyncMock()
        mock_async_playwright.start = AsyncMock(return_value=mock_playwright)

        mock_playwright.chromium = MagicMock()
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        with patch("src.scraper.browser.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.crawler = MagicMock()
            mock_get_config.return_value = mock_config

            with patch("playwright.async_api.async_playwright",
                    return_value=mock_async_playwright):

                async with BrowserManager() as manager:
                    assert manager.browser is not None
                    assert manager.context is not None

                mock_context.close.assert_called()
                mock_browser.close.assert_called()
                mock_playwright.stop.assert_called()