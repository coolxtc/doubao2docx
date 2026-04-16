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

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, TYPE_CHECKING

from ..config import CrawlerConfig
from ..exceptions import CrawlerError

if TYPE_CHECKING:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext


# 爬虫步骤枚举，用于进度跟踪
class FetchStep:
    STARTING = "任务开始"
    RECEIVED = "收到任务"
    LOADING_PAGE = "访问页面"
    PAGE_LOADED = "加载完成"
    SCROLLING = "滚动加载"
    EXPANDING_CODE = "展开代码"
    EXTRACTING = "提取数据"
    COMPLETED = "爬取完成"


# 步骤到索引的映射
STEP_INDEX = {
    FetchStep.STARTING: 0,
    FetchStep.RECEIVED: 1,
    FetchStep.LOADING_PAGE: 2,
    FetchStep.PAGE_LOADED: 3,
    FetchStep.SCROLLING: 4,
    FetchStep.EXPANDING_CODE: 5,
    FetchStep.EXTRACTING: 6,
    FetchStep.COMPLETED: 7,
}

STEP_COUNT = 8

# 步骤简称（用于显示）
STEP_SHORT = {
    0: "启动",
    1: "任务",
    2: "访问",
    3: "加载",
    4: "滚动",
    5: "代码",
    6: "提取",
    7: "完成",
}


def _log(prefix: str, msg: str) -> None:
    elapsed = time.time() - _task_start_time
    print(f"{prefix} {msg} [+{elapsed:.1f}s]")


def _format_progress(prefix: str, current_step: int, current_action: str = "") -> str:
    """生成单行动态状态，如 [1/5][abc] ●●○○○○ 访问页面"""
    dots = ""
    for i in range(STEP_COUNT):
        if i < current_step:
            dots += "●"
        elif i == current_step:
            dots += "→"
        else:
            dots += "○"
    if current_action:
        return f"{prefix} {dots} {current_action}"
    return f"{prefix} {dots}"


_task_start_time = time.time()


def reset_timer() -> None:
    global _task_start_time
    _task_start_time = time.time()


@dataclass
class ChatMessage:
    """单条聊天消息的数据模型
    
    数据类（dataclass）会自动生成 __init__、__repr__、__eq__ 等方法。
    
    属性：
        role: 消息发送者角色，"user"表示用户发送的消息，"assistant"表示AI回复的消息
        content: 消息的文本内容
        timestamp: 消息发送时间，可选字段，默认为None
        images: 图片URL列表，可选字段，默认为空列表
    """
    role: str  # "user" 表示用户的消息，"assistant" 表示AI助手的消息
    content: str  # 消息的实际文本内容
    timestamp: Optional[str] = None  # 可选的时间戳
    images: list[str] = field(default_factory=list)  # 图片URL列表

    def to_dict(self) -> dict:
        """将消息对象转换为字典格式"""
        return {"role": self.role, "content": self.content, "timestamp": self.timestamp, "images": self.images}


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
        tag: str = "",
        progress_callback: Callable[[str], None] | None = None,
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
        self.page_load_timeout = self.config.page_load_timeout
        self.scroll_timeout = self.config.scroll_timeout
        self.api_timeout = self.config.api_timeout
        self.timeout = self.config.timeout
        self.wait_for_selector = self.config.wait_for_selector
        self.tag = tag
        self.progress_callback = progress_callback
        
        # 浏览器相关属性，初始化为None
        self.browser: Optional["Browser"] = None
        self.context: Optional["BrowserContext"] = None
        self.playwright = None  # Playwright 引擎实例
    
    def _report_progress(self, step: str) -> None:
        if self.progress_callback:
            self.progress_callback(step)

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
        self.playwright = await async_playwright().start()
        
        # 启动Chromium浏览器（无头模式）
        self.browser = await self.playwright.chromium.launch(headless=True)
        
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
        import asyncio
        import platform
        import warnings
        
        # 抑制 Windows 上的 ResourceWarning
        if platform.system() == "Windows":
            warnings.filterwarnings("ignore", category=ResourceWarning)
        
        # 关闭时的异常可以忽略，因为可能是资源已被清理
        try:
            if self.context:
                await self.context.close()
        except Exception:
            pass

        try:
            if self.browser:
                await self.browser.close()
        except Exception:
            pass

        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
        
        # Windows 上的资源清理处理
        if platform.system() == "Windows":
            import gc
            gc.collect()
            await asyncio.sleep(self.config.browser_close_delay)

    async def fetch(self, url: str) -> ChatData:
        # 验证URL格式
        if not self._validate_url(url):
            raise CrawlerError(f"无效的豆包URL: {url}")

        tag = self.tag
        prefix = f"[{tag}]" if tag else ""
        
        # 懒启动：如果浏览器还没启动，则启动它
        if not self.browser:
            self._report_progress(FetchStep.STARTING)
            await self.start()
        
        self._report_progress(FetchStep.RECEIVED)

        # 创建新页面并访问URL
        page = await self.context.new_page()
        self._report_progress(FetchStep.LOADING_PAGE)
        
        await page.goto(url, timeout=self.page_load_timeout, wait_until="networkidle")
        self._report_progress(FetchStep.PAGE_LOADED)
        
        # 滚动页面加载更多内容
        self._report_progress(FetchStep.SCROLLING)
        await self._scroll_page(page)

        # 提取聊天数据
        self._report_progress(FetchStep.EXPANDING_CODE)
        chat_data = await self._extract_chat_data(page, url)
        
        self._report_progress(FetchStep.EXTRACTING)
        
        # 关闭页面，释放资源
        await page.close()
        
        self._report_progress(FetchStep.COMPLETED)

        return chat_data

    def _validate_url(self, url: str) -> bool:
        """验证URL是否为有效的豆包链接
        
        使用正则表达式验证URL格式：
        - 必须以 http:// 或 https:// 开头
        - 域名必须是 doubao.com
        - 路径必须以 /thread/ 开头
        """
        return bool(re.match(self.DOUBAO_URL_PATTERN, url))

    async def _scroll_page(self, page: "Page") -> None:
        """滚动页面加载更多内容"""
        last_height = 0
        for i in range(self.config.scroll_max_attempts):
            try:
                await asyncio.wait_for(
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)"),
                    timeout=self.scroll_timeout / 1000
                )
            except asyncio.TimeoutError:
                break
            
            await page.wait_for_timeout(self.config.scroll_wait_ms)
            
            try:
                new_height = await asyncio.wait_for(
                    page.evaluate("document.body.scrollHeight"),
                    timeout=self.scroll_timeout / 1000
                )
            except asyncio.TimeoutError:
                break
            
            if new_height == last_height:
                break
            last_height = new_height

    async def _scroll_for_lazy_images(self, page: "Page") -> None:
        """滚动页面触发所有懒加载图片
        
        改进版：逐个图片元素滚动，等待加载完成
        """
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(1000)
        
        max_scroll_attempts = 20
        scroll_count = 0
        
        while scroll_count < max_scroll_attempts:
            scroll_count += 1
            
            all_imgs = await page.query_selector_all('picture img, img[class*="image"]')
            
            for img in all_imgs:
                try:
                    await img.scroll_into_view_if_needed()
                    await page.wait_for_timeout(300)
                except Exception:
                    pass
            
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(800)
            
            new_height = await page.evaluate("document.body.scrollHeight")
            
            prev_height = await page.evaluate("""
                () => {
                    if (!window._prev_scroll_height) return 0;
                    return window._prev_scroll_height;
                }
            """)
            
            if prev_height and new_height == prev_height:
                break
            
            await page.evaluate(f"window._prev_scroll_height = {new_height}")
        
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(2000)

    async def _expand_code_blocks(self, page: "Page") -> None:
        """展开所有'已生成代码'按钮
        
        豆包页面中，AI生成的代码默认是折叠的，
        需要点击"已生成代码"按钮才能展开查看。
        
        点击展开后，代码块出现在按钮容器外部（同级），
        为方便后续解析，这里将代码内容注入到按钮容器中。
        
        包含智能重试机制，确保代码块可靠展开。
        """
        tag = self.tag
        prefix = f"[{tag}] " if tag else ""
        max_retries = self.config.code_expand_max_retries
        
        for attempt in range(max_retries):
            try:
                # 点击所有未处理的按钮
                await page.evaluate("""
                    () => {
                        const containers = document.querySelectorAll('div');
                        
                        for (const container of containers) {
                            if (container.querySelector('pre[data-expanded-code]')) {
                                continue;
                            }
                            
                            if (container.textContent && container.textContent.includes('已生成代码')) {
                                const button = container.querySelector('[class*="button-"]');
                                if (button) {
                                    try {
                                        button.click();
                                    } catch (e) {
                                        const event = new MouseEvent('click', {bubbles: true, cancelable: true, view: window});
                                        button.dispatchEvent(event);
                                    }
                                }
                            }
                        }
                    }
                """)
                # 等待代码块展开
                base_wait_ms = self.config.code_expand_base_ms
                extra_wait_ms = attempt * self.config.code_expand_extra_ms
                wait_time_ms = base_wait_ms + extra_wait_ms
                await page.wait_for_timeout(wait_time_ms)
                
                # 注入代码块内容
                result = await page.evaluate("""
                    () => {
                        let injected = 0;
                        let codeBlocksFound = 0;
                        let buttonsWithoutCode = 0;
                        const containers = document.querySelectorAll('div');
                        
                        for (const container of containers) {
                            if (container.querySelector('pre[data-expanded-code]')) {
                                continue;
                            }
                            
                            const button = container.querySelector('[class*="button-"]');
                            if (!button || !button.textContent.includes('已生成代码')) {
                                continue;
                            }
                            
                            let nextSibling = container.nextElementSibling;
                            let foundCodeBlock = false;
                            
                            for (let i = 0; i < 5 && nextSibling; i++) {
                                if (nextSibling.classList && nextSibling.classList.contains('custom-code-block-container')) {
                                    foundCodeBlock = true;
                                    codeBlocksFound++;
                                    const pre = nextSibling.querySelector('pre');
                                    if (pre) {
                                        const hiddenPre = document.createElement('pre');
                                        hiddenPre.style.display = 'none';
                                        hiddenPre.setAttribute('data-expanded-code', 'true');
                                        hiddenPre.textContent = pre.textContent;
                                        container.appendChild(hiddenPre);
                                        injected++;
                                    }
                                    break;
                                }
                                nextSibling = nextSibling.nextElementSibling;
                            }
                            
                            if (!foundCodeBlock) {
                                buttonsWithoutCode++;
                            }
                        }
                        return { injected, codeBlocksFound, buttonsWithoutCode };
                    }
                """)
                
                # 如果有按钮但代码块未出现，尝试再次点击
                if result['buttonsWithoutCode'] > 0 and result['codeBlocksFound'] == 0:
                    await page.evaluate("""
                        () => {
                            const containers = document.querySelectorAll('div');
                            for (const container of containers) {
                                if (container.querySelector('pre[data-expanded-code]')) {
                                    continue;
                                }
                                if (container.textContent && container.textContent.includes('已生成代码')) {
                                    const button = container.querySelector('[class*="button-"]');
                                    if (button) {
                                        try {
                                            button.click();
                                        } catch (e) {
                                            const event = new MouseEvent('click', {bubbles: true, cancelable: true, view: window});
                                            button.dispatchEvent(event);
                                        }
                                    }
                                }
                            }
                        }
                    """)
                
                if result['injected'] > 0:
                    break
                elif result['codeBlocksFound'] == 0 and result['buttonsWithoutCode'] == 0:
                    # 没有按钮，不需要展开
                    break
                elif attempt == max_retries - 1 and result['injected'] == 0:
                    pass  # 静默失败，不打印调试信息
                    
            except Exception as e:
                _log(prefix, f"展开代码块失败 (尝试 {attempt + 1}): {e}")

    async def _extract_chat_data(self, page: "Page", url: str) -> ChatData:
        """从页面提取完整的聊天数据
        
        提取流程：
        1. 提取聊天标题
        2. 再次滚动确保完整加载
        3. 滚动触发懒加载图片
        4. 展开所有代码块
        5. 等待展开动画完成
        6. 提取所有消息
        7. 获取原始HTML
        """
        title = await self._extract_title(page)
        
        await self._scroll_page(page)
        await self._scroll_for_lazy_images(page)
        
        await self._expand_code_blocks(page)
        
        await page.wait_for_timeout(self.config.code_expand_settle_ms)
        
        messages = await self._extract_messages(page)
        
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
        1. 使用 JavaScript 提取所有消息块及其完整内容（包括展开后的代码块）
        2. 对每个消息块提取角色和 HTML 内容
        """
        messages = []

        try:
            result = await page.evaluate("""
                () => {
                    const results = [];
                    const messageBlocks = document.querySelectorAll("[class*='message-item']");
                    
                    for (const block of messageBlocks) {
                        const classAttr = block.className || '';
                        const role = classAttr.includes('justify-end') ? 'user' : 'assistant';
                        
                        let content = block.innerHTML;
                        
                        const hiddenPres = block.querySelectorAll('pre[data-expanded-code]');
                        for (const pre of hiddenPres) {
                            content += pre.outerHTML;
                        }
                        
                        const images = [];
                        const seen = new Set();
                        const pictureContainers = block.querySelectorAll('picture');
                        
                        for (const pic of pictureContainers) {
                            const sources = pic.querySelectorAll('source');
                            const imgElement = pic.querySelector('img');
                            
                            let foundSrc = '';
                            
                            for (const src of sources) {
                                const srcset = src.srcset || src.dataset.srcset;
                                if (srcset && !srcset.startsWith('data:')) {
                                    foundSrc = srcset;
                                    break;
                                }
                            }
                            
                            if (!foundSrc && imgElement) {
                                const src = imgElement.dataset.original || imgElement.dataset.src || imgElement.src;
                                if (src && !src.startsWith('data:')) {
                                    foundSrc = src;
                                }
                            }
                            
                            if (foundSrc && !seen.has(foundSrc)) {
                                seen.add(foundSrc);
                                images.push(foundSrc);
                            }
                        }
                        
                        if (content && content.length > 0) {
                            results.push({ role, content, images });
                        }
                    }
                    
                    return results;
                }
            """)
            
            for item in result:
                messages.append(ChatMessage(role=item['role'], content=item['content'], images=item.get('images', [])))

            if not messages:
                messages = await self._extract_fallback(page)

        except Exception:
            messages = await self._extract_fallback(page)

        return messages

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