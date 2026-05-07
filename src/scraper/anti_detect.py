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
        user_agents: list[str] | None = None,
    ) -> None:
        """
        初始化反爬中间件

        Args:
            random_user_agent: 是否随机选择 User-Agent
            disableAutomation: 是否隐藏自动化标识
            user_agents: 可选的 UA 列表，不传则从配置读取
        """
        from ..config import get_config

        self.random_user_agent: bool = random_user_agent
        self.disableAutomation: bool = disableAutomation
        if user_agents is not None:
            self.user_agents: list[str] = user_agents
        else:
            config = get_config()
            crawler_config = config.crawler
            self.user_agents = crawler_config.user_agents if crawler_config and crawler_config.user_agents else []
        # 外部传入的统一 UA，确保 HTTP 头和 JS 一致
        self._unified_ua: str | None = None

    async def apply(self, context: "BrowserContext", ua: str | None = None) -> None:
        """
        应用反爬措施到浏览器上下文

        Args:
            context: Playwright 浏览器上下文
            ua: 可选，强制 HTTP 头和 JS 使用同一 UA；若不传则随机选取
        """
        # 确定统一 UA
        if ua:
            self._unified_ua = ua
        elif self.random_user_agent and self.user_agents:
            self._unified_ua = random.choice(self.user_agents)
        else:
            self._unified_ua = None

        if self.random_user_agent:
            await self._set_random_user_agent(context)
        if self.disableAutomation:
            await self._disable_automation(context)

    async def _set_random_user_agent(self, context: "BrowserContext") -> None:
        """
        设置随机 User-Agent（使用统一 UA）

        Args:
            context: Playwright 浏览器上下文
        """
        ua = self._unified_ua
        if not ua and self.user_agents:
            ua = random.choice(self.user_agents)
        if ua:
            await context.set_extra_http_headers({"User-Agent": ua})

    async def _disable_automation(self, context: "BrowserContext") -> None:
        """
        隐藏 webdriver 自动化标识（使用统一 UA）

        Args:
            context: Playwright 浏览器上下文
        """
        # 确定 UA（如果前面没设置，则在这里选一个兜底）
        ua = self._unified_ua
        if not ua:
            if self.user_agents:
                ua = random.choice(self.user_agents)
            else:
                ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

        ua_escaped = ua.replace("'", "\\'")

        init_script = f"""
            Object.defineProperty(navigator, 'webdriver', {{
                get: () => undefined
            }});

            Object.defineProperty(navigator, 'userAgent', {{
                get: () => '{ua_escaped}'
            }});

            const pluginNames = [
                'Chrome PDF Plugin', 'Chrome PDF Viewer', 'Native Client',
                'Widevine Content Decryption Module', 'Microsoft Edge PDF Plugin',
                'WebKit built-in PDF'
            ];
            const numPlugins = 3 + Math.floor(Math.random() * 5);
            const plugins = [];
            for (let i = 0; i < numPlugins; i++) {{
                plugins.push({{
                    name: pluginNames[i % pluginNames.length],
                    description: '',
                    filename: 'internal-pdf-viewer'
                }});
            }}
            Object.defineProperty(navigator, 'plugins', {{
                get: () => plugins
            }});

            Object.defineProperty(navigator, 'languages', {{
                get: () => ['zh-CN', 'zh', 'en-US', 'en']
            }});

            delete window.cdc_adoQpoasnfaoPgfQlAShMmHhkk;
            delete window.__webdriver_evaluate;
            delete window.domAutomation;
            delete window.domAutomationActivated;
            delete window.domAutomationController;

            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({{ state: Notification.permission }}) :
                    originalQuery(parameters)
            );

            window.chrome = {{ runtime: {{}} }};
        """
        await context.add_init_script(init_script)


def create_anti_detect_middleware(level: str = "medium", **kwargs: object) -> AntiDetectMiddleware:
    """
    工厂函数：创建预设的反爬中间件

    Args:
        level: 反爬级别（low/medium/high）
        **kwargs: 传递给 AntiDetectMiddleware 的额外参数

    Returns:
        AntiDetectMiddleware: 配置好的中间件实例
    """
    presets: dict[str, dict[str, object]] = {
        "low": {"random_user_agent": True, "disableAutomation": False},
        "medium": {"random_user_agent": True, "disableAutomation": True},
        "high": {"random_user_agent": True, "disableAutomation": True},
    }
    params = presets.get(level, presets["medium"]).copy()
    params.update(kwargs)
    user_agents = kwargs.get("user_agents")
    assert user_agents is None or isinstance(user_agents, list)
    return AntiDetectMiddleware(
        random_user_agent=bool(params.get("random_user_agent", True)),
        disableAutomation=bool(params.get("disableAutomation", True)),
        user_agents=user_agents,
    )
