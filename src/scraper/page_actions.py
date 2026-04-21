"""页面交互操作模块"""

from typing import Any, Callable

from ..config import CrawlerConfig

CLICK_EXPAND_BUTTONS_JS = """
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
"""

INJECT_EXPANDED_CODE_JS = """
() => {
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
        for (let i = 0; i < 5 && nextSibling; i++) {
            if (nextSibling.classList && nextSibling.classList.contains('custom-code-block-container')) {
                const pre = nextSibling.querySelector('pre');
                if (pre) {
                    const hiddenPre = document.createElement('pre');
                    hiddenPre.style.display = 'none';
                    hiddenPre.setAttribute('data-expanded-code', 'true');
                    hiddenPre.textContent = pre.textContent;
                    container.appendChild(hiddenPre);
                }
                break;
            }
            nextSibling = nextSibling.nextElementSibling;
        }
    }
}
"""


class PageActions:
    """页面交互操作类"""

    def __init__(self, config: CrawlerConfig) -> None:
        self.config: CrawlerConfig = config

    async def scroll_step_by_step(self, page: Any) -> int:
        """通用逐屏滚动方法"""
        max_attempts = self.config.scroll_max_attempts
        scroll_count = 0
        last_height: int = 0

        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(self.config.scroll_wait_ms)
        last_height = await page.evaluate("document.body.scrollHeight")

        for _ in range(max_attempts):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(self.config.scroll_wait_ms)

            scroll_count += 1
            new_height: int = await page.evaluate("document.body.scrollHeight")

            if new_height == last_height:
                break

            last_height = new_height

        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(self.config.scroll_wait_ms)

        return scroll_count

    async def scroll_for_lazy_images(self, page: Any) -> None:
        """滚动触发懒加载图片"""
        base_wait = self.config.scroll_wait_ms
        max_attempts = self.config.scroll_max_attempts * 2

        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(base_wait)

        scroll_count = 0

        while scroll_count < max_attempts:
            scroll_count += 1

            all_imgs = await page.query_selector_all("picture img, img[class*='image']")

            for img in all_imgs:
                try:
                    await img.scroll_into_view_if_needed()
                    await page.wait_for_timeout(base_wait)
                except Exception:
                    pass

            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(base_wait)

            new_height: int = await page.evaluate("document.body.scrollHeight")

            prev_height: int | None = await page.evaluate("""
                () => {
                    if (!window._prev_scroll_height) return 0;
                    return window._prev_scroll_height;
                }
            """)

            if prev_height and new_height == prev_height:
                break

            await page.evaluate(f"window._prev_scroll_height = {new_height}")

        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(self.config.code_expand_settle_ms)

    async def scroll_all(
        self,
        page: Any,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        """统一滚动方法"""
        base_wait = self.config.scroll_wait_ms
        max_attempts = self.config.scroll_max_attempts * 2
        settle_wait = self.config.code_expand_settle_ms
        code_expand_retries = self.config.code_expand_max_retries

        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(base_wait)
        last_height: int = await page.evaluate("document.body.scrollHeight")

        scroll_count = 0
        stable_count = 0

        while scroll_count < max_attempts:
            scroll_count += 1

            if progress_callback:
                progress_callback(scroll_count, max_attempts)

            all_imgs = await page.query_selector_all("picture img, img[class*='image']")
            for img in all_imgs:
                try:
                    await img.scroll_into_view_if_needed()
                    await page.wait_for_timeout(base_wait)
                except Exception:
                    pass

            for _ in range(code_expand_retries):
                await self._click_expand_buttons(page)
                await page.wait_for_timeout(base_wait)
                await self._inject_expanded_code(page)

            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(base_wait)

            new_height: int = await page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                stable_count += 1
                if stable_count >= 2:
                    break
            else:
                stable_count = 0
            last_height = new_height

        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(settle_wait)

    async def _click_expand_buttons(self, page: Any) -> None:
        """点击代码展开按钮"""
        await page.evaluate(CLICK_EXPAND_BUTTONS_JS)

    async def _inject_expanded_code(self, page: Any) -> None:
        """将已展开的代码块注入到按钮容器"""
        await page.evaluate(INJECT_EXPANDED_CODE_JS)

    async def expand_code_blocks(self, page: Any) -> None:
        """展开代码块（带重试机制）"""
        max_retries = self.config.code_expand_max_retries

        for attempt in range(max_retries):
            try:
                await self._click_expand_buttons(page)

                base_wait_ms = self.config.code_expand_base_ms
                extra_wait_ms = attempt * self.config.code_expand_extra_ms
                await page.wait_for_timeout(base_wait_ms + extra_wait_ms)

                result: dict[str, int] = await page.evaluate("""
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
