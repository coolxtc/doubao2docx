# AGENTS.md - Doubao Export

## 快速开始

```bash
# 安装依赖（必须）
pip install -r requirements.txt

# 安装浏览器（必须）
playwright install chromium

# 运行导出
python -m src.cli <豆包链接>
```

## 关键命令

- `python3 -m src.cli <url>` - 主入口，Python 3 必须用 `python3`
- `make install` - 安装所有依赖（pip + playwright）
- `make run` - 默认运行（需要传 URL）

## 必须的环境配置

1. Python 3.10+
2. Playwright Chromium 浏览器 (`playwright install chromium`)
3. filelock>=3.13.0（随 requirements.txt 自动安装，用于文件锁）
4. 可选：pandoc（用于 LaTeX 公式转换）

## CLI 参数

| 参数 | 说明 | 默认 |
|------|------|------|
| `urls` | 豆包聊天页面 URL（支持多个） | - |
| `--level` | 反爬级别：low/medium/high | medium |
| `--index` | 手动指定文档序号（仅单URL） | 自动 |
| `--concurrency` | 批量导出并发数 | 5 |

## 输出位置

- 文档：`data/export/YYYYMMDD/*.docx`（按日期分类）
- 报告：批量导出完成后在终端直接打印，不保存文件
- 索引：`data/link_index.json`

## 项目结构

```
src/
├── cli.py           # 入口
├── config.py       # 配置
├── scraper/        # 爬虫（Playwright）
├── preprocessor/   # 解析（BeautifulSoup）
└── generator/     # 生成（python-docx）
    └── batch_report.py  # 批量导出报告
```

## 重要约束

- 使用 `python3` 而非 `python`（系统默认可能是 Python 2）
- 公式转换失败时使用 Unicode fallback
- 同一天同一 URL 再次导出不会增加序号
- Windows 平台已做资源清理兼容处理

## 已有注释风格

代码注释面向 Python 新手，详细解释概念和原理。保持这个风格。