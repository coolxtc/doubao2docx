"""数据提取功能模块"""

from typing import Any

from ..config import CrawlerConfig
from .models import ChatData, ChatMessage, ImageData


class DataExtractor:
    """数据提取器"""

    def __init__(self, config: CrawlerConfig) -> None:
        self.config: CrawlerConfig = config

    async def extract_title(self, page: Any) -> str:
        """提取聊天标题"""
        try:
            title_element = await page.query_selector("h1, .chat-title, [class*='title']")
            if title_element:
                return await title_element.inner_text()
        except Exception:
            pass
        return "未命名对话"

    async def extract_messages(self, page: Any) -> list[ChatMessage]:
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

        except Exception:
            messages = await self._extract_fallback(page)

        return messages

    async def _extract_fallback(self, page: Any) -> list[ChatMessage]:
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

    async def extract_all(self, page: Any, url: str) -> ChatData:
        """提取完整的聊天数据"""
        title = await self.extract_title(page)
        messages = await self.extract_messages(page)
        raw_html = await page.content()

        return ChatData(url=url, title=title, messages=messages, raw_html=raw_html)
