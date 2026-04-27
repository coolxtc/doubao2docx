# AGENTS.md - Doubao Export

**Generated:** 2026-04-27
**Commit:** 631a6d48
**Branch:** master

豆包聊天记录导出工具：爬取 → 解析 → 生成 Word。

## 运行命令

```bash
pip install -e . && playwright install chromium
python3 -m src.cli <豆包链接>        # 主入口
pip install -e . && doubao-export <url> # 安装后
```

## 项目结构

```
doubao-export/
├── src/
│   ├── cli.py              # 主入口 + TaskManager + asyncio
│   ├── config.py           # 配置加载（YAML → dataclass）
│   ├── exceptions.py       # CrawlerError / ParseError / ExportError
│   ├── utils.py            # Windows 兼容性
│   ├── scraper/            # Playwright 爬虫层
│   ├── preprocessor/       # BeautifulSoup 解析层
│   └── generator/          # python-docx 生成层
├── config.yaml              # 运行时配置（无默认值）
├── data/                   # 导出数据目录
└── pyproject.toml          # 项目元数据
```

## WHERE TO LOOK

| 任务 | 位置 | 关键类 |
|------|------|--------|
| 修改爬虫 | `src/scraper/` | `DoubaoSpider`, `BrowserPool`, `PageActions` |
| 修改解析 | `src/preprocessor/` | `DoubaoHTMLParser`, `BaseParser`, `PlatformConfig` |
| 修改文档 | `src/generator/` | `DocxBuilder`, `DocNamer` |
| 修改配置 | `config.yaml` | — |
| 修改入口 | `src/cli.py` | argparse, TaskManager |

## 核心设计模式

### 异步上下文管理器
所有资源管理类实现 `__aenter__/__aexit__` 协议：
```python
class BrowserManager:
    async def __aenter__(self): await self.start(); return self
    async def __aexit__(self, ...): await self.close()
```

### 浏览器池（单浏览器多标签页）
```python
pool = BrowserPool()  # 1个浏览器进程
page = await pool.acquire(concurrency)  # 获取页面
await pool.release(page)  # 归还（关闭标签页）
```

### 工厂模式
```python
create_anti_detect_middleware(level="medium")  # 反爬中间件
DoubaoHTMLParser(config=PlatformConfig())     # 解析器
```

## CONVENTIONS

- **注释**：面向 Python 新手，解释"为什么"
- **类型注解**：必须使用
- **入口**：`python3 -m src.cli`
- **配置**：`config.yaml` 必需，无默认值

## ANTI-PATTERNS (THIS PROJECT)

- **禁止删除测试使测试通过**
- **禁止 `as any` 绕过类型检查**
- **禁止不验证（lsp_diagnostics）**
- **禁止空 catch 块**：`except: pass`

## 批量导出流程

```
1. DocNamer 初始化 → 清理过期记录
2. 预扫描 link_index.json → 预分配序号
3. BrowserPool + Semaphore(concurrency) → 并发执行
4. BatchReport → 汇总报告
```

## 数据结构

- **TextBlock**: `type`, `content`, `language`, `items`
- **ChatData**: `url`, `title`, `messages[]`, `raw_html`
- **ChatMessage**: `role`, `content` (HTML), `timestamp`, `images[]`
- **TableData**: `headers[]`, `rows[][]`, `header_bold[]`, `cell_bold[][]`

## 导出结构

- 文档：`data/export/YYYYMMDD/*.docx`
- 索引：`data/link_index.json`

## 已知约束

1. 序号一致性：`threading.Lock`
2. 公式 fallback：pandoc → Unicode
3. 预分配序号：批量并发避免冲突
4. Windows：需先 `chcp 65001`

## NOTES

- pyproject.toml 无 linter/formatter 配置，依赖 AGENTS.md 约定
- scraper 模块支持 `external_page` 注入（BrowserPool 复用）
- preprocessor 使用钩子方法（`_is_*()`, `_extract_*()`）支持多平台

## 测试

### 运行测试

```bash
# 运行所有测试
python3 -m pytest tests/

# 运行单个测试文件
python3 -m pytest tests/test_base_extended.py -v

# 查看覆盖率
python3 -m pytest tests/ --cov=src --cov-report=term
```

### 测试覆盖率

| 模块 | 覆盖率 | 测试文件 |
|------|--------|---------|
| preprocessor/base.py | 79% | test_base_extended.py |
| scraper/page_actions.py | 100% | test_page_actions.py |
| scraper/extractor.py | 98% | test_extractor.py |
| scraper/crawler.py | 50% | test_crawler.py |
| generator/batch_report.py | 72% | test_batch_report.py |
| config.py | 90% | test_config.py |

### 测试模式

**MockParser 模式**（用于 base.py 扩展测试）：
```python
from src.preprocessor.base import BaseParser, PlatformConfig, TextBlock, InlineContent

class MockParser(BaseParser):
    def __init__(self):
        self.config = PlatformConfig()

    def _get_title_selectors(self):
        return ["h1"]

    def _is_math_element(self, element):
        return element.has_attr("copy-text")

    def _is_display_math(self, element):
        return "display" in (element.get("class") or [])

    def _is_code_container(self, element):
        return "code-container" in (element.get("class") or [])

    def _is_paragraph_container(self, element):
        return "paragraph" in (element.get("class") or [])

    def _is_code_button(self, element):
        return "button-" in (element.get("class") or [])

    def _extract_latex_content(self, element):
        return element.get("copy-text", "")

    def _is_image_element(self, element):
        return element.name == "picture"

    def _extract_image_url(self, element):
        return element.get("src", "")
```

**真实 HTML 结构**（来自 tests/test2.html）：
- 嵌套 ul：`ul > li > strong > ul > li`
- line-break div：`<div class="md-box-line-break">`
- header：`<h3 class="header-iWP5WJ">`

### 覆盖目标

| 模块 | 目标 |
|------|------|
| preprocessor/base.py | ≥75% |
| scraper/* | ≥50% |
| generator/* | ≥50% |
