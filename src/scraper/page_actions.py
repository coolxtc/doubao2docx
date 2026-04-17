"""
页面交互操作模块

本模块封装了 Playwright 页面对象的各种交互操作，
包括滚动、代码块展开等自动化行为。

核心功能：
1. scroll_to_bottom: 滚动页面到底部，加载所有历史消息
2. scroll_for_lazy_images: 滚动触发懒加载图片的加载
3. expand_code_blocks: 点击"已生成代码"按钮展开代码块
"""

import asyncio
from typing import TYPE_CHECKING

from ..config import CrawlerConfig

if TYPE_CHECKING:
    from playwright.async_api import Page


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

    async def scroll_to_bottom(self, page: "Page") -> None:
        """
        滚动页面到最底部

        豆包聊天页面采用无限滚动加载机制，
        需要滚动到页面底部才能加载出完整的历史消息。

        算法：
        1. 滚动到页面底部
        2. 等待新内容加载
        3. 检查页面高度是否变化
        4. 如果高度不变，说明已加载完成
        5. 如果高度变化，继续滚动
        """
        last_height = 0
        for _ in range(self.config.scroll_max_attempts):
            try:
                # 执行 JavaScript 滚动到页面底部
                await asyncio.wait_for(
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)"),
                    timeout=self.config.scroll_timeout / 1000,
                )
            except asyncio.TimeoutError:
                break

            # 等待新内容加载
            await page.wait_for_timeout(self.config.scroll_wait_ms)

            try:
                # 获取当前页面高度
                new_height = await asyncio.wait_for(
                    page.evaluate("document.body.scrollHeight"),
                    timeout=self.config.scroll_timeout / 1000,
                )
            except asyncio.TimeoutError:
                break

            # 高度不变，说明已到达底部
            if new_height == last_height:
                break
            last_height = new_height

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
        # 先回到顶部
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(1000)

        max_scroll_attempts = self.config.scroll_max_attempts * 2
        scroll_count = 0

        while scroll_count < max_scroll_attempts:
            scroll_count += 1

            # 获取所有图片元素
            all_imgs = await page.query_selector_all("picture img, img[class*='image']")

            # 滚动每个图片到可视区域
            for img in all_imgs:
                try:
                    await img.scroll_into_view_if_needed()
                    await page.wait_for_timeout(300)
                except Exception:
                    pass

            # 向下滚动一个视口高度
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(800)

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
        await page.wait_for_timeout(2000)

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