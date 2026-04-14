# AGENTS.md - Doubao Export

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 安装浏览器（必须）
playwright install chromium

# 运行
python3 -m src.cli <豆包链接>
```

## 关键命令

| 命令 | 说明 |
|------|------|
| `python3 -m src.cli <url>` | 主入口 |
| `pip install -r requirements.txt` | 安装依赖 |
| `playwright install chromium` | 安装浏览器 |

## 环境要求

- Python 3.10+
- Playwright Chromium 浏览器
- 可选：pandoc（公式转换）

## 配置

`config.yaml` 支持配置项和同名环境变量覆盖：

| 配置 | 环境变量 | 说明 |
|------|----------|------|
| `crawler.timeout` | `CRAWLER_TIMEOUT` | 请求超时(ms) |
| `crawler.scroll_max_attempts` | `CRAWLER_SCROLL_MAX_ATTEMPTS` | 最大滚动次数 |
| `crawler.browser_close_delay` | - | 浏览器关闭延迟(s) |
| `index.lock_timeout` | `INDEX_LOCK_TIMEOUT` | 文件锁超时(s) |

## CLI 参数

| 参数 | 说明 | 默认 |
|------|------|------|
| `urls` | 豆包聊天页面 URL（支持多个） | - |
| `--level` | 反爬级别：low/medium/high | medium |
| `--index` | 手动指定序号（仅单URL） | 自动 |
| `--concurrency` | 批量并发数 | 5 |

## 项目结构

```
src/
├── cli.py           # 入口，TaskManager（Rich Live 进度显示）
├── config.py        # 配置加载（YAML + 环境变量）
├── exceptions.py    # 自定义异常
├── scraper/         # 爬虫（Playwright）
│   └── crawler.py  # FetchStep 枚举、8步进度回调
├── preprocessor/    # 解析（BeautifulSoup）
│   └── doubao_parser.py
└── generator/      # 生成（python-docx）
    ├── docx_builder.py   # 文档构建
    ├── latex_converter.py # LaTeX 公式转换
    └── doc_namer.py     # 文件命名 + FileLock
```

## 进度显示（TaskManager）

```
0. 任务开始
1. 收到任务
2. 访问页面
3. 页面加载完成
4. 滚动加载
5. 展开代码块
6. 提取数据
7. 爬取完成  ← FetchStep.COMPLETED
8. 完成      ← 文档生成完成
```

- 使用 **Rich Live** 动态刷新
- 非交互式终端自动降级为纯文本
- 管道模式下不显示进度动画

## 重要约束

1. **必须用 `python3`** 而非 `python`（避免 Python 2 问题）
2. **同一天同一 URL 不会增加序号**（通过 FileLock 保证）
3. **公式转换失败时使用 Unicode fallback**
4. **Windows 兼容性已处理**：gc.collect()、browser_close_delay、ResourceWarning 过滤

## 注释风格

代码注释面向 Python 新手，详细解释概念和原理。新增代码应保持此风格。

## preprocessor 模块导出

```python
from src.preprocessor import (
    BaseParser, PlatformConfig, DoubaoHTMLParser,
    TableData, InlineContent, TextBlock, ParsedPage
)
```

## 导出结构

- 文档：`data/export/YYYYMMDD/*.docx`
- 索引：`data/link_index.json`
