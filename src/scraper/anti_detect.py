"""
反爬处理中间件

提供反检测功能，帮助爬虫伪装成真实用户浏览器。
"""

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext


class AntiDetectMiddleware:
    """反爬检测中间件

    通过注入 JavaScript 代码修改浏览器属性，伪装成真实用户。
    """

    def __init__(
        self,
        random_user_agent: bool = True,
        disableAutomation: bool = True,
    ) -> None:
        """初始化反爬中间件"""
        from ..config import get_config

        self.random_user_agent = random_user_agent
        self.disableAutomation = disableAutomation
        # 使用全局配置单例
        self.user_agents = get_config().crawler.user_agents

    async def apply(self, context: "BrowserContext") -> None:
        """应用反爬措施到浏览器上下文"""
        if self.random_user_agent:
            await self._set_random_user_agent(context)

        if self.disableAutomation:
            await self._disable_automation(context)

    async def _set_random_user_agent(self, context: "BrowserContext") -> None:
        """设置随机 User-Agent"""
        user_agent = random.choice(self.user_agents)
        await context.set_extra_http_headers({"User-Agent": user_agent})

    async def _disable_automation(self, context: "BrowserContext") -> None:
        """隐藏 webdriver 自动化标识"""
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)


def create_anti_detect_middleware(
    level: str = "medium",
) -> AntiDetectMiddleware:
    """创建预设的反爬中间件"""
    presets = {
        "low": {"random_user_agent": True, "disableAutomation": False},
        "medium": {"random_user_agent": True, "disableAutomation": True},
        "high": {"random_user_agent": True, "disableAutomation": True},
    }
    config = presets.get(level, presets["medium"])
    return AntiDetectMiddleware(**config)