"""
浏览器生命周期管理

本模块负责管理 Playwright 浏览器的启动、关闭等生命周期操作。

为什么需要这个模块？
在自动化爬取场景中，需要手动管理浏览器的启动和关闭。
手动管理容易遗漏关闭操作导致资源泄漏，使用 async with 语法
可以确保浏览器在使用完毕后正确关闭，释放系统资源。

主要功能：
1. BrowserManager: 浏览器生命周期管理器，支持 async with 语法自动管理资源
2. 启动浏览器并创建独立的浏览器上下文
3. 应用反爬措施到浏览器上下文
"""

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
    """
    浏览器生命周期管理器

    负责浏览器的启动、关闭等生命周期操作。
    支持 async with 语法，自动管理资源清理。

    使用方式：
        async with BrowserManager(anti_detect_level="medium") as browser:
            page = await browser.new_page()
            # ... 使用浏览器

    为什么需要 async with？
    - 确保浏览器在使用完毕后一定被关闭
    - 即便在发生异常的情况下也能正确释放资源
    - 避免手动调用 close() 导致资源泄漏
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
        """
        异步上下文管理器入口

        使用 async with 语法时自动调用此方法，等价于调用 start() 方法。
        进入上下文时启动浏览器，为后续操作做好准备。
        """
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        异步上下文管理器退出

        使用 async with 语法退出时自动调用此方法。
        等价于调用 close() 方法，确保浏览器资源被正确释放。

        Args:
            exc_type: 异常类型（如果有）
            exc_val: 异常值（如果有）
            exc_tb: 异常回溯（如果有）

        为什么要捕获异常还要关闭？
        - 即使爬取过程中发生异常，也要确保浏览器被关闭
        - 否则浏览器进程会一直占用系统资源
        """
        await self.close()

    async def start(self) -> None:
        """
        启动浏览器并创建浏览器上下文

        执行以下操作：
        1. 启动 Playwright 引擎
        2. 启动 Chromium 浏览器（无头模式）
        3. 创建独立的浏览器上下文
        4. 应用反爬措施到上下文
        """
        from playwright.async_api import async_playwright

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context()
        await self.anti_detect.apply(self.context)

    async def close(self) -> None:
        """
        关闭浏览器并释放资源

        按顺序执行以下操作：
        1. 关闭浏览器上下文（清除 Cookie、LocalStorage 等）
        2. 关闭浏览器进程
        3. 停止 Playwright 引擎
        4. Windows 平台执行兼容性清理

        为什么分步关闭？
        - 优雅关闭：按启动的相反顺序关闭，确保资源正确释放
        - 容错处理：每个关闭操作都捕获异常，避免一个失败影响其他
        """
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
        """
        创建新页面

        在浏览器上下文中创建一个新的页面标签。

        Returns:
            Page 对象，可以进行导航、点击、输入等操作

        Raises:
            RuntimeError: 如果浏览器上下文未初始化
        """
        if not self.context:
            raise RuntimeError("Browser context not initialized")
        return await self.context.new_page()
