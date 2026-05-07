"""页面交互操作（滚动、展开代码）"""

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from playwright.async_api import Page

from ..config import CrawlerConfig
from .steps import FetchStep

SCROLL_TO_TOP_JS = "window.scrollTo(0, 0)"
SCROLL_TO_BOTTOM_JS = "window.scrollTo(0, document.body.scrollHeight)"

# 滚动触发图片懒加载
SCROLL_IMAGES_JS = """
() => {
    const imgs = document.querySelectorAll('picture img, img[class*="image"]');
    imgs.forEach(img => img.scrollIntoView({ behavior: 'instant', block: 'center' }));
}
"""

# 点击展开代码按钮
CLICK_EXPAND_BUTTONS_JS = """
() => {
    document.querySelectorAll('div').forEach((div) => {
        if (div.querySelector('pre[data-expanded-code]')) return;
        if (div.textContent && div.textContent.includes('已生成代码')) {
            const btn = div.querySelector('[class*="button-"]');
            if (btn) {
                try { btn.click(); }
                catch (e) { btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window})); }
            }
        }
    });
}
"""

# 注入展开代码
INJECT_EXPANDED_CODE_JS = """
() => {
    document.querySelectorAll('div').forEach((div) => {
        if (div.querySelector('pre[data-expanded-code]')) return;
        const btn = div.querySelector('[class*="button-"]');
        if (!btn || !btn.textContent.includes('已生成代码')) return;
        let s = div.nextElementSibling;
        for (let i = 0; i < 5 && s; i++) {
            if (s.classList && s.classList.contains('custom-code-block-container')) {
                const pre = s.querySelector('pre');
                if (pre) {
                    const expanded = document.createElement('pre');
                    expanded.style.display = 'none';
                    expanded.setAttribute('data-expanded-code', 'true');
                    expanded.textContent = pre.textContent;
                    div.appendChild(expanded);
                }
                break;
            }
            s = s.nextElementSibling;
        }
    });
}
"""


class PageActions:
    """
    页面交互操作

    支持异步上下文管理器协议。
    """

    def __init__(self, config: CrawlerConfig) -> None:
        """
        初始化页面交互器

        Args:
            config: 爬虫配置，包含滚动等待时间等参数
        """
        self.config: CrawlerConfig = config

    async def scroll_all(self, page: "Page", progress_callback: Callable[[str], None] | None = None) -> None:
        """
        执行完整页面交互流程

        流程：滚动到顶部 → 触发图片懒加载 → 展开代码块 → 滚动到底部

        Args:
            page: Playwright 页面对象
            progress_callback: 进度回调函数
        """
        base_wait = self.config.scroll_wait_ms

        await page.evaluate(SCROLL_TO_TOP_JS)

        if progress_callback:
            progress_callback(FetchStep.LOADING_IMAGES.value)
        imgs = await page.query_selector_all("picture img, img[class*='image']")
        for img in imgs:
            await img.scroll_into_view_if_needed()
        await page.wait_for_timeout(base_wait)

        await page.evaluate(SCROLL_TO_TOP_JS)

        if progress_callback:
            progress_callback(FetchStep.EXPANDING_CODE.value)
        await page.evaluate(CLICK_EXPAND_BUTTONS_JS)
        await page.evaluate(INJECT_EXPANDED_CODE_JS)
        await page.wait_for_timeout(base_wait)

        await page.evaluate(SCROLL_TO_BOTTOM_JS)
