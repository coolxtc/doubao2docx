# AGENTS.md - Doubao Export

豆包聊天记录导出工具：爬取 → 解析 → 生成 Word。

## 运行命令

```bash
pip install -r requirements.txt && playwright install chromium
python3 -m src.cli <豆包链接>        # 主入口
pip install -e . && doubao-export <url> # 安装后
```

## 项目结构

```
src/
├── cli.py              # 主入口 + TaskManager
├── config.py           # 配置加载（YAML → dataclass）
├── exceptions.py       # CrawlerError / ParseError / ExportError
├── utils.py            # Windows 兼容性
├── scraper/            # Playwright 爬虫层
├── preprocessor/       # BeautifulSoup 解析层
└── generator/          # python-docx 生成层
```

## WHERE TO LOOK

| 任务 | 位置 | 关键类 |
|------|------|--------|
| 修改爬虫 | `src/scraper/` | `DoubaoSpider`, `PageActions` |
| 修改解析 | `src/preprocessor/` | `DoubaoHTMLParser`, `PlatformConfig` |
| 修改文档 | `src/generator/` | `DocxBuilder`, `DocumentConfig` |
| 修改配置 | `config.yaml` | — |
| 修改入口 | `src/cli.py` | argparse |

## CONVENTIONS

- **注释**：面向 Python 新手，解释"为什么"
- **类型注解**：必须使用
- **入口**：`python3 -m src.cli`
- **配置**：`config.yaml` 必需，无默认值

## ANTI-PATTERNS

- 禁止删除测试使测试通过
- 禁止 `as any` 绕过类型检查
- 禁止不验证（lsp_diagnostics）

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
