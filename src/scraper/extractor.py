"""
数据提取功能模块

本模块负责从 Playwright 页面中提取聊天数据。
使用 JavaScript 在页面上下文执行 DOM 查询，避免网络往返开销。

主要功能：
1. extract_title: 提取聊天标题
2. extract_messages: 提取消息列表（包括用户和 AI 的消息）
3. extract_all: 提取完整数据（标题 + 消息 + 原始 HTML）
"""

from typing import TYPE_CHECKING

from ..config import CrawlerConfig
from .models import ChatData, ChatMessage, ImageData

if TYPE_CHECKING:
    from playwright.async_api import Page


class DataExtractor:
    """
    数据提取器

    负责从页面中提取聊天标题、消息等内容。
    使用 page.evaluate() 在浏览器中执行 JavaScript 进行提取，
    然后将结果转换为 Python 数据对象。
    """

    def __init__(self, config: CrawlerConfig) -> None:
        self.config = config

    async def extract_title(self, page: "Page") -> str:
        """
        提取聊天标题

        尝试多个选择器，找到第一个匹配的元素并提取其文本。

        Returns:
            聊天标题，如果未找到则返回"未命名对话"
        """
        try:
            title_element = await page.query_selector("h1, .chat-title, [class*='title']")
            if title_element:
                return await title_element.inner_text()
        except Exception:
            pass
        return "未命名对话"

    async def extract_messages(self, page: "Page") -> list[ChatMessage]:
        """
        提取聊天消息列表

        核心提取逻辑在 JavaScript 中执行：
        1. 查找所有消息容器（[class*='message-item']）
        2. 根据 class 中的 'justify-end' 判断是用户还是 AI
        3. 提取消息的 innerHTML（保留格式）
        4. 查找已展开的代码块（pre[data-expanded-code]）
        5. 提取图片信息（URL 和上下文标题）

        Returns:
            消息对象列表
        """
        messages = []

        try:
            result = await page.evaluate("""
                () => {
                    const results = [];
                    // 查找所有消息容器
                    const messageBlocks = document.querySelectorAll("[class*='message-item']");

                    for (const block of messageBlocks) {
                        // 根据 class 判断角色：包含 'justify-end' 是用户消息
                        const classAttr = block.className || '';
                        const role = classAttr.includes('justify-end') ? 'user' : 'assistant';

                        // 提取消息内容（保留 HTML 格式）
                        let content = block.innerHTML;

                        // 附加已展开的代码块内容
                        const hiddenPres = block.querySelectorAll('pre[data-expanded-code]');
                        for (const pre of hiddenPres) {
                            content += pre.outerHTML;
                        }

                        // 提取图片信息
                        const images = [];
                        const seen = new Set();  // 用于去重
                        const pictureContainers = block.querySelectorAll('picture');

                        for (const pic of pictureContainers) {
                            const sources = pic.querySelectorAll('source');
                            const imgElement = pic.querySelector('img');

                            let foundSrc = '';

                            // 尝试从 source 元素获取 URL
                            for (const src of sources) {
                                const srcset = src.srcset || src.dataset.srcset;
                                if (srcset && !srcset.startsWith('data:')) {
                                    // srcset 格式: "url1 1x, url2 2x"，取第一个
                                    foundSrc = srcset.split(',')[0].trim().split(' ')[0];
                                    break;
                                }
                            }

                            // 尝试从 img.currentSrc 获取（懒加载图片加载后的地址）
                            if (!foundSrc && imgElement) {
                                const currentSrc = imgElement.currentSrc;
                                if (currentSrc && !currentSrc.startsWith('data:')) {
                                    foundSrc = currentSrc;
                                }
                            }

                            // 尝试从 dataset 或 src 获取
                            if (!foundSrc && imgElement) {
                                const src = imgElement.dataset.original || imgElement.dataset.src || imgElement.src;
                                if (src && !src.startsWith('data:')) {
                                    foundSrc = src;
                                }
                            }

                            if (foundSrc && !seen.has(foundSrc)) {
                                seen.add(foundSrc);

                                // 查找图片上下文中的标题（用于定位）
                                const anchorTexts = [];
                                const headingMatches = content.match(/<h[1-6][^>]*>([^<]+)<\\/h[1-6]>/g) || [];
                                for (const match of headingMatches) {
                                    const textMatch = match.match(/>([^<]+)</);
                                    if (textMatch) {
                                        anchorTexts.push(textMatch[1].trim());
                                    }
                                }

                                // 计算图片在内容中的位置
                                const picOuterHTML = pic.outerHTML;
                                const picPos = content.indexOf(picOuterHTML);

                                let prevText = '';
                                let nextText = '';
                                let prevDist = Infinity;
                                let nextDist = Infinity;

                                // 找到图片前后最近的标题
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

                                // 截断过长文本
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

            # 将 JavaScript 结果转换为 Python 对象
            for item in result:
                image_list = []
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

            # 如果没有提取到消息，尝试备用方法
            if not messages:
                messages = await self._extract_fallback(page)

        except Exception:
            messages = await self._extract_fallback(page)

        return messages

    async def _extract_fallback(self, page: "Page") -> list[ChatMessage]:
        """
        备用消息提取方法

        当主提取方法失败时（如页面结构变化），
        尝试用更通用的选择器提取文本内容。
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

    async def extract_all(self, page: "Page", url: str) -> ChatData:
        """
        提取完整的聊天数据

        依次调用标题、消息提取方法，并保存原始 HTML。

        Args:
            page: Playwright 页面对象
            url: 聊天页面的 URL

        Returns:
            包含所有数据的 ChatData 对象
        """
        title = await self.extract_title(page)
        messages = await self.extract_messages(page)
        raw_html = await page.content()

        return ChatData(url=url, title=title, messages=messages, raw_html=raw_html)
