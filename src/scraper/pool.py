"""浏览器池（单浏览器多标签页模式）"""

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..config import CrawlerConfig, get_config
from .browser import BrowserManager

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)


@dataclass
class PooledPage:
    """池化页面对象"""
    page: "Page | None" = None  # Playwright 页面
    in_use: bool = False  # 是否正在使用


class BrowserPool:
    """
    浏览器池

    单浏览器多标签页模式，支持异步上下文管理器协议。
    """

    def __init__(
        self,
        anti_detect_level: str = "medium",
        config: CrawlerConfig | None = None,
    ) -> None:
        self._anti_detect_level: str = anti_detect_level
        self._config: CrawlerConfig = config or get_config().crawler  # 爬虫配置
        self._manager: BrowserManager | None = None  # 浏览器管理器
        self._closed: bool = False  # 池是否已关闭
        self._semaphore: asyncio.Semaphore | None = None  # 并发控制信号量

    async def initialize(self) -> None:
        """
        初始化浏览器池

        Raises:
            RuntimeError: 池已关闭
        """
        if self._closed:
            raise RuntimeError("浏览器池已关闭，无法初始化")

        logger.info("正在初始化浏览器池...")
        self._manager = BrowserManager(
            anti_detect_level=self._anti_detect_level,
            config=self._config,
        )
        await self._manager.start()
        logger.info("浏览器池初始化完成")

    async def acquire(self, concurrency: int = 5) -> "Page":
        """
        获取页面

        Args:
            concurrency: 允许的最大并发数

        Returns:
            Page: 可用的页面

        Raises:
            RuntimeError: 池已关闭或浏览器未初始化
        """
        # 池已关闭
        if self._closed:
            raise RuntimeError("浏览器池已关闭，无法获取资源")

        # 浏览器未初始化
        if self._manager is None or self._manager.context is None:
            raise RuntimeError("浏览器上下文未初始化")

        # 懒创建信号量
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(concurrency)

        await self._semaphore.acquire()

        try:
            page = await self._manager.context.new_page()
            return page
        except Exception as e:
            self._semaphore.release()
            raise e

    async def release(self, page: "Page | None") -> None:
        """
        归还页面（关闭标签页）

        Args:
            page: 待关闭的页面
        """
        # 释放信号量占用
        if self._semaphore is not None:
            self._semaphore.release()

        # 关闭页面
        if page is not None:
            try:
                await page.close()
            except Exception as e:
                logger.debug(f"关闭页面时出错: {e}")

    @asynccontextmanager
    async def page_context(self, concurrency: int = 5):
        """
        异步上下文管理器：安全获取/归还页面

        确保异常时也能正确释放信号量和关闭页面。

        Args:
            concurrency: 允许的最大并发数

        Yields:
            Page: 可用的页面

        Example:
            async with pool.page_context(5) as page:
                await page.goto(url)
        """
        page = await self.acquire(concurrency)
        try:
            yield page
        finally:
            await self.release(page)

    async def close(self) -> None:
        """关闭池并清理资源"""
        # 池已关闭，直接返回
        if self._closed:
            return

        self._closed = True
        logger.info("正在关闭浏览器池...")

        # 关闭浏览器管理器
        if self._manager is not None:
            await self._manager.close()
            self._manager = None

        logger.info("浏览器池已关闭")

    @property
    def is_initialized(self) -> bool:
        """池是否已初始化"""
        return self._manager is not None and not self._closed
