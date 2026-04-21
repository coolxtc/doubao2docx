"""
页面交互操作模块

封装 Playwright 页面对象的各种交互操作，包括滚动、代码块展开等。
"""

from typing import TYPE_CHECKING, Callable

from ..config import CrawlerConfig

if TYPE_CHECKING:
    from playwright.async_api import Page
    fromCallable = Callable[[int, int], None]

# 内联 JavaScript 代码常量 - 便于维护和调试
# 点击代码展开按钮
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

# 将已展开的代码块注入到按钮容器
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
    """页面交互操作类

    封装页面滚动、代码块展开等交互操作，所有方法都是异步的。
    """

    def __init__(self, config: CrawlerConfig) -> None:
        """初始化页面操作器"""
        self.config = config

    async def scroll_step_by_step(self, page: "Page") -> int:
        """通用逐屏滚动方法"""
        max_attempts = self.config.scroll_max_attempts
        scroll_count = 0
        last_height = 0

        # 初始化：先滚动到顶部确保从起点开始
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(self.config.scroll_wait_ms)
        last_height = await page.evaluate("document.body.scrollHeight")

        for _ in range(max_attempts):
            # 向下滚动一个视口高度
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(self.config.scroll_wait_ms)

            scroll_count += 1
            new_height = await page.evaluate("document.body.scrollHeight")

            # 页面高度不再变化，说明已到底部
            if new_height == last_height:
                break

            last_height = new_height

        # 滚动到最底部确保完整加载
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(self.config.scroll_wait_ms)

        return scroll_count

    async def scroll_for_lazy_images(self, page: "Page") -> None:
        """滚动触发懒加载图片"""
        base_wait = self.config.scroll_wait_ms
        max_attempts = self.config.scroll_max_attempts * 2

        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(base_wait)

        scroll_count = 0

        while scroll_count < max_attempts:
            scroll_count += 1

            # 获取所有图片元素
            all_imgs = await page.query_selector_all("picture img, img[class*='image']")

            # 滚动每个图片到可视区域
            for img in all_imgs:
                try:
                    await img.scroll_into_view_if_needed()
                    await page.wait_for_timeout(base_wait)
                except Exception:
                    pass

            # 向下滚动一个视口高度
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(base_wait)

            new_height = await page.evaluate("document.body.scrollHeight")

            # 检查页面高度是否变化
            prev_height = await page.evaluate("""
                () => {
                    if (!window._prev_scroll_height) return 0;
                    return window._prev_scroll_height;
                }
            """)

            if prev_height and new_height == prev_height:
                break

            # 记录当前高度
            await page.evaluate(f"window._prev_scroll_height = {new_height}")

        # 滚动到底部
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(self.config.code_expand_settle_ms)

    async def scroll_all(
        self,
        page: "Page",
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        """统一滚动方法"""
        base_wait = self.config.scroll_wait_ms
        max_attempts = self.config.scroll_max_attempts * 2
        settle_wait = self.config.code_expand_settle_ms
        code_expand_retries = self.config.code_expand_max_retries

        # 初始化：滚动到顶部
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(base_wait)
        last_height = await page.evaluate("document.body.scrollHeight")

        scroll_count = 0
        stable_count = 0

        while scroll_count < max_attempts:
            scroll_count += 1

            if progress_callback:
                progress_callback(scroll_count, max_attempts)

            # 1. 触发当前可见的图片（scroll_for_lazy_images 逻辑）
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

            # 3. 向下滚动一个视口高度
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(base_wait)

            # 4. 检查页面高度是否变化
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                stable_count += 1
                if stable_count >= 2:
                    break
            else:
                stable_count = 0
            last_height = new_height

        # 滚动到底部
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(settle_wait)

    async def _click_expand_buttons(self, page: "Page") -> None:
        """点击代码展开按钮"""
        await page.evaluate(CLICK_EXPAND_BUTTONS_JS)

    async def _inject_expanded_code(self, page: "Page") -> None:
        """将已展开的代码块注入到按钮容器"""
        await page.evaluate(INJECT_EXPANDED_CODE_JS)

    async def expand_code_blocks(self, page: "Page") -> None:
        """展开代码块（带重试机制）"""
        max_retries = self.config.code_expand_max_retries

        for attempt in range(max_retries):
            try:
                # 点击所有展开按钮
                await self._click_expand_buttons(page)

                # 等待时间递增：基础等待 + 额外等待（每次重试增加）
                base_wait_ms = self.config.code_expand_base_ms
                extra_wait_ms = attempt * self.config.code_expand_extra_ms
                await page.wait_for_timeout(base_wait_ms + extra_wait_ms)

                # 检查代码块展开情况
                result = await page.evaluate("""
                    () => {
                        let injected = 0;         // 本次注入的代码块数
                        let codeBlocksFound = 0;  // 找到的代码块容器数
                        let buttonsWithoutCode = 0; // 有按钮但找不到代码的容器数
                        const containers = document.querySelectorAll('div');

                        for (const container of containers) {
                            // 跳过已有展开代码的容器
                            if (container.querySelector('pre[data-expanded-code]')) {
                                continue;
                            }

                            // 查找"已生成代码"按钮
                            const button = container.querySelector('[class*="button-"]');
                            if (!button || !button.textContent.includes('已生成代码')) {
                                continue;
                            }

                            // 在按钮后续元素中查找代码块容器
                            let nextSibling = container.nextElementSibling;
                            let foundCodeBlock = false;

                            for (let i = 0; i < 5 && nextSibling; i++) {
                                if (nextSibling.classList && nextSibling.classList.contains('custom-code-block-container')) {
                                    foundCodeBlock = true;
                                    codeBlocksFound++;
                                    // 找到代码块，提取内容并注入到按钮容器
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

                # 如果有按钮但没找到代码，再尝试点击一次
                if result["buttonsWithoutCode"] > 0 and result["codeBlocksFound"] == 0:
                    await self._click_expand_buttons(page)

                # 判断是否继续
                if result["injected"] > 0:
                    break  # 成功展开，退出
                elif result["codeBlocksFound"] == 0 and result["buttonsWithoutCode"] == 0:
                    break  # 没有更多可展开的内容
                elif attempt == max_retries - 1 and result["injected"] == 0:
                    pass  # 最后一次重试

            except Exception:
                pass
