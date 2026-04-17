"""页面交互操作"""

import asyncio
from typing import TYPE_CHECKING

from ..config import CrawlerConfig

if TYPE_CHECKING:
    from playwright.async_api import Page


class PageActions:
    """页面交互操作类
    
    封装页面滚动、代码块展开等交互操作。
    """

    def __init__(self, config: CrawlerConfig) -> None:
        self.config = config

    async def scroll_to_bottom(self, page: "Page") -> None:
        """滚动页面到最底部"""
        last_height = 0
        for _ in range(self.config.scroll_max_attempts):
            try:
                await asyncio.wait_for(
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)"),
                    timeout=self.config.scroll_timeout / 1000,
                )
            except asyncio.TimeoutError:
                break

            await page.wait_for_timeout(self.config.scroll_wait_ms)

            try:
                new_height = await asyncio.wait_for(
                    page.evaluate("document.body.scrollHeight"),
                    timeout=self.config.scroll_timeout / 1000,
                )
            except asyncio.TimeoutError:
                break

            if new_height == last_height:
                break
            last_height = new_height

    async def scroll_for_lazy_images(self, page: "Page") -> None:
        """滚动页面触发所有懒加载图片"""
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(1000)

        max_scroll_attempts = self.config.scroll_max_attempts * 2
        scroll_count = 0

        while scroll_count < max_scroll_attempts:
            scroll_count += 1

            all_imgs = await page.query_selector_all("picture img, img[class*='image']")

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

    async def _click_expand_buttons(self, page: "Page") -> None:
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

    async def expand_code_blocks(self, page: "Page") -> None:
        max_retries = self.config.code_expand_max_retries

        for attempt in range(max_retries):
            try:
                await self._click_expand_buttons(page)
                base_wait_ms = self.config.code_expand_base_ms
                extra_wait_ms = attempt * self.config.code_expand_extra_ms
                await page.wait_for_timeout(base_wait_ms + extra_wait_ms)

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

                if result["buttonsWithoutCode"] > 0 and result["codeBlocksFound"] == 0:
                    await self._click_expand_buttons(page)

                if result["injected"] > 0:
                    break
                elif result["codeBlocksFound"] == 0 and result["buttonsWithoutCode"] == 0:
                    break
                elif attempt == max_retries - 1 and result["injected"] == 0:
                    pass

            except Exception:
                pass