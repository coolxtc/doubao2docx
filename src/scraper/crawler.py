"""豆包爬虫核心类"""

import random
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
    """
    豆包网页爬取器
    
    负责访问豆包聊天页面、加载内容、提取数据。
    支持异步上下文管理器协议。
    """

    # 豆包聊天页面 URL 正则匹配模式
    DOUBAO_URL_PATTERN: str = r"https?://(?:www\.)?doubao\.com/thread/[\w-]+"

    def __init__(
        self,
        anti_detect_level: str = "medium",
        config: CrawlerConfig | None = None,
        tag: str = "",
        progress_callback: Callable[[str], None] | None = None,
        external_page: "Page | None" = None,
    ) -> None:
        """
        初始化爬虫
        
        Args:
            anti_detect_level: 反爬级别（low/medium/high）
            config: 爬虫配置，None 时自动从全局配置获取
            tag: 爬虫标识标签
            progress_callback: 进度回调函数
            external_page: 外部注入的页面对象，用于复用已有浏览器
        """
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
        """
        报告爬虫进度
        
        Args:
            step: 进度步骤名称
        """
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
        """
        初始化爬虫并启动浏览器
        """
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
        """
        关闭爬虫
        """
        if self._owns_browser and self.browser_mgr:
            await self.browser_mgr.close()
            self.browser_mgr = None

    async def fetch(self, url: str, max_retries: int = 3) -> ChatData:
        """
        爬取豆包聊天记录
        
        Args:
            url: 豆包聊天页面URL
            max_retries: 最大重试次数
        
        Returns:
            ChatData: 提取的聊天数据
        
        Raises:
            CrawlerError: URL无效或爬取失败
        """
        # 验证 URL 格式
        if not self._validate_url(url):
            raise CrawlerError(f"无效的豆包URL: {url}")

        # 使用外部页面或创建新页面
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

        # 遍历重试直到成功或达到最大重试次数
        for attempt in range(max_retries):
            try:
                # 访问目标页面
                await page.goto(url, timeout=self.config.page_load_timeout, wait_until="networkidle")
                
                # 检测是否被重定向到登录页或首页（反爬触发）
                current_url = page.url
                if "/login" in current_url or current_url == "https://www.doubao.com/" or current_url == "https://www.doubao.com":
                    raise CrawlerError("页面被重定向到登录页，可能是反爬触发")
                
                # 验证当前 URL 仍然有效
                if not self._validate_url(current_url):
                    raise CrawlerError(f"URL验证失败: {current_url}")

                # 执行页面交互（滚动、展开代码等）
                if self.page_actions:
                    await self.page_actions.scroll_all(page, self._report_progress)

                # 提取聊天数据
                if self.extractor:
                    chat_data = await self.extractor.extract_all(page, url)
                else:
                    raise CrawlerError("数据提取器未初始化")

                # 关闭页面
                if self._owns_browser:
                    await page.close()

                return chat_data
                
            # 捕获已知的爬取错误，进行重试
            except CrawlerError:
                if attempt == max_retries - 1:
                    raise
                # 指数退避 + 随机抖动
                wait_time = (2 ** attempt) + random.randint(500, 1500)
                await page.wait_for_timeout(wait_time)

            # 捕获其他异常，进行重试
            except Exception as e:
                if attempt == max_retries - 1:
                    raise CrawlerError(f"爬取失败: {e}")
                # 指数退避 + 随机抖动
                wait_time = (2 ** attempt) + random.randint(500, 1500)
                await page.wait_for_timeout(wait_time)

        raise CrawlerError("达到最大重试次数")

    def _validate_url(self, url: str) -> bool:
        """
        验证 URL 是否为有效的豆包聊天页面地址
        
        Args:
            url: 待验证的 URL 字符串
        
        Returns:
            bool: URL 是否符合豆包聊天页面格式
        """
        return bool(re.match(self.DOUBAO_URL_PATTERN, url))