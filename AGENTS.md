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

## CLI 参数

| 参数 | 说明 | 默认 |
|------|------|------|
| `urls` | 豆包聊天页面 URL（支持多个） | - |
| `--level` | 反爬级别：low/medium/high | medium |
| `--concurrency` | 批量并发数 | 5 |

## 项目结构

```
src/
├── __init__.py           # 包初始化
├── cli.py                # 入口，TaskManager（Rich Live 进度显示）
├── config.py             # 配置加载（YAML + 环境变量）
├── exceptions.py         # 自定义异常（CrawlerError, ParseError, ExportError）
├── scraper/              # 爬虫模块（Playwright）
│   ├── __init__.py       # 模块导出
│   ├── models.py         # 数据模型（ChatData, ChatMessage, ImageData）
│   ├── browser.py        # 浏览器生命周期管理
│   ├── crawler.py        # 爬虫核心类（DoubaoSpider）
│   ├── steps.py          # 步骤枚举和进度工具
│   ├── extractor.py       # 数据提取器
│   ├── page_actions.py   # 页面交互（滚动、展开代码）
│   └── anti_detect.py    # 反爬中间件
├── preprocessor/         # 解析模块（BeautifulSoup）
│   ├── __init__.py       # 模块导出
│   ├── base.py           # 解析器基类（BaseParser, PlatformConfig）
│   └── doubao_parser.py  # 豆包 HTML 解析器
└── generator/            # 生成模块（python-docx）
    ├── __init__.py       # 模块导出
    ├── docx_builder.py   # Word 文档构建器
    ├── latex_converter.py # LaTeX 公式转换器
    ├── doc_namer.py      # 文档命名器 + 序号管理
    └── batch_report.py    # 批量导出报告
```

## 进度显示（TaskManager）

```
0. 任务开始
1. 收到任务
2. 访问页面
3. 加载完成
4. 滚动加载
5. 展开代码
6. 提取数据
7. 爬取完成  ← FetchStep.COMPLETED
8. 解析内容
9. 生成文档
10. 完成      ← 文档生成完成
```

- 使用 **Rich Live** 动态刷新
- 非交互式终端自动降级为纯文本
- 管道模式下不显示进度动画

## 重要约束

1. **必须用 `python3`** 而非 `python`（避免 Python 2 问题）
2. **同一天同一 URL 不会增加序号**（通过 threading.Lock 保证）
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

## 已知问题

| 问题 | 说明 | 状态 |
|------|------|------|
| **缺少 `__main__.py`** | 无法使用 `python3 -m src` 运行 | 建议添加 |
| **pyproject.toml 无 scripts** | 未配置 `[project.scripts]`，无法安装后用命令运行 | 建议添加 |
| **README 提及 Makefile** | 文档与实际不符 | 需删除或创建 |

### 建议修复

1. 创建 `src/__main__.py`：
```python
from src.cli import main
if __name__ == "__main__":
    raise SystemExit(main())
```

2. pyproject.toml 添加：
```toml
[project.scripts]
doubao-export = "src.cli:main"
```

3. 删除 README 中 Makefile 相关描述
