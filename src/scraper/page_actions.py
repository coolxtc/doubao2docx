"""页面交互操作模块"""

from typing import Any

from ..config import CrawlerConfig

SCROLL_TO_TOP_JS = "window.scrollTo(0, 0)"
SCROLL_TO_BOTTOM_JS = "window.scrollTo(0, document.body.scrollHeight)"

SCROLL_IMAGES_JS = """
() => {
    const imgs = document.querySelectorAll('picture img, img[class*="image"]');
    imgs.forEach(img => img.scrollIntoView({ behavior: 'instant', block: 'center' }));
}
"""

SCROLL_CODE_BUTTONS_JS = """
() => {
    document.querySelectorAll('div').forEach((div) => {
        if (div.textContent && div.textContent.includes('已生成代码')) {
            const btn = div.querySelector('[class*="button-"]');
            if (btn) div.scrollIntoView({ behavior: 'instant', block: 'center' });
        }
    });
}
"""

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
    def __init__(self, config: CrawlerConfig) -> None:
        self.config: CrawlerConfig = config

    async def scroll_all(self, page: Any) -> None:
        base_wait = self.config.scroll_wait_ms

        # 1. 回顶部
        await page.evaluate(SCROLL_TO_TOP_JS)
        await page.wait_for_timeout(base_wait)

        # 2. 触发懒加载图片
        imgs = await page.query_selector_all("picture img, img[class*='image']")
        for img in imgs:
            await img.scroll_into_view_if_needed()
        await page.wait_for_timeout(base_wait)

        # 3. 回顶部
        await page.evaluate(SCROLL_TO_TOP_JS)
        await page.wait_for_timeout(base_wait)

        # 4. 滚动代码按钮
        await page.evaluate(SCROLL_CODE_BUTTONS_JS)
        await page.wait_for_timeout(base_wait)

        # 5. 展开代码
        await page.evaluate(CLICK_EXPAND_BUTTONS_JS)
        await page.evaluate(INJECT_EXPANDED_CODE_JS)
        await page.wait_for_timeout(base_wait)

        # 6. 滚动到底部
        await page.evaluate(SCROLL_TO_BOTTOM_JS)
