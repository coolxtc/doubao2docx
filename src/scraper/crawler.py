"""豆包爬虫核心类"""

import re
from typing import TYPE_CHECKING, Any, Callable

from ..config import CrawlerConfig, get_config
from ..exceptions import CrawlerError
from .browser import BrowserManager
from .extractor import DataExtractor
from .models import ChatData
from .page_actions import PageActions
from .steps import FetchStep

if TYPE_CHECKING:
    from playwright.async_api import Page


class DoubaoSpider:
    """豆包网页爬取器"""

    DOUBAO_URL_PATTERN: str = r"https?://(?:www\.)?doubao\.com/thread/[\w-]+"

    def __init__(
        self,
        anti_detect_level: str = "medium",
        config: CrawlerConfig | None = None,
        tag: str = "",
        progress_callback: Callable[[str], None] | None = None,
        external_page: "Page | None" = None,
    ) -> None:
        self.config: CrawlerConfig = config or get_config().crawler
        self.anti_detect_level: str = anti_detect_level
        self.tag: str = tag
        self.progress_callback: Callable[[str], None] | None = progress_callback
        self.browser_mgr: BrowserManager | None = None
        self.page_actions: PageActions | None = None
        self.extractor: DataExtractor | None = None
        self._external_page: "Page | None" = external_page
        self._owns_browser: bool = external_page is None

    def _report_progress(self, step: str) -> None:
        """报告爬虫进度"""
        if self.progress_callback:
            self.progress_callback(step)

    async def __aenter__(self) -> "DoubaoSpider":
        """异步上下文管理器入口"""
        await self.start()
        return self

    async def __aexit__(self, exc_type: type, exc_val: BaseException, exc_tb: Any) -> None:
        """异步上下文管理器退出"""
        await self.close()

    async def start(self) -> None:
        """初始化爬虫并启动浏览器"""
        if self._external_page is not None:
            self.page_actions = PageActions(self.config)
            self.extractor = DataExtractor(self.config)
            return

        self.browser_mgr = BrowserManager(
            anti_detect_level=self.anti_detect_level,
            config=self.config,
        )
        await self.browser_mgr.start()
        self.page_actions = PageActions(self.config)
        self.extractor = DataExtractor(self.config)

    async def close(self) -> None:
        """关闭爬虫"""
        if self._owns_browser and self.browser_mgr:
            await self.browser_mgr.close()
            self.browser_mgr = None

    async def fetch(self, url: str) -> ChatData:
        """爬取豆包聊天记录"""
        if not self._validate_url(url):
            raise CrawlerError(f"无效的豆包URL: {url}")

        if self._external_page is not None:
            page = self._external_page
        else:
            if not self.browser_mgr:
                self._report_progress(FetchStep.STARTING)
                await self.start()
            if not self.browser_mgr:
                raise CrawlerError("浏览器未初始化")
            page = await self.browser_mgr.new_page()

        self._report_progress(FetchStep.LOADING_PAGE)

        await page.goto(url, timeout=self.config.page_load_timeout, wait_until="networkidle")
        self._report_progress(FetchStep.PAGE_LOADED)

        self._report_progress(FetchStep.SCROLLING)

        if self.page_actions:
            await self.page_actions.scroll_all(page)

        if self.extractor:
            chat_data = await self.extractor.extract_all(page, url)
        else:
            raise CrawlerError("数据提取器未初始化")

        if self._owns_browser:
            await page.close()

        self._report_progress(FetchStep.COMPLETED)

        return chat_data

    def _validate_url(self, url: str) -> bool:
        """验证 URL 是否为有效的豆包聊天页面地址"""
        return bool(re.match(self.DOUBAO_URL_PATTERN, url))


async def fetch_doubao_chat(url: str, **kwargs: Any) -> ChatData:
    """直接爬取豆包聊天记录"""
    async with DoubaoSpider(**kwargs) as spider:
        return await spider.fetch(url)