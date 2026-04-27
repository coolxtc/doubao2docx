"""浏览器生命周期管理"""

import logging
from typing import TYPE_CHECKING, Any

from ..config import CrawlerConfig, get_config
from ..utils import is_windows, windows_compat_close
from .anti_detect import AntiDetectMiddleware, create_anti_detect_middleware

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class BrowserManager:
    """
    浏览器生命周期管理器

    支持异步上下文管理器协议。
    """

    def __init__(
        self,
        anti_detect_level: str = "medium",
        config: CrawlerConfig | None = None,
    ) -> None:
        """
        初始化浏览器管理器

        Args:
            anti_detect_level: 反爬级别（low/medium/high）
            config: 爬虫配置，None 时自动从全局配置获取
        """
        self.config: CrawlerConfig = config or get_config().crawler  # 爬虫配置
        self.anti_detect: AntiDetectMiddleware = create_anti_detect_middleware(anti_detect_level)  # 反爬中间件
        self.browser: "Browser | None" = None  # Playwright 浏览器实例
        self.context: "BrowserContext | None" = None  # Playwright 浏览器上下文
        self.playwright: "Any" = None  # Playwright 实例

    async def __aenter__(self) -> "BrowserManager":
        """异步上下文管理器入口"""
        await self.start()
        return self

    async def __aexit__(self, exc_type: type, exc_val: BaseException, exc_tb: Any) -> None:
        """异步上下文管理器退出"""
        await self.close()

    async def start(self) -> None:
        """
        启动浏览器并创建上下文

        Raises:
            RuntimeError: 浏览器启动失败
        """
        from playwright.async_api import async_playwright

        self.playwright = await async_playwright().start()
        chromium = self.playwright.chromium
        self.browser = await chromium.launch(headless=True)
        if self.browser:
            self.context = await self.browser.new_context(
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                viewport={"width": 1920, "height": 1080},
            )
        else:
            raise RuntimeError("无法启动 Chromium 浏览器")
        await self.anti_detect.apply(self.context)

    async def close(self) -> None:
        """关闭浏览器并释放资源"""
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

    async def new_page(self) -> "Page":
        """
        创建新页面

        Returns:
            Page: 新创建的页面对象

        Raises:
            RuntimeError: 上下文未初始化
        """
        if not self.context:
            raise RuntimeError("Browser context not initialized")
        return await self.context.new_page()
