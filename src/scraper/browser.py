"""浏览器生命周期管理"""

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

from ..config import CrawlerConfig
from ..utils import is_windows, windows_compat_close
from .anti_detect import create_anti_detect_middleware

if TYPE_CHECKING:
    from playwright.async_api import async_playwright, Browser, BrowserContext

logger = logging.getLogger(__name__)


class BrowserManager:
    """浏览器生命周期管理器
    
    负责浏览器的启动、关闭等生命周期操作。
    支持 async with 语法，自动管理资源清理。
    """

    def __init__(
        self,
        anti_detect_level: str = "medium",
        config: Optional[CrawlerConfig] = None,
    ) -> None:
        self.config = config or CrawlerConfig()
        self.anti_detect = create_anti_detect_middleware(anti_detect_level)
        self.browser: Optional["Browser"] = None
        self.context: Optional["BrowserContext"] = None
        self.playwright: Optional["async_playwright"] = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def start(self) -> None:
        """启动浏览器并创建浏览器上下文"""
        from playwright.async_api import async_playwright

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context()
        await self.anti_detect.apply(self.context)

    async def close(self) -> None:
        try:
            if self.context:
                await self.context.close()
        except Exception as e:
            logger.debug(f"关闭浏览器上下文时出错: {e}")

        try:
            if self.browser:
                await self.browser.close()
        except Exception as e:
            logger.debug(f"关闭浏览器时出错: {e}")

        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.debug(f"停止 Playwright 时出错: {e}")

        if is_windows():
            await windows_compat_close(self.config.browser_close_delay)

    async def new_page(self):
        """创建新页面"""
        if not self.context:
            raise RuntimeError("Browser context not initialized")
        return await self.context.new_page()