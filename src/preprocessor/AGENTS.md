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

## 扩展新平台

1. `PlatformConfig` 定义 CSS 选择器/属性名
2. 继承 `BaseParser`，实现抽象方法（`_is_*()`, `_extract_*()`）
3. 导出新解析器

## 导出

```python
from src.preprocessor import DoubaoHTMLParser, TextBlock, InlineContent
```
