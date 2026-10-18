"""浏览器生命周期管理"""

import logging
import os
import random
from typing import TYPE_CHECKING, Any

from ..config import CrawlerConfig, get_config
from ..utils import is_windows, windows_compat_close
from .anti_detect import AntiDetectMiddleware, create_anti_detect_middleware

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page

logger = logging.getLogger(__name__)

# Chromium 启动参数环境变量名（逗号分隔）
CHROMIUM_ARGS_ENV = "CHROMIUM_ARGS"


def _parse_chromium_args() -> list[str]:
    """
    从环境变量解析 Chromium 启动参数

    容器内以 root 运行必须带 --no-sandbox，桌面端不设置该环境变量时
    返回空列表，启动行为与 Playwright 默认一致。

    Returns:
        list[str]: 解析后的参数列表，未设置时为空列表
    """
    raw = os.environ.get(CHROMIUM_ARGS_ENV, "")
    return [arg.strip() for arg in raw.split(",") if arg.strip()]


def _reap_orphan_zombies() -> None:
    """
    收割转为孤儿僵尸的浏览器子进程

    browser.close() 能终止主进程，但其部分子进程会转为孤儿挂到 PID 1 下变成僵尸；
    容器里 PID 1 通常是 uvicorn，不会主动 waitpid，长期运行会持续累积直至耗尽 PID。
    必须在 playwright 已停止之后调用，避免抢走其内部等待的子进程状态。
    Windows 无 waitpid 语义，直接跳过。
    """
    if is_windows():
        return
    try:
        while True:
            pid, _ = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                break
        logger.debug("已收割残留的浏览器子进程")
    except ChildProcessError:
        # 没有可收割的子进程属正常情况
        pass


class BrowserManager:
    """
    浏览器生命周期管理器

    支持异步上下文管理器协议。
    """

    def __init__(
        self,
        anti_detect_level: str = "medium",
        config: CrawlerConfig | None = None,
        launch_args: list[str] | None = None,
    ) -> None:
        """
        初始化浏览器管理器

        Args:
            anti_detect_level: 反爬级别（low/medium/high）
            config: 爬虫配置，None 时自动从全局配置获取
            launch_args: Chromium 启动参数，None 时读取 CHROMIUM_ARGS 环境变量
        """
        self.config: CrawlerConfig = config or get_config().crawler  # 爬虫配置
        self.anti_detect: AntiDetectMiddleware = create_anti_detect_middleware(
            anti_detect_level,
            user_agents=self.config.user_agents
        )  # 反爬中间件（直接传入 UA 列表，避免重复获取配置）
        self.launch_args: list[str] = (
            list(launch_args) if launch_args is not None else _parse_chromium_args()
        )  # Chromium 启动参数（容器内 root 需 --no-sandbox）
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
        self.browser = await chromium.launch(
            headless=True,
            args=self.launch_args,
        )
        if self.browser:
            self.context = await self.browser.new_context(
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                viewport={"width": 1920, "height": 1080},
            )
        else:
            raise RuntimeError("无法启动 Chromium 浏览器")
        # 生成统一 UA（HTTP 头和 JS 注入使用同一个，避免特征矛盾）
        ua_list = self.anti_detect.user_agents
        selected_ua = random.choice(ua_list) if ua_list else None
        await self.anti_detect.apply(self.context, ua=selected_ua)

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

        # playwright 停止后，其 driver 与浏览器子进程的退出状态已无人认领
        _reap_orphan_zombies()

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
