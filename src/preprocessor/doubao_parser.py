"""豆包 HTML 解析器"""

from typing import List

from bs4 import Tag

import re

from ..config import get_config
from .base import BaseParser, PlatformConfig, ParsedPage


class DoubaoHTMLParser(BaseParser):
    """豆包平台 HTML 解析器"""

    def __init__(self, config: PlatformConfig | None = None) -> None:
        """
        初始化豆包解析器

        Args:
            config: 平台配置，默认使用 PlatformConfig()
        """
        if config is None:
            cfg = get_config()
            config = PlatformConfig(latex_attr=cfg.parser.latex_attr)
        self.config = config
        self._latex_fallback_count: int = 0  # LaTeX 解析失败次数（用于统计）

    def parse(self, html: str) -> ParsedPage:
        """
        解析 HTML 页面

        Args:
            html: HTML 字符串

        Returns:
            ParsedPage: 解析结果
        """
        self._latex_fallback_count = 0
        page = self._parse_impl(html)
        page.latex_fallback_count = self._latex_fallback_count
        return page

    def _get_title_selectors(self) -> List[str]:
        """
        获取标题选择器列表

        Returns:
            CSS 选择器列表
        """
        return self.config.heading_selectors.split(", ")

    def _is_math_element(self, element: Tag) -> bool:
        """
        判断元素是否为公式元素

        多策略检测：copy-text 属性 → math-inline/math-display 类名

        Args:
            element: HTML 元素

        Returns:
            True 如果包含公式
        """
        # 检查 latex_attr 属性
        if element.has_attr(self.config.latex_attr):
            return True
        if self._has_math_class(element):
            return True
        return False

    def _has_math_class(self, element: Tag) -> bool:
        """
        检查元素是否包含数学公式相关的 CSS 类名

        Args:
            element: HTML 元素

        Returns:
            True 如果包含数学类名
        """
        classes = element.get("class") or []
        class_str = " ".join(classes) if isinstance(classes, list) else str(classes)

        math_classes = ["math-inline", "math-display", "math-block"]
        if any(cls in class_str for cls in math_classes):
            return True

        return False

    def _is_display_math(self, element: Tag) -> bool:
        """
        判断元素是否为展示公式

        Args:
            element: HTML 元素

        Returns:
            True 如果是展示公式
        """
        # 获取元素的 CSS 类名列表
        classes = element.get("class") or []
        class_str = " ".join(c for c in classes) if isinstance(classes, list) else str(classes)
        return any(cls in class_str for cls in self.config.math_display_classes)

    def _is_code_container(self, element: Tag) -> bool:
        """
        判断元素是否为代码容器

        Args:
            element: HTML 元素

        Returns:
            True 如果是代码容器
        """
        # 获取元素的 CSS 类名列表
        classes = element.get("class") or []
        return self.config.code_container_class in classes

    def _is_paragraph_container(self, element: Tag) -> bool:
        """
        判断元素是否为段落容器

        Args:
            element: HTML 元素

        Returns:
            True 如果是段落容器
        """
        # 获取元素类名，支持字符串和列表两种格式
        classes = element.get("class") or []
        if isinstance(classes, str):
            classes = classes.split()
        if any(isinstance(cls, str) and cls.startswith(self.config.paragraph_prefix) for cls in classes):
            return True
        full_class_str = " ".join(c for c in classes)
        return self.config.paragraph_prefix in full_class_str

    def _is_code_button(self, element: Tag) -> bool:
        """
        判断元素是否为代码展开按钮

        Args:
            element: HTML 元素

        Returns:
            True 如果是代码按钮
        """
        # 获取元素类名，检测是否包含代码按钮样式
        classes = element.get("class") or []
        return any(isinstance(cls, str) and cls.startswith(self.config.code_button_pattern) for cls in classes)

    def _extract_latex_content(self, element: Tag) -> str:
        """
        从公式元素中提取 LaTeX 内容

        策略：latex_attr 属性 → 扫描所有属性搜索 LaTeX 格式

        Args:
            element: 公式元素

        Returns:
            LaTeX 公式字符串
        """
        # 策略1：优先从 latex_attr 属性提取
        if element.has_attr(self.config.latex_attr):
            latex = str(element.get(self.config.latex_attr, ""))
            return re.sub(r'\\tag\{[^}]*\}', '', latex)

        # 策略2：扫描所有属性搜索 LaTeX 格式
        for attr_name, attr_value in element.attrs.items():
            if not isinstance(attr_value, str):
                continue
            match = re.search(r'(\\\(.+?\\\)|\\\[.+?\\\]|\$\$.+?\$\$)', attr_value)
            if match:
                self._latex_fallback_count += 1
                latex = match.group(1)
                return re.sub(r'\\tag\{[^}]*\}', '', latex)

        # 策略3：回退到文本内容
        return element.get_text(strip=True)

    def _is_image_element(self, element: Tag) -> bool:
        """
        判断元素是否为图片元素

        Args:
            element: HTML 元素

        Returns:
            True 如果是 picture 元素
        """
        return element.name == "picture"

    def _extract_image_url(self, element: Tag) -> str:
        """
        从 picture 元素中提取图片 URL

        优先级：source.srcset → img.currentSrc → img.src

        Args:
            element: picture 元素

        Returns:
            图片 URL 字符串
        """
        # 优先从 source.srcset 提取
        source = element.find("source")
        if source:
            srcset = source.get("srcset") or source.get("data-srcset")
            if srcset and isinstance(srcset, str) and not srcset.startswith("data:"):
                return srcset.split(",")[0].strip().split(" ")[0]

        # 回退到 img 标签
        img = element.find("img")
        if img:
            # 优先使用 currentSrc
            current_src = img.get("currentSrc")
            if current_src and isinstance(current_src, str) and not current_src.startswith("data:"):
                return current_src

            # 最后回退到 src 属性
            src = str(img.get("data-original") or img.get("data-src") or img.get("src") or "")
            if src and isinstance(src, str) and not src.startswith("data:"):
                return src

        return ""
