"""
页面交互操作模块

提供页面自动化操作的 JavaScript 脚本和 Python 封装。
用于滚动页面、触发懒加载、展开代码块等操作。
"""

from typing import Any, Callable

from ..config import CrawlerConfig

# 滚动到页面顶部
SCROLL_TO_TOP_JS = "window.scrollTo(0, 0)"

# 滚动到页面底部
SCROLL_TO_BOTTOM_JS = "window.scrollTo(0, document.body.scrollHeight)"

# 滚动触发图片懒加载：将所有图片元素滚动到视口中央
SCROLL_IMAGES_JS = """
() => {
    const imgs = document.querySelectorAll('picture img, img[class*="image"]');
    imgs.forEach(img => img.scrollIntoView({ behavior: 'instant', block: 'center' }));
}
"""

# 点击展开代码按钮：查找包含"已生成代码"文本的按钮并点击
# 豆包页面中代码块默认折叠，需要点击按钮展开
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

# 注入展开代码：对于未自动展开的代码，手动创建展开标记
# 查找"已生成代码"按钮后的代码容器，将内容注入到按钮所在的 div 中
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
    页面交互操作类
    
    提供页面滚动、图片懒加载触发、代码块展开等自动化操作。
    """

    def __init__(self, config: CrawlerConfig) -> None:
        """
        初始化页面交互器
        
        Args:
            config: 爬虫配置，包含滚动等待时间等参数
        """
        self.config: CrawlerConfig = config

    async def scroll_all(self, page: Any, progress_callback: Callable[[str], None] | None = None) -> None:
        """
        执行完整的页面交互流程
        
        流程：滚动到顶部 → 触发图片懒加载 → 展开代码块 → 滚动到底部
        
        Args:
            page: Playwright 页面对象
            progress_callback: 进度回调函数
        """
        base_wait = self.config.scroll_wait_ms

        await page.evaluate(SCROLL_TO_TOP_JS)

        if progress_callback:
            progress_callback("加载图片")
        imgs = await page.query_selector_all("picture img, img[class*='image']")
        for img in imgs:
            await img.scroll_into_view_if_needed()
        await page.wait_for_timeout(base_wait)

        await page.evaluate(SCROLL_TO_TOP_JS)

        if progress_callback:
            progress_callback("展开代码")
        await page.evaluate(CLICK_EXPAND_BUTTONS_JS)
        await page.evaluate(INJECT_EXPANDED_CODE_JS)
        await page.wait_for_timeout(base_wait)

        await page.evaluate(SCROLL_TO_BOTTOM_JS)
