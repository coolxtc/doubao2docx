"""
反爬处理中间件

本模块提供反检测功能，帮助爬虫伪装成真实用户浏览器。
主要通过修改浏览器指纹来绕过网站的自动化检测。

检测原理：
    网站可以通过以下方式检测自动化脚本：
    1. navigator.webdriver 属性：Selenium/Playwright等工具会设置此属性
    2. User-Agent：自动化浏览器可能有特殊的User-Agent
    3. 浏览器特征：如是否有真实浏览器的各种特性

本模块的反检测措施：
    1. 随机User-Agent：每次请求使用不同的浏览器标识
    2. 隐藏webdriver属性：将 navigator.webdriver 设为 undefined
"""

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext


class AntiDetectMiddleware:
    """反爬检测中间件 - 负责修改浏览器指纹
    
    这个类的核心功能是修改浏览器的一些设置，
    让网站无法轻易识别出我们是自动化程序。
    
    工作原理：
    1. 在浏览器上下文中注入JavaScript代码
    2. 这些代码会在页面加载前执行
    3. 修改浏览器的某些属性，伪装成真实用户
    
    检测原理：
    - 当使用Playwright等自动化工具时，浏览器会设置 navigator.webdriver = true
    - 网站可以通过这个属性判断是否是自动化程序
    - 我们通过JavaScript把这个属性改为 undefined（未定义）
    """
    
    # 预定义的常见浏览器User-Agent列表
    # User-Agent 是浏览器向服务器发送的标识字符串
    # 包含了浏览器类型、版本、操作系统等信息
    USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    ]

    def __init__(
        self,
        random_user_agent: bool = True,
        disableAutomation: bool = True,
    ) -> None:
        """初始化反爬中间件
        
        Args:
            random_user_agent: 是否随机选择User-Agent
                               True: 每次请求随机选择列表中的一个
            disableAutomation: 是否隐藏webdriver自动化标识
                               True: 修改 navigator.webdriver 为 undefined
        """
        self.random_user_agent = random_user_agent
        self.disableAutomation = disableAutomation

    async def apply(self, context: "BrowserContext") -> None:
        """应用反爬措施到浏览器上下文
        
        根据配置调用其他方法：
        1. 如果启用random_user_agent，设置随机User-Agent
        2. 如果启用disableAutomation，注入隐藏webdriver的脚本
        
        BrowserContext（浏览器上下文）小科普：
        - 类似于浏览器中的"新的隐身窗口"
        - 每个上下文有独立的Cookie、LocalStorage、Session
        - 不同上下文之间完全隔离，互不影响
        """
        if self.random_user_agent:
            await self._set_random_user_agent(context)

        if self.disableAutomation:
            await self._disable_automation(context)

    async def _set_random_user_agent(self, context: "BrowserContext") -> None:
        """设置随机User-Agent
        
        User-Agent 小科普：
        - 是浏览器向网站服务器发送的"自我介绍"字符串
        - 包含浏览器类型、版本、操作系统等信息
        
        为什么需要随机：
        - 同一个UA大量请求很容易被发现
        - 随机使用多个UA可以分散请求特征
        
        实现原理：
        - 使用 random.choice 从列表中随机选择一个
        - 通过 set_extra_http_headers 设置HTTP请求头
        - 这样该上下文发出的所有请求都会带上这个UA
        """
        user_agent = random.choice(self.USER_AGENTS)
        await context.set_extra_http_headers({"User-Agent": user_agent})

    async def _disable_automation(self, context: "BrowserContext") -> None:
        """隐藏webdriver自动化标识 - 核心反检测技术
        
        原理详解：
        1. Selenium、Playwright等自动化工具会在浏览器中注入脚本
        2. 这些脚本会设置 navigator.webdriver = true
        3. 网站可以通过 JavaScript 检测这个属性
        4. 我们通过注入脚本把这个属性覆盖为 undefined
        
        实现方式：
        - 使用 add_init_script 注入初始化脚本
        - 这个脚本会在页面加载前执行
        - 使用 Object.defineProperty 重新定义属性
        """
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)


def create_anti_detect_middleware(
    level: str = "medium",
) -> AntiDetectMiddleware:
    """创建预设的反爬中间件 - 工厂函数
    
    根据指定的级别返回不同配置的中间件。
    
    预设级别说明：
    - "low"（低）：随机User-Agent开启，隐藏webdriver关闭
    - "medium"（中）：随机User-Agent开启，隐藏webdriver开启
    - "high"（高）：同medium，可扩展更多措施
    
    Args:
        level: 预设级别，可选 'low', 'medium', 'high'
              如果传入不存在的级别，使用 'medium' 作为默认值
        
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