"""
浏览器池模块

提供浏览器实例的复用机制，减少批量导出时的浏览器启动开销。

采用单浏览器多标签页模式：
- 只启动 1 个浏览器进程
- 每个任务使用独立的标签页 (page)
- 任务完成后关闭标签页，浏览器进程复用
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..config import CrawlerConfig, get_config
from .browser import BrowserManager

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)


@dataclass
class PooledPage:
    page: "Page | None" = None
    in_use: bool = False


class BrowserPool:
    """
    浏览器池（单浏览器多标签页模式）

    管理一个预热的浏览器实例，通过标签页实现并发。

    使用方式：
    1. 创建池实例并初始化
    2. 调用 acquire() 获取页面
    3. 执行任务
    4. 调用 release() 归还页面
    5. 任务完成后调用 close() 关闭池
    """

    def __init__(
        self,
        anti_detect_level: str = "medium",
        config: CrawlerConfig | None = None,
    ) -> None:
        self._anti_detect_level: str = anti_detect_level
        self._config: CrawlerConfig = config or get_config().crawler
        self._manager: BrowserManager | None = None
        self._closed: bool = False
        self._semaphore: asyncio.Semaphore | None = None

    async def initialize(self) -> None:
        """初始化池：启动浏览器实例"""
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
        从池中获取一个页面

        Args:
            concurrency: 允许的最大并发数（控制信号量大小）

        Returns:
            Page: 可用的页面
        """
        if self._closed:
            raise RuntimeError("浏览器池已关闭，无法获取资源")

        if self._manager is None or self._manager.browser is None:
            raise RuntimeError("浏览器未初始化")

        # 懒创建信号量
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(concurrency)

        await self._semaphore.acquire()

        try:
            page = await self._manager.browser.new_page()
            return page
        except Exception as e:
            self._semaphore.release()
            raise e

    async def release(self, page: "Page | None") -> None:
        """
        归还页面到池中（关闭标签页）

        Args:
            page: 待关闭的页面
        """
        if self._semaphore is not None:
            self._semaphore.release()

        if page is not None:
            try:
                await page.close()
            except Exception as e:
                logger.debug(f"关闭页面时出错: {e}")

    async def close(self) -> None:
        """关闭池：清理浏览器资源"""
        if self._closed:
            return

        self._closed = True
        logger.info("正在关闭浏览器池...")

        if self._manager is not None:
            await self._manager.close()
            self._manager = None

        logger.info("浏览器池已关闭")

    @property
    def is_initialized(self) -> bool:
        """池是否已初始化"""
        return self._manager is not None and not self._closed
