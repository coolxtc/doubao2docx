"""
数据提取功能模块

负责从 Playwright 页面中提取聊天数据。
使用 JavaScript 在浏览器内执行提取逻辑，获取结构化的聊天信息。

为什么需要这个模块？
1. 性能：直接在浏览器中提取数据，避免数据传输开销
2. 准确性：可以访问 DOM 的完整状态，包括懒加载内容
3. 可靠性：复杂的 CSS 选择器在浏览器中可以正确执行

提取流程：
1. extract_title(): 提取聊天标题
2. extract_messages(): 提取消息列表（角色、内容、图片）
3. extract_all(): 组装完整的 ChatData

技术细节：
- 使用 page.evaluate() 在浏览器内执行 JavaScript
- 通过 querySelectorAll 获取消息块
- 解析 class 属性判断用户/助手角色
- 从 picture 元素提取懒加载图片
"""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from playwright.async_api import Page

from ..config import CrawlerConfig
from .models import ChatData, ChatMessage, ImageData


class DataExtractor:
    """数据提取器"""

    def __init__(self, config: CrawlerConfig) -> None:
        self.config: CrawlerConfig = config
        self.logger = logging.getLogger(__name__)

    async def extract_title(self, page: "Page") -> str:
        """提取聊天标题"""
        try:
            title_element = await page.query_selector("h1, .chat-title, [class*='title']")
            if title_element:
                return await title_element.inner_text()
        except Exception:
            pass
        return "未命名对话"

    async def extract_messages(self, page: "Page") -> list[ChatMessage]:
        """提取聊天消息列表"""
        messages: list[ChatMessage] = []

        try:
            result: list[dict[str, Any]] = await page.evaluate("""
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
                                    foundSrc = srcset.split(',')[0].trim().split(' ')[0];
                                    break;
                                }
                            }

                            if (!foundSrc && imgElement) {
                                const currentSrc = imgElement.currentSrc;
                                if (currentSrc && !currentSrc.startsWith('data:')) {
                                    foundSrc = currentSrc;
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

                                const anchorTexts = [];
                                const headingMatches = content.match(/<h[1-6][^>]*>([^<]+)<\\/h[1-6]>/g) || [];
                                for (const match of headingMatches) {
                                    const textMatch = match.match(/>([^<]+)</);
                                    if (textMatch) {
                                        anchorTexts.push(textMatch[1].trim());
                                    }
                                }

                                const picOuterHTML = pic.outerHTML;
                                const picPos = content.indexOf(picOuterHTML);

                                let prevText = '';
                                let nextText = '';
                                let prevDist = Infinity;
                                let nextDist = Infinity;

                                for (const anchor of anchorTexts) {
                                    const anchorPos = content.indexOf(anchor);
                                    if (anchorPos < 0) continue;

                                    if (anchorPos < picPos && picPos - anchorPos < prevDist) {
                                        prevDist = picPos - anchorPos;
                                        prevText = anchor;
                                    }
                                    if (anchorPos > picPos && anchorPos - picPos < nextDist) {
                                        nextDist = anchorPos - picPos;
                                        nextText = anchor;
                                    }
                                }

                                prevText = prevText.substring(0, 50);
                                nextText = nextText.substring(0, 50);

                                images.push({ url: foundSrc, prev_text: prevText, next_text: nextText });
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
                image_list: list[ImageData] = []
                for img in item.get("images", []):
                    url = img["url"] if isinstance(img, dict) else img
                    prev_text = img.get("prev_text", "") if isinstance(img, dict) else ""
                    next_text = img.get("next_text", "") if isinstance(img, dict) else ""
                    image_list.append(
                        ImageData(url=url, prev_text=prev_text, next_text=next_text)
                    )
                messages.append(
                    ChatMessage(role=item["role"], content=item["content"], images=image_list)
                )

            if not messages:
                messages = await self._extract_fallback(page)

        except Exception as e:
            self.logger.warning(f"消息提取失败，使用备用方法: {e}")
            messages = await self._extract_fallback(page)

        return messages

    async def _extract_fallback(self, page: "Page") -> list[ChatMessage]:
        """备用消息提取方法"""
        messages: list[ChatMessage] = []
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

    async def extract_all(self, page: "Page", url: str) -> ChatData:
        """提取完整的聊天数据"""
        title = await self.extract_title(page)
        messages = await self.extract_messages(page)
        raw_html = await page.content()

        return ChatData(url=url, title=title, messages=messages, raw_html=raw_html)
