"""
豆包网页爬取器

本模块提供了从豆包网站爬取聊天记录的功能。
主要使用 Playwright 自动化浏览器来模拟真实用户访问网页，
并提取聊天内容。

主要功能：
1. 验证豆包聊天页面的URL格式
2. 启动无头浏览器（headless）访问网页
3. 等待页面完全加载
4. 滚动页面加载更多历史消息
5. 展开"已生成代码"等隐藏内容
6. 提取聊天标题和消息内容
"""

import re
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

from ..config import CrawlerConfig

if TYPE_CHECKING:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext


@dataclass
class ChatMessage:
    """单条聊天消息的数据模型
    
    数据类（dataclass）会自动生成 __init__、__repr__、__eq__ 等方法。
    
    属性：
        role: 消息发送者角色，"user"表示用户发送的消息，"assistant"表示AI回复的消息
        content: 消息的文本内容
        timestamp: 消息发送时间，可选字段，默认为None
    """
    role: str  # "user" 表示用户的消息，"assistant" 表示AI助手的消息
    content: str  # 消息的实际文本内容
    timestamp: Optional[str] = None  # 可选的时间戳

    def to_dict(self) -> dict:
        """将消息对象转换为字典格式"""
        return {"role": self.role, "content": self.content, "timestamp": self.timestamp}


@dataclass
class ChatData:
    """聊天记录数据模型
    
    用于存储完整的聊天对话数据，包括：
    - url：聊天页面的网址
    - title：聊天标题
    - messages：消息列表
    - raw_html：页面的原始HTML
    
    属性：
        url: 豆包聊天页面的完整URL
        title: 聊天标题
        messages: ChatMessage对象列表
        raw_html: 页面的完整HTML源代码
    """
    url: str
    title: str = ""
    messages: list[ChatMessage] = field(default_factory=list)
    raw_html: str = ""

    def to_dict(self) -> dict:
        """将聊天数据转换为字典格式"""
        return {
            "url": self.url,
            "title": self.title,
            "messages": [msg.to_dict() for msg in self.messages],
        }


class DoubaoSpider:
    """豆包网页爬取器 - 核心爬虫类
    
    使用 Playwright 自动化浏览器来爬取豆包聊天记录。
    支持 async with 语法，使用完毕后自动关闭浏览器。
    
    工作原理：
    1. 使用Playwright启动Chromium浏览器（无头模式）
    2. 创建BrowserContext（浏览器上下文），相当于新的浏览器会话
    3. 应用反爬中间件，修改浏览器指纹
    4. 访问目标URL，等待页面加载
    5. 滚动页面触发懒加载，获取更多历史消息
    6. 提取页面中的聊天标题和消息内容
    7. 返回ChatData对象
    
    使用示例：
        async with DoubaoSpider() as spider:
            data = await spider.fetch(url)
    """
    
    # URL匹配正则表达式：匹配 doubao.com/thread/xxx 格式的URL
    DOUBAO_URL_PATTERN = r"https?://(?:www\.)?doubao\.com/thread/[\w-]+"

    def __init__(
        self,
        anti_detect_level: str = "medium",
        config: CrawlerConfig = None,
    ) -> None:
        """初始化爬虫实例
        
        Args:
            anti_detect_level: 反爬措施级别，可选 "low"/"medium"/"high"
                              级别越高，反爬措施越强，但也可能影响访问速度
            config: 爬虫配置对象，如果为None则使用默认配置
        """
        from .anti_detect import create_anti_detect_middleware

        # 如果没有提供配置，使用默认配置
        self.config = config or CrawlerConfig()
        
        # 根据级别创建反爬中间件
        self.anti_detect = create_anti_detect_middleware(anti_detect_level)
        
        # 从配置中读取超时时间和等待选择器
        self.timeout = self.config.timeout
        self.wait_for_selector = self.config.wait_for_selector
        
        # 浏览器相关属性，初始化为None
        self.browser: Optional["Browser"] = None
        self.context: Optional["BrowserContext"] = None

    async def __aenter__(self):
        """异步上下文管理器入口 - 支持 with...as 语法
        
        进入 with 块时调用，确保浏览器在使用前启动。
        """
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口 - 自动清理资源
        
        无论是否发生异常，都会执行清理工作，关闭浏览器。
        """
        await self.close()

    async def start(self) -> None:
        """启动浏览器并创建浏览器上下文
        
        核心步骤：
        1. 启动Playwright引擎
        2. 启动Chromium浏览器（无头模式）
        3. 创建浏览器上下文（独立的会话环境）
        4. 应用反爬中间件
        
        Playwright工作原理：
        - Playwright是微软开发的浏览器自动化工具
        - 支持Chromium、Firefox、WebKit三种浏览器引擎
        - "无头模式"（headless=True）表示不显示浏览器窗口，在后台运行
        - BrowserContext类似于浏览器的"隐身窗口"，有独立的Cookie和Session
        """
        from playwright.async_api import async_playwright
        
        # 启动Playwright引擎
        playwright = await async_playwright().start()
        
        # 启动Chromium浏览器（无头模式）
        self.browser = await playwright.chromium.launch(headless=True)
        
        # 创建浏览器上下文（独立的会话环境）
        self.context = await self.browser.new_context()
        
        # 应用反爬中间件
        await self.anti_detect.apply(self.context)

    async def close(self) -> None:
        """关闭浏览器并释放资源
        
        重要：每次使用完爬虫后必须调用此方法，
        否则浏览器进程会留在内存中，造成资源泄漏。
        
        使用 async with 语法会自动调用此方法。
        """
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()

    async def fetch(self, url: str) -> ChatData:
        """爬取指定URL的聊天记录 - 主方法
        
        完成整个爬取流程：
        1. 验证URL格式
        2. 懒启动：如果浏览器还没启动，则启动它
        3. 创建新页面并访问URL
        4. 等待内容加载
        5. 滚动页面加载更多内容
        6. 提取聊天数据
        7. 清理页面资源
        
        Args:
            url: 豆包聊天页面URL，格式如 https://www.doubao.com/thread/xxx
            
        Returns:
            ChatData: 包含url、title、messages、raw_html的数据对象
            
        Raises:
            ValueError: 如果URL格式无效
        """
        # 验证URL格式
        if not self._validate_url(url):
            raise ValueError(f"无效的豆包URL: {url}")

        # 懒启动：如果浏览器还没启动，则启动它
        if not self.browser:
            await self.start()

        # 创建新页面（标签页）
        page = await self.context.new_page()
        
        # 访问URL并等待网络空闲
        # timeout: 请求超时时间（毫秒）
        # wait_until="networkidle": 等待网络请求都完成
        await page.goto(url, timeout=self.timeout, wait_until="networkidle")

        # 等待页面内容加载
        await self._wait_for_content(page)
        
        # 滚动页面加载更多内容
        await self._scroll_page(page)

        # 提取聊天数据
        chat_data = await self._extract_chat_data(page, url)
        
        # 关闭页面，释放资源
        await page.close()

        return chat_data

    def _validate_url(self, url: str) -> bool:
        """验证URL是否为有效的豆包链接
        
        使用正则表达式验证URL格式：
        - 必须以 http:// 或 https:// 开头
        - 域名必须是 doubao.com
        - 路径必须以 /thread/ 开头
        """
        return bool(re.match(self.DOUBAO_URL_PATTERN, url))

    async def _wait_for_content(self, page: "Page") -> None:
        """等待页面内容加载完成
        
        策略：
        1. 尝试等待指定的选择器出现
        2. 如果超时，则等待固定时间
        """
        try:
            await page.wait_for_selector(self.wait_for_selector, timeout=self.timeout)
        except Exception:
            await page.wait_for_timeout(self.config.content_load_wait_ms / 1000)

    async def _scroll_page(self, page: "Page") -> None:
        """滚动页面加载更多内容
        
        豆包聊天页面使用"无限滚动"（lazy loading）技术：
        - 初始只显示部分消息
        - 滚动到底部时再加载更多
        - 重复滚动直到没有新内容
        """
        last_height = 0
        for _ in range(self.config.scroll_max_attempts):
            # 滚动到页面最底部
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            
            # 等待新内容加载
            await page.wait_for_timeout(self.config.scroll_wait_ms / 1000)
            
            # 获取新的页面高度
            new_height = await page.evaluate("document.body.scrollHeight")
            
            # 如果高度没变，说明已经滚动到底部
            if new_height == last_height:
                break
            last_height = new_height

    async def _expand_code_blocks(self, page: "Page") -> None:
        """展开所有'已生成代码'按钮
        
        豆包页面中，AI生成的代码默认是折叠的，
        需要点击"已生成代码"按钮才能展开查看。
        """
        try:
            result = await page.evaluate("""
                () => {
                    let clicked = 0;
                    
                    // 方法1: 通过按钮文案查找
                    const buttons = document.querySelectorAll('div');
                    for (const btn of buttons) {
                        if (btn.textContent && btn.textContent.includes('已生成代码') && typeof btn.click === 'function') {
                            btn.click();
                            clicked++;
                            continue;
                        }
                    }
                    
                    // 方法2: 使用CSS选择器备选
                    if (clicked === 0) {
                        const fallbackButtons = document.querySelectorAll('[class*="button-L3npDO"]');
                        fallbackButtons.forEach(btn => {
                            if (btn.textContent && btn.textContent.includes('已生成代码') && typeof btn.click === 'function') {
                                btn.click();
                                clicked++;
                            }
                        });
                    }
                    
                    return clicked;
                }
            """)
            await page.wait_for_timeout(self.config.code_expand_wait_ms / 1000)
        except Exception as e:
            print(f"展开代码块失败: {e}")

    async def _extract_chat_data(self, page: "Page", url: str) -> ChatData:
        """从页面提取完整的聊天数据
        
        提取流程：
        1. 提取聊天标题
        2. 再次滚动确保完整加载
        3. 展开所有代码块
        4. 等待展开动画完成
        5. 提取所有消息
        6. 获取原始HTML
        """
        # 提取标题
        title = await self._extract_title(page)
        
        # 再次滚动（确保完整加载）
        await self._scroll_page(page)
        
        # 展开代码块
        await self._expand_code_blocks(page)
        
        # 等待展开动画完成
        await page.wait_for_timeout(self.config.code_expand_settle_ms / 1000)
        
        # 提取消息列表
        messages = await self._extract_messages(page)
        
        # 获取原始HTML
        raw_html = await page.content()

        return ChatData(url=url, title=title, messages=messages, raw_html=raw_html)

    async def _extract_title(self, page: "Page") -> str:
        """提取聊天标题
        
        尝试多种方式查找标题：
        1. h1 元素
        2. class包含"chat-title"的元素
        3. class包含"title"的元素
        """
        try:
            title_element = await page.query_selector("h1, .chat-title, [class*='title']")
            if title_element:
                return await title_element.inner_text()
        except Exception:
            pass
        return "未命名对话"

    async def _extract_messages(self, page: "Page") -> list[ChatMessage]:
        """提取聊天消息列表
        
        主要提取策略：
        1. 查找所有消息块元素（class包含"message-item"）
        2. 对每个消息块提取角色和内容
        3. 如果提取不到，使用备用方法
        """
        messages = []

        try:
            message_blocks = await page.query_selector_all("[class*='message-item']")

            for block in message_blocks:
                role = await self._extract_role(block)
                content = await self._extract_content(block)

                if content and role:
                    messages.append(ChatMessage(role=role, content=content))

            if not messages:
                messages = await self._extract_fallback(page)

        except Exception:
            messages = await self._extract_fallback(page)

        return messages

    async def _extract_role(self, element) -> Optional[str]:
        """从消息元素中提取角色（user或assistant）
        
        通过CSS类名判断：
        - 如果class包含"justify-end"，则是用户消息
        - 否则是AI助手消息
        """
        try:
            class_attr = await element.get_attribute("class") or ""
            if "justify-end" in class_attr:
                return "user"
            else:
                return "assistant"
        except Exception:
            pass
        return None

    async def _extract_content(self, element) -> Optional[str]:
        """从消息元素中提取内容
        
        策略：
        1. 如果HTML包含data-custom-copy-text属性，使用完整HTML
        2. 如果内容较长（>100字符），也使用完整HTML
        """
        try:
            html = await element.evaluate("(el) => el.innerHTML")
            if html and "data-custom-copy-text" in html:
                return html
            if html and len(html) > 100:
                return html
        except Exception:
            pass
        return None

    async def _extract_fallback(self, page: "Page") -> list[ChatMessage]:
        """备用消息提取方法
        
        如果常规方法提取失败，尝试查找所有p标签和class包含content的div
        """
        messages = []
        try:
            text = await page.evaluate("""
                () => {
                    const elements = document.querySelectorAll('p, div[class*="content"]');
                    return Array.from(elements).map(el => el.innerText).join('\\n');
                }
            """)
            if text:
                messages.append(ChatMessage(role="assistant", content=text))
        except Exception:
            pass
        return messages


async def fetch_doubao_chat(url: str, **kwargs) -> ChatData:
    """便捷函数：直接爬取豆包聊天记录
    
    封装了常见的使用模式，自动创建爬虫实例并确保资源清理。
    
    使用示例：
        data = await fetch_doubao_chat(url)
    
    Args:
        url: 豆包聊天页面URL
        **kwargs: 传递给DoubaoSpider的其他参数
        
    Returns:
        ChatData: 爬取到的聊天数据
    """
    async with DoubaoSpider(**kwargs) as spider:
        return await spider.fetch(url)