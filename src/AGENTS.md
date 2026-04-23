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

面向 Python 新手：详细解释"为什么这样做"。

## ANTI-PATTERNS (THIS PROJECT)

- **禁止删除测试使测试通过**
- **禁止 `as any` 绕过类型检查**
- **禁止空 catch 块**：`except: pass`
