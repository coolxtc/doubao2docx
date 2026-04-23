# src/preprocessor/

## 模块职责

HTML → 结构化 TextBlock[]。插件化设计，支持多平台扩展。

## 关键模块

| 文件 | 类 | 用途 |
|------|-----|------|
| `base.py` | `BaseParser`, `PlatformConfig`, `TextBlock`, `InlineContent` | 基类 + 数据类型 |
| `doubao_parser.py` | `DoubaoHTMLParser` | 豆包平台实现 |

## 解析流程

```
HTML → BeautifulSoup → BaseParser._parse_impl()
    → 子类 _get_*_selectors() → TextBlock[]
```

## TextBlock 类型

`paragraph`, `latex`, `code`, `heading`, `list_item`, `table`, `blockquote`, `image`

## 钩子方法（子类必须实现）

| 方法 | 用途 |
|------|------|
| `_get_title_selectors()` | 标题选择器列表 |
| `_is_math_element()` | 判断公式元素 |
| `_is_display_math()` | 判断展示公式 |
| `_is_code_container()` | 判断代码容器 |
| `_is_paragraph_container()` | 判断段落容器 |
| `_is_code_button()` | 判断代码按钮 |
| `_extract_latex_content()` | 提取 LaTeX 内容 |
| `_is_image_element()` | 判断图片元素 |
| `_extract_image_url()` | 提取图片 URL |

## 扩展新平台

1. `PlatformConfig` 定义 CSS 选择器/属性名
2. 继承 `BaseParser`，实现抽象方法（`_is_*()`, `_extract_*()`）
3. 导出新解析器

## 导出

```python
from src.preprocessor import DoubaoHTMLParser, TextBlock, InlineContent
```
