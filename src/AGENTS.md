# src/

## 模块分层

```
cli.py          → 入口层：命令行解析 + TaskManager + asyncio 调度
    ↓
config.py       → 配置层：YAML + 环境变量 → dataclass 配置对象
    ↓
scraper/        → 依赖层：Playwright 浏览器自动化
preprocessor/   → 转换层：HTML → 结构化 TextBlock[]
generator/      → 输出层：TextBlock[] → Word 文档
    ↑
exceptions.py  → 异常定义
utils.py        → Windows 兼容性工具
```

## 入口

```bash
python3 -m src.cli <url>        # 标准入口
python3 -m src                  # __main__.py 转发到 cli.main
```

## 关键类

| 类 | 模块 | 用途 |
|----|------|------|
| `TaskManager` | `cli.py` | Rich Live 表格进度显示 |
| `GlobalConfig` | `config.py` | 配置单例（YAML+环境变量） |
| `DoubaoSpider` | `scraper/crawler.py` | 爬虫上下文管理器 |
| `DoubaoHTMLParser` | `preprocessor/doubao_parser.py` | HTML 解析器 |
| `DocxBuilder` | `generator/docx_builder.py` | Word 文档构建器 |
| `DocNamer` | `generator/doc_namer.py` | 文件名+序号管理 |

## 注释风格

**面向 Python 新手**：详细解释概念和原理（"为什么这样做"），而非"做了什么"。

## 配置架构

```
代码默认值 → config.yaml → 环境变量
          (优先级递增)
```

环境变量命名：`前缀_层级_键名` 全大写（如 `CRAWLER_SCROLL_TIMEOUT`）。
