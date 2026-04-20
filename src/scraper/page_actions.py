"""
页面交互操作模块

本模块封装了 Playwright 页面对象的各种交互操作，
包括滚动、代码块展开等自动化行为。

核心功能：
1. scroll_step_by_step: 通用逐屏滚动方法（按 viewport 逐屏滚动直到页面底部）
2. scroll_for_lazy_images: 滚动触发懒加载图片的加载
3. scroll_all: 统一滚动方法
"""

from typing import TYPE_CHECKING, Callable

from ..config import CrawlerConfig

if TYPE_CHECKING:
    from playwright.async_api import Page
    fromCallable = Callable[[int, int], None]


class PageActions:
    """
    页面交互操作类

    封装页面滚动、代码块展开等交互操作。
    所有方法都是异步的，需要在 async 函数中调用。

    工作原理：
    - 使用 Playwright 的 page.evaluate() 执行 JavaScript
    - 使用 page.wait_for_timeout() 等待页面渲染
    - 通过配置控制滚动次数和等待时间
    """

    def __init__(self, config: CrawlerConfig) -> None:
        """
        初始化页面操作器

        Args:
            config: 爬虫配置，包含超时时间、滚动次数等参数
        """
        self.config = config

    async def scroll_step_by_step(self, page: "Page") -> int:
        """
        通用逐屏滚动方法，按 viewport 逐屏滚动直到页面底部

        算法：
        1. 记录初始页面高度
        2. 向下滚动一个视口高度
        3. 等待内容加载
        4. 检查页面高度是否变化
        5. 如果高度不变或达到最大次数，停止滚动

        Returns:
            实际滚动的次数
        """
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
        """
        滚动页面触发所有懒加载图片

        豆包页面中的图片采用懒加载机制，
        只有滚动到可视区域才会开始加载。
        此方法确保所有图片都被加载后再提取内容。

        算法：
        1. 回到页面顶部
        2. 遍历所有图片元素，滚动使其可见
        3. 继续向下滚动
4. 重复直到页面高度不再变化
        """
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
        """
        统一滚动方法：一次逐屏滚动同时处理历史消息加载、图片懒加载、代码块展开

        在逐屏滚动到底的过程中：
        1. 滚动每个图片到可视区域，触发懒加载
        2. 检查并点击代码展开按钮
        3. 检查页面高度变化

        合并了 scroll_to_bottom + scroll_for_lazy_images + expand_code_blocks 的逻辑，
        减少页面滚动次数。

        Args:
            page: Playwright 页面对象
            progress_callback: 进度回调函数，签名 (current: int, total: int)，每次滚动后调用
        """
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
        """
        点击代码展开按钮

        豆包页面中，AI 生成的代码默认是折叠的，
        需要点击"已生成代码"按钮才能展开显示完整代码。

        实现：
        1. 查找所有包含"已生成代码"文本的容器
        2. 在容器中查找按钮元素
        3. 点击按钮触发展开
        """
        await page.evaluate("""
            () => {
                const containers = document.querySelectorAll('div');
                for (const container of containers) {
                    // 跳过已经有展开代码的容器
                    if (container.querySelector('pre[data-expanded-code]')) {
                        continue;
                    }
                    // 查找包含"已生成代码"的容器
                    if (container.textContent && container.textContent.includes('已生成代码')) {
                        const button = container.querySelector('[class*="button-"]');
                        if (button) {
                            try {
                                button.click();
                            } catch (e) {
                                // 备用：手动触发点击事件
                                const event = new MouseEvent('click', {bubbles: true, cancelable: true, view: window});
                                button.dispatchEvent(event);
                            }
                        }
                    }
                }
            }
        """)

    async def _inject_expanded_code(self, page: "Page") -> None:
        await page.evaluate("""
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
        """)

    async def expand_code_blocks(self, page: "Page") -> None:
        """
        展开代码块（带重试机制）

        由于代码块可能是动态加载的，需要多次尝试展开。
        每次尝试：
        1. 点击展开按钮
        2. 等待代码加载
        3. 将已加载的代码注入到按钮容器中（标记为 data-expanded-code）
        4. 检查是否成功展开

        退出条件：
        - 成功注入代码（injected > 0）
        - 没有找到更多可展开的按钮
        - 达到最大重试次数
        """
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