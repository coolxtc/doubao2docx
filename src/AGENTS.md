# src/

## 模块分层

```
cli.py          → 入口层：命令行解析 + TaskManager + asyncio 调度
    ↓
config.py       → 配置层：YAML → dataclass 配置对象
    ↓
scraper/        → Playwright 浏览器自动化
preprocessor/   → HTML → 结构化 TextBlock[]
generator/      → TextBlock[] → Word 文档
    ↑
exceptions.py  → 异常定义
utils.py        → Windows 兼容性
```

## 关键类

| 类 | 模块 | 用途 |
|------|------|------|
| `GlobalConfig` | `config.py` | 配置单例（`GlobalConfig.load()`） |
| `TaskManager` | `cli.py` | Rich Live 进度显示 |
| `DoubaoSpider` | `scraper/crawler.py` | 爬虫上下文管理器 |
| `DoubaoHTMLParser` | `preprocessor/doubao_parser.py` | HTML 解析器 |
| `DocxBuilder` | `generator/docx_builder.py` | Word 文档构建器 |
| `DocNamer` | `generator/doc_namer.py` | 文件名+序号管理 |
| `BrowserPool` | `scraper/pool.py` | 浏览器池（单浏览器多标签页） |

## 配置

`config.yaml` → `GlobalConfig.load()` → 各模块通过 `get_config()` 获取。

无默认值，缺少配置直接报错。

## 注释风格

**核心原则**：强类型风格，清晰严谨。

### 模块/类文档

一句话定位，不展开：

```python
"""豆包爬虫核心类"""

class DoubaoSpider:
    """
    豆包网页爬取器
    
    支持异步上下文管理器协议。
    """
```

### 方法文档

必须包含 Args / Returns / Raises：

```python
def fetch(self, url: str, max_retries: int = 3) -> ChatData:
    """
    爬取豆包聊天记录
    
    Args:
        url: 豆包聊天页面URL
        max_retries: 最大重试次数
    
    Returns:
        ChatData: 提取的聊天数据
    
    Raises:
        CrawlerError: URL无效或爬取失败
    """
```

### 变量注释

必须有，清晰说明含义：

```python
# 有序列表序号
self._list_counter: int = 0

# 上一个列表类型（"ul" 或 "ol"）
self._last_list_type: str | None = None

# 外部注入时由外部管理生命周期
self._owns_browser: bool = external_page is None
```

### dataclass 字段注释

每个字段必须有注释：

```python
@dataclass
class DocumentConfig:
    """Word 文档全局样式配置"""
    title: str = "豆包聊天记录"  # 文档标题
    author: str = "Doubao Export"  # 文档作者
    margin_left: float = 1.0  # 左边距（英寸）
    margin_right: float = 1.0  # 右边距
    font_name: str = "微软雅黑"  # 正文字体
```

### 局部函数注释

嵌套/局部函数必须有注释：

```python
def _set_math_chinese_font(self, math_element: Element, font_name: str) -> None:
    """
    设置数学公式中的中文字体
    
    Args:
        math_element: 数学公式 XML 元素
        font_name: 字体名称
    """
    W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

    def qn_m(tag: str) -> str:  # 构建 Math 命名空间标签
        return "{%s}%s" % (M_NS, tag)

    def qn_w(tag: str) -> str:  # 构建 Word 命名空间标签
        return "{%s}%s" % (W_NS, tag)

    def is_chinese(text: str) -> bool:  # 判断是否包含中文字符
        return any('\u4e00' <= c <= '\u9fff' for c in text)
```

### 局部变量注释

关键局部变量应有注释：

```python
def parse_table(self, table: Tag) -> Optional[TableData]:
    headers = []  # 表头文本列表
    rows = []    # 数据行列表
    header_bold = []  # 表头加粗标记
```

### 分支注释

关键分支逻辑应有注释：

```python
# 简单段落：直接提取文本
if not math_elements and not has_strong and not has_picture:
    ...

# 复杂段落：解析内联内容
# （进入 items 处理逻辑）

# 遇到新标题、切换列表类型或层级变化时重置计数器
if self._last_block_type == "heading" or self._last_list_level != level:
    self._list_counter = 0

# 已有记录：复用序号
if url in records and records[url].index > 0:
    ...
# 新记录：分配新序号
else:
    ...
```

格式：`# 简短说明`

## ANTI-PATTERNS (THIS PROJECT)

- **禁止删除测试使测试通过**
- **禁止 `as any` 绕过类型检查**
- **禁止空 catch 块**：`except: pass`
