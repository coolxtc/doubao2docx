"""反爬中间件"""

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext


class AntiDetectMiddleware:
    """
    反爬检测中间件

    通过修改浏览器上下文属性绕过反爬检测。
    """

    def __init__(
        self,
        random_user_agent: bool = True,
        disableAutomation: bool = True,
    ) -> None:
        """
        初始化反爬中间件

        Args:
            random_user_agent: 是否随机选择 User-Agent
            disableAutomation: 是否隐藏自动化标识
        """
        from ..config import get_config

        self.random_user_agent: bool = random_user_agent
        self.disableAutomation: bool = disableAutomation
        config = get_config()
        crawler_config = config.crawler
        self.user_agents: list[str] = crawler_config.user_agents if crawler_config and crawler_config.user_agents else []

    async def apply(self, context: "BrowserContext") -> None:
        """
        应用反爬措施到浏览器上下文

        Args:
            context: Playwright 浏览器上下文
        """
        if self.random_user_agent:
            await self._set_random_user_agent(context)

        if self.disableAutomation:
            await self._disable_automation(context)

    async def _set_random_user_agent(self, context: "BrowserContext") -> None:
        """
        设置随机 User-Agent

        Args:
            context: Playwright 浏览器上下文
        """
        if self.user_agents:
            user_agent = random.choice(self.user_agents)
            await context.set_extra_http_headers({"User-Agent": user_agent})

    async def _disable_automation(self, context: "BrowserContext") -> None:
        """
        隐藏 webdriver 自动化标识

        Args:
            context: Playwright 浏览器上下文
        """
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en-US', 'en']
            });
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5].map(() => ({
                    name: Math.random().toString(36).substring(7),
                    description: '',
                    filename: ''
                }))
            });
            
            delete window.cdc_adoQpoasnfaoPgfQlAShMmHhkk;
            delete window.__webdriver_evaluate;
            delete window.domAutomation;
            delete window.domAutomationActivated;
            delete window.domAutomationController;
            
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (query) => (
                query === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(query)
            );
        """)


def create_anti_detect_middleware(level: str = "medium") -> AntiDetectMiddleware:
    """
    工厂函数：创建预设的反爬中间件

    Args:
        level: 反爬级别（low/medium/high）

    Returns:
        AntiDetectMiddleware: 配置好的中间件实例
    """
    presets = {
        "low": {"random_user_agent": True, "disableAutomation": False},
        "medium": {"random_user_agent": True, "disableAutomation": True},
        "high": {"random_user_agent": True, "disableAutomation": True},
    }
    config = presets.get(level, presets["medium"])
    return AntiDetectMiddleware(**config)
