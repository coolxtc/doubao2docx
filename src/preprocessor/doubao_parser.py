from typing import List

from bs4 import Tag

from .base import BaseParser, PlatformConfig, ParsedPage


class DoubaoHTMLParser(BaseParser):
    """豆包 HTML 解析器 - 实现平台特定的钩子方法"""
    
    config = PlatformConfig()
    
    def parse(self, html: str) -> ParsedPage:
        """解析 HTML 页面"""
        return self._parse_impl(html)
    
    def _get_title_selectors(self) -> List[str]:
        """获取豆包平台的标题选择器"""
        return self.config.heading_selectors.split(", ")
    
    def _is_math_element(self, element: Tag) -> bool:
        """判断元素是否为公式元素（通过 latex_attr 属性）"""
        return element.has_attr(self.config.latex_attr)
    
    def _is_display_math(self, element: Tag) -> bool:
        """判断元素是否为展示公式"""
        class_str = " ".join(element.get("class", []))
        return any(cls in class_str for cls in self.config.math_display_classes)
    
    def _is_code_container(self, element: Tag) -> bool:
        """判断元素是否为代码容器"""
        return self.config.code_container_class in element.get("class", [])
    
    def _is_paragraph_container(self, element: Tag) -> bool:
        """判断元素是否为段落容器"""
        return any(cls.startswith(self.config.paragraph_prefix) for cls in element.get("class", []))
    
    def _is_code_button(self, element: Tag) -> bool:
        """判断元素是否为代码展开按钮"""
        return any(cls.startswith(self.config.code_button_pattern) for cls in element.get("class", []))
    
    def _extract_latex_content(self, element: Tag) -> str:
        """从公式元素中提取 LaTeX 内容"""
        return element.get(self.config.latex_attr, "")
