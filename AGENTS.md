# AGENTS.md - Doubao Export

## 运行命令

```bash
pip install -r requirements.txt && playwright install chromium
python3 -m src.cli <豆包链接>        # 主入口
pip install -e . && doubao-export <url> # 安装后
```

## 项目结构

```
src/
├── cli.py              # 主入口：TaskManager（Rich Live）+ 批量调度
├── config.py           # 配置加载：YAML + 环境变量覆盖
├── exceptions.py       # CrawlerError / ParseError / ExportError
├── utils.py            # Windows 兼容性
├── scraper/            # Playwright 爬虫层
├── preprocessor/       # BeautifulSoup 解析层
└── generator/          # python-docx 生成层
```

## WHERE TO LOOK

| 任务 | 位置 | 关键类/函数 |
|------|------|-------------|
| 修改爬虫行为 | `src/scraper/` | `DoubaoSpider`, `PageActions` |
| 修改解析逻辑 | `src/preprocessor/` | `DoubaoHTMLParser`, `PlatformConfig` |
| 修改文档样式 | `src/generator/` | `DocxBuilder`, `DocumentConfig` |
| 修改配置项 | `config.yaml` | — |
| 修改入口参数 | `src/cli.py` | `argparse` |

## CODE MAP

| 符号 | 类型 | 位置 | 用途 |
|------|------|------|------|
| `DoubaoSpider` | 类 | `scraper/crawler.py` | 爬虫上下文管理器 |
| `DoubaoHTMLParser` | 类 | `preprocessor/doubao_parser.py` | HTML→TextBlock 解析器 |
| `DocxBuilder` | 类 | `generator/docx_builder.py` | TextBlock→Word 文档 |
| `DocNamer` | 类 | `generator/doc_namer.py` | 文件名+序号管理 |
| `FetchStep` | 枚举 | `scraper/steps.py` | 进度步骤定义 |
| `PlatformConfig` | dataclass | `preprocessor/base.py` | 平台差异配置 |
| `TaskManager` | 类 | `cli.py` | Rich Live 进度显示 |

## CONVENTIONS

- **注释风格**：面向 Python 新手，详细解释概念和原理
- **类型注解**：必须使用，禁止 `as any`
- **入口**：必须用 `python3 -m src.cli`（Windows 用 `py -3`）
- **配置优先级**：代码默认值 < YAML < 环境变量
- **环境变量命名**：`前缀_层级_键名`，全大写（如 `CRAWLER_PAGE_LOAD_TIMEOUT`）
- **进度步骤**：`FetchStep` 枚举 + `FETCH_STEP_NAMES` 映射

## ANTI-PATTERNS

- **禁止**：删除失败的测试使测试通过
- **禁止**：使用 `@ts-ignore` / `as any` 绕过类型检查
- **禁止**：空 `catch(e) {}` 吞掉异常
- **禁止**：修改代码后不验证（lsp_diagnostics + 运行测试）

## 批量导出流程

```
1. DocNamer 初始化 → 清理过期记录
2. 预扫描 link_index.json → 预分配序号
3. asyncio.Semaphore(concurrency) → 并发执行
4. BatchReport → 汇总报告
```

## 数据结构

- **TextBlock**: `type` (paragraph/latex/code/heading/list/table/blockquote/image), `content`, `language`, `items`
- **ChatData**: `url`, `title`, `messages[]`, `raw_html`
- **ChatMessage**: `role` (user/bot), `content` (HTML), `timestamp`, `images[]`
- **TableData**: `headers[]`, `rows[][]`, `header_bold[]`, `cell_bold[][]`

## 导出结构

- 文档：`data/export/YYYYMMDD/*.docx`
- 索引：`data/link_index.json`

## Windows 兼容性

| 函数 | 位置 | 用途 |
|------|------|------|
| `is_windows()` | `utils.py` | 检测平台 |
| `windows_compat_setup()` | `utils.py` | 过滤 ResourceWarning |
| `windows_compat_cleanup()` | `utils.py` | gc.collect() |

## 已知约束

1. **序号一致性**：同一天同一 URL 不增加序号（`threading.Lock`）
2. **公式 fallback**：pandoc 失败时使用 Unicode 替代
3. **预分配序号**：批量并发时预分配避免冲突
4. **Windows PowerShell**：需先运行 `chcp 65001`
