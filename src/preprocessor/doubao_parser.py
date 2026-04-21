"""
豆包 HTML 解析器模块

继承自 BaseParser，实现豆包平台特定的钩子方法。

解析器架构说明：
- BaseParser: 提供通用的解析框架和公共方法
- DoubaoHTMLParser: 实现豆包平台特有的判断逻辑

钩子方法说明：
- _get_title_selectors: 标题选择器列表
- _is_math_element: 判断是否为公式元素
- _is_display_math: 判断是否为展示公式
- _is_code_container: 判断是否为代码容器
- _is_paragraph_container: 判断是否为段落容器
- _is_code_button: 判断是否为代码展开按钮
- _extract_latex_content: 提取 LaTeX 内容

这些方法都依赖于 PlatformConfig 中定义的平台特定参数，
使得解析器可以适应不同的网页结构。
"""

from typing import List

from bs4 import Tag

from .base import BaseParser, PlatformConfig, ParsedPage


class DoubaoHTMLParser(BaseParser):
    """
    豆包 HTML 解析器

    实现 BaseParser 中定义的抽象钩子方法，
    提供豆包平台特定的 HTML 解析逻辑。

    配置说明：
    - 使用默认的 PlatformConfig 实例
    - 所有平台特定参数都存储在 config 中
    """

    # 使用默认平台配置
    config = PlatformConfig()

    def parse(self, html: str) -> ParsedPage:
        """解析 HTML 页面"""
        return self._parse_impl(html)

    def _get_title_selectors(self) -> List[str]:
        """
        获取豆包平台的标题选择器

        Returns:
            CSS 选择器列表，如 ["h1", ".chat-title", "[class*='title']"]
        """
        return self.config.heading_selectors.split(", ")

    def _is_math_element(self, element: Tag) -> bool:
        """
        判断元素是否为公式元素

        通过检查元素是否包含 latex_attr 属性来判断。

        Args:
            element: HTML 元素

        Returns:
            True 如果包含公式
        """
        return element.has_attr(self.config.latex_attr)

    def _is_display_math(self, element: Tag) -> bool:
        """
        判断元素是否为展示公式

        通过检查元素的 class 是否包含展示公式的标记来判断。

        Args:
            element: HTML 元素

        Returns:
            True 如果是展示公式
        """
        classes = element.get("class") or []
        class_str = " ".join(c for c in classes) if isinstance(classes, list) else str(classes)
        return any(cls in class_str for cls in self.config.math_display_classes)

    def _is_code_container(self, element: Tag) -> bool:
        """
        判断元素是否为代码容器

        通过检查 class 是否包含代码容器标记来判断。

        Args:
            element: HTML 元素

        Returns:
            True 如果是代码容器
        """
        classes = element.get("class") or []
        return self.config.code_container_class in classes

    def _is_paragraph_container(self, element: Tag) -> bool:
        """判断元素是否为段落容器"""
        classes = element.get("class") or []
        if isinstance(classes, str):
            classes = classes.split()
        # 检查是否有任何 class 以段落前缀开头
        if any(isinstance(cls, str) and cls.startswith(self.config.paragraph_prefix) for cls in classes):
            return True
        # 处理转义引号问题：检查完整 class 字符串中是否包含段落前缀
        full_class_str = " ".join(c for c in classes)
        return self.config.paragraph_prefix in full_class_str

    def _is_code_button(self, element: Tag) -> bool:
        """
        判断元素是否为代码展开按钮

        通过检查 class 是否以按钮前缀开头来判断。

        Args:
            element: HTML 元素

        Returns:
            True 如果是代码按钮
        """
        classes = element.get("class") or []
        return any(isinstance(cls, str) and cls.startswith(self.config.code_button_pattern) for cls in classes)

    def _extract_latex_content(self, element: Tag) -> str:
        """
        从公式元素中提取 LaTeX 内容

        从元素的 latex_attr 属性中获取 LaTeX 源码。

        Args:
            element: 公式元素

        Returns:
            LaTeX 公式字符串
        """
        return str(element.get(self.config.latex_attr, ""))

    def _is_image_element(self, element: Tag) -> bool:
        """
        判断元素是否为图片元素

        通过检查元素的标签名是否为 picture 来判断。

        Args:
            element: HTML 元素

        Returns:
            True 如果是 picture 元素
        """
        return element.name == "picture"

    def _extract_image_url(self, element: Tag) -> str:
        """
        从 picture 元素中提取图片 URL

        优先级：
        1. source.srcset - 响应式图片资源
        2. img.currentSrc - 懒加载图片加载后的地址
        3. img.src - 备用图片地址

        Args:
            element: picture 元素

        Returns:
            图片 URL 字符串，如果提取失败则返回空字符串
        """
        # 1. 尝试从 source 元素获取 URL
        source = element.find("source")
        if source:
            srcset = source.get("srcset") or source.get("data-srcset")
            if srcset and isinstance(srcset, str) and not srcset.startswith("data:"):
                # srcset 格式: "url1 1x, url2 2x"，取第一个
                return srcset.split(",")[0].strip().split(" ")[0]

        # 2. 尝试从 img.currentSrc 获取（懒加载图片加载后的地址）
        img = element.find("img")
        if img:
            current_src = img.get("currentSrc")
            if current_src and isinstance(current_src, str) and not current_src.startswith("data:"):
                return current_src

            # 3. 尝试从 dataset 或 src 获取
            src = str(img.get("data-original") or img.get("data-src") or img.get("src") or "")
            if src and isinstance(src, str) and not src.startswith("data:"):
                return src

        return ""
