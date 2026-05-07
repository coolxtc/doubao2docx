"""BrowserPool 单元测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.scraper.pool import BrowserPool, PooledPage


class TestPooledPageDataclass:
    """PooledPage 数据类测试"""

    def test_default_values(self):
        """默认值"""
        page = PooledPage()

        assert page.page is None
        assert page.in_use is False


class TestBrowserPoolInit:
    """初始化测试"""

    def test_init_default_values(self):
        """默认值"""
        with patch("src.scraper.pool.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.crawler = MagicMock()
            mock_get_config.return_value = mock_config

            pool = BrowserPool()

            assert pool._anti_detect_level == "medium"
            assert pool._manager is None
            assert pool._closed is False
            assert pool._semaphore is None

    def test_init_with_custom_config(self):
        """自定义配置"""
        mock_config = MagicMock()
        mock_config.crawler = MagicMock()

        with patch("src.scraper.pool.get_config") as mock_get_config:
            mock_get_config.return_value = mock_config

            custom_config = MagicMock()
            pool = BrowserPool(anti_detect_level="high", config=custom_config)

            assert pool._anti_detect_level == "high"
            assert pool._config is custom_config


class TestBrowserPoolInitialize:
    """初始化池测试"""

    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """初始化成功"""
        mock_manager = AsyncMock()
        mock_browser = AsyncMock()
        mock_manager.browser = mock_browser

        with patch("src.scraper.pool.get_config") as mock_get_config, \
             patch("src.scraper.pool.BrowserManager", return_value=mock_manager):

            mock_config = MagicMock()
            mock_config.crawler = MagicMock()
            mock_get_config.return_value = mock_config

            pool = BrowserPool()
            await pool.initialize()

            assert pool._manager is not None

    @pytest.mark.asyncio
    async def test_initialize_after_close(self):
        """关闭后初始化异常"""
        with patch("src.scraper.pool.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.crawler = MagicMock()
            mock_get_config.return_value = mock_config

            pool = BrowserPool()
            pool._closed = True

            with pytest.raises(RuntimeError, match="浏览器池已关闭"):
                await pool.initialize()


class TestBrowserPoolAcquire:
    """获取页面测试"""

    @pytest.mark.asyncio
    async def test_acquire_success(self):
        """获取页面成功"""
        mock_manager = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_semaphore = AsyncMock()

        mock_manager.context = mock_context
        mock_context.new_page.return_value = mock_page

        mock_config = MagicMock()
        mock_config.crawler = MagicMock()

        with patch("src.scraper.pool.get_config") as mock_get_config:
            mock_get_config.return_value = mock_config

            pool = BrowserPool()
            pool._manager = mock_manager
            pool._semaphore = mock_semaphore

            page = await pool.acquire(concurrency=3)

            assert page is mock_page

    @pytest.mark.asyncio
    async def test_acquire_after_close(self):
        """关闭后获取异常"""
        mock_config = MagicMock()
        mock_config.crawler = MagicMock()

        with patch("src.scraper.pool.get_config") as mock_get_config:
            mock_get_config.return_value = mock_config

            pool = BrowserPool()
            pool._closed = True

            with pytest.raises(RuntimeError, match="浏览器池已关闭"):
                await pool.acquire()

    @pytest.mark.asyncio
    async def test_acquire_no_manager(self):
        """未初始化异常"""
        mock_config = MagicMock()
        mock_config.crawler = MagicMock()

        with patch("src.scraper.pool.get_config") as mock_get_config:
            mock_get_config.return_value = mock_config

            pool = BrowserPool()
            pool._manager = None
            pool._closed = False

            with pytest.raises(RuntimeError, match="浏览器上下文未初始化"):
                await pool.acquire()


class TestBrowserPoolRelease:
    """归还页面测试"""

    @pytest.mark.asyncio
    async def test_release_success(self):
        """归还页面"""
        mock_page = AsyncMock()
        mock_semaphore = MagicMock()

        mock_config = MagicMock()
        mock_config.crawler = MagicMock()

        with patch("src.scraper.pool.get_config") as mock_get_config:
            mock_get_config.return_value = mock_config

            pool = BrowserPool()
            pool._semaphore = mock_semaphore

            await pool.release(mock_page)

            mock_page.close.assert_called_once()
            mock_semaphore.release.assert_called_once()

    @pytest.mark.asyncio
    async def test_release_with_page_close_error(self):
        """页面关闭异常处理"""
        mock_page = AsyncMock()
        mock_page.close.side_effect = Exception("close error")
        mock_semaphore = MagicMock()

        mock_config = MagicMock()
        mock_config.crawler = MagicMock()

        with patch("src.scraper.pool.get_config") as mock_get_config:
            mock_get_config.return_value = mock_config

            pool = BrowserPool()
            pool._semaphore = mock_semaphore

            await pool.release(mock_page)

            mock_semaphore.release.assert_called_once()

    @pytest.mark.asyncio
    async def test_release_none_page(self):
        """归还空页面"""
        mock_semaphore = MagicMock()

        mock_config = MagicMock()
        mock_config.crawler = MagicMock()

        with patch("src.scraper.pool.get_config") as mock_get_config:
            mock_get_config.return_value = mock_config

            pool = BrowserPool()
            pool._semaphore = mock_semaphore

            await pool.release(None)

            mock_semaphore.release.assert_called_once()


class TestBrowserPoolClose:
    """关闭池测试"""

    @pytest.mark.asyncio
    async def test_close_success(self):
        """关闭成功"""
        mock_manager = AsyncMock()

        mock_config = MagicMock()
        mock_config.crawler = MagicMock()

        with patch("src.scraper.pool.get_config") as mock_get_config:
            mock_get_config.return_value = mock_config

            pool = BrowserPool()
            pool._manager = mock_manager
            pool._closed = False

            await pool.close()

            mock_manager.close.assert_called_once()
            assert pool._manager is None
            assert pool._closed is True

    @pytest.mark.asyncio
    async def test_close_already_closed(self):
        """重复关闭"""
        mock_config = MagicMock()
        mock_config.crawler = MagicMock()

        with patch("src.scraper.pool.get_config") as mock_get_config:
            mock_get_config.return_value = mock_config

            pool = BrowserPool()
            pool._closed = True

            await pool.close()

            assert pool._closed is True


class TestBrowserPoolIsInitialized:
    """初始化状态属性测试"""

    def test_is_initialized_true(self):
        """已初始化"""
        mock_manager = AsyncMock()
        mock_config = MagicMock()
        mock_config.crawler = MagicMock()

        with patch("src.scraper.pool.get_config") as mock_get_config:
            mock_get_config.return_value = mock_config

            pool = BrowserPool()
            pool._manager = mock_manager
            pool._closed = False

            assert pool.is_initialized is True

    def test_is_initialized_no_manager(self):
        """无管理器"""
        mock_config = MagicMock()
        mock_config.crawler = MagicMock()

        with patch("src.scraper.pool.get_config") as mock_get_config:
            mock_get_config.return_value = mock_config

            pool = BrowserPool()
            pool._manager = None
            pool._closed = False

            assert pool.is_initialized is False

    def test_is_initialized_closed(self):
        """已关闭"""
        mock_config = MagicMock()
        mock_config.crawler = MagicMock()

        with patch("src.scraper.pool.get_config") as mock_get_config:
            mock_get_config.return_value = mock_config

            pool = BrowserPool()
            pool._manager = AsyncMock()
            pool._closed = True

            assert pool.is_initialized is False


class TestBrowserPoolSemaphore:
    """信号量测试"""

    @pytest.mark.asyncio
    async def test_lazy_semaphore_creation(self):
        """懒创建信号量"""
        mock_manager = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_semaphore = AsyncMock()

        mock_manager.context = mock_context
        mock_context.new_page.return_value = mock_page

        mock_config = MagicMock()
        mock_config.crawler = MagicMock()

        with patch("src.scraper.pool.get_config") as mock_get_config, \
             patch("src.scraper.pool.asyncio.Semaphore", return_value=mock_semaphore):
            mock_get_config.return_value = mock_config

            pool = BrowserPool()
            pool._manager = mock_manager

            page = await pool.acquire(concurrency=5)

            assert pool._semaphore is not None
            assert page is mock_page