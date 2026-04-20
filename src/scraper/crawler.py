"""
豆包爬虫核心类

整合爬虫的各个功能模块，提供统一的爬虫入口。
"""

import re
from typing import Callable, Optional, TYPE_CHECKING

from ..config import CrawlerConfig
from ..exceptions import CrawlerError
from .browser import BrowserManager
from .extractor import DataExtractor
from .models import ChatData
from .page_actions import PageActions
from .steps import FetchStep, reset_timer

if TYPE_CHECKING:
    from playwright.async_api import Page


class DoubaoSpider:
    """豆包网页爬取器

    使用 Playwright 自动化浏览器来爬取豆包聊天记录，支持 async with 语法。
    """

    DOUBAO_URL_PATTERN = r"https?://(?:www\.)?doubao\.com/thread/[\w-]+"

    def __init__(
        self,
        anti_detect_level: str = "medium",
        config: Optional[CrawlerConfig] = None,
        tag: str = "",
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config or CrawlerConfig()
        self.anti_detect_level = anti_detect_level
        self.tag = tag
        self.progress_callback = progress_callback
        self.browser_mgr: Optional[BrowserManager] = None
        self.page_actions: Optional[PageActions] = None
        self.extractor: Optional[DataExtractor] = None

    def _report_progress(self, step: str) -> None:
        """报告爬虫进度"""
        if self.progress_callback:
            self.progress_callback(step)

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self.close()

    async def start(self) -> None:
        """初始化爬虫并启动浏览器

        创建浏览器管理器、页面操作器和数据提取器。
        """
        self.browser_mgr = BrowserManager(
            anti_detect_level=self.anti_detect_level,
            config=self.config,
        )
        await self.browser_mgr.start()
        self.page_actions = PageActions(self.config)
        self.extractor = DataExtractor(self.config)

    async def close(self) -> None:
        """关闭爬虫"""
        if self.browser_mgr:
            await self.browser_mgr.close()
            self.browser_mgr = None

    async def fetch(self, url: str) -> ChatData:
        """爬取豆包聊天记录"""
        if not self._validate_url(url):
            raise CrawlerError(f"无效的豆包URL: {url}")

        tag = self.tag
        prefix = f"[{tag}]" if tag else ""

        if not self.browser_mgr:
            self._report_progress(FetchStep.STARTING)
            await self.start()

        page = await self.browser_mgr.new_page()
        self._report_progress(FetchStep.LOADING_PAGE)

        await page.goto(url, timeout=self.config.page_load_timeout, wait_until="networkidle")
        self._report_progress(FetchStep.PAGE_LOADED)

        self._report_progress(FetchStep.SCROLLING)

        def on_scroll_progress(current: int, total: int) -> None:
            self._report_progress(f"滚动{current}次")

        await self.page_actions.scroll_all(page, progress_callback=on_scroll_progress)

        chat_data = await self.extractor.extract_all(page, url)

        await page.close()

        self._report_progress(FetchStep.COMPLETED)

        return chat_data

    def _validate_url(self, url: str) -> bool:
        """验证 URL 是否为有效的豆包聊天页面地址"""
        return bool(re.match(self.DOUBAO_URL_PATTERN, url))


async def fetch_doubao_chat(url: str, **kwargs) -> ChatData:
    """直接爬取豆包聊天记录"""
    async with DoubaoSpider(**kwargs) as spider:
        return await spider.fetch(url)