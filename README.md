# Doubao Export

## 豆包聊天记录导出工具

一款帮助您将豆包 AI 助手中的聊天记录导出为格式规范的 Word 文档的工具。无论您是想保存重要的对话内容、整理学习笔记，还是备份工作资料，这款工具都能帮您轻松完成。

---

## 为什么需要这个工具

在使用豆包 AI 助手的过程中，您可能遇到过这些情况：

- **想保存重要对话**：与 AI 的讨论内容很有价值，想要长期保存
- **需要离线查看**：不想每次查看都登录网页版
- **格式整理需求**：希望将对话整理成规范的文档，方便打印或分享
- **内容复用**：想把自己满意的 AI 回复复制到其他场景使用

这个工具可以自动完成这些工作：访问您的豆包聊天页面，提取对话内容，转换为格式规范的 Word 文档。

---

## 功能特性

| 功能 | 说明 |
|------|------|
| 自动爬取 | 自动访问豆包聊天页面，提取完整对话内容 |
| 智能解析 | 支持解析多种内容类型，包括数学公式、代码块、表格等 |
| 格式转换 | 将解析后的内容转换为规范的 Word 文档 |
| 反爬适配 | 内置反检测机制，适配豆包的防爬措施 |
| 自动命名 | 自动生成规范的文件名，包含日期和序号 |
| 历史记录 | 自动维护已导出文档的索引，避免重复导出 |
| 代码块展开 | 自动点击展开隐藏的代码块，确保代码完整导出 |
| 进度日志 | 实时显示各阶段进度（启动浏览器→爬取→解析→生成），方便追踪 |

### 支持解析的内容类型

- **数学公式**：支持 LaTeX 格式的公式，转换为 Word 原生公式显示
- **代码块**：保留代码内容，带灰色背景显示
- **表格**：完整保留表格结构和数据
- **标题**：支持多级标题
- **列表**：支持有序列表和无序列表
- **引用**：保留引用格式

---

## 技术原理（通俗说明）

整个工具的工作流程可以想象成一条"流水线"：

```
豆包网页 → 爬虫抓取 → 内容解析 → 格式转换 → Word文档
```

**第一步：爬虫抓取（类似模拟浏览器）**

程序使用一个"自动化浏览器"来访问豆包网页。这个浏览器可以自动滚动页面、加载更多内容、展开折叠的内容，就像您手动操作一样。它会模拟真实用户的访问行为，因此能够获取到完整的聊天记录。

**第二步：内容解析（类似翻译工作）**

从网页获取的是 HTML 格式（网页的"源代码"），需要解析成结构化的数据。程序会识别网页中的各种元素：哪里是标题、哪里是代码、哪里是公式、哪里是表格。这个过程类似于把一篇混排的文章整理成结构化的笔记。

**第三步：格式转换（类似排版工作）**

根据解析后的结构，使用 Word 文档库创建对应的内容：标题用标题样式、代码用等宽字体加灰色背景、表格用 Word 表格样式。特别地，数学公式会通过 pandoc 工具转换为 Word 的原生公式格式，可以在 Word 中直接编辑。

**第四步：保存文档**

将生成的 Word 文档保存到指定目录，同时更新索引文件记录这次导出。

---

## 环境准备

在开始安装之前，请确认您的电脑上具备以下条件：

### 1. Python 环境

工具需要 Python 3.10 或更高版本。您可以通过以下命令检查：

```bash
python3 --version
```

如果没有安装，推荐通过以下方式安装：

- **macOS**：推荐使用 Homebrew 安装
  ```bash
  brew install python3
  ```
- **Windows**：从 [Python 官网](https://www.python.org/downloads/) 下载安装
- **Linux**：大多数发行版已预装，或使用包管理器安装

### 2. 必要软件

| 软件 | 用途 | 安装方式 |
|------|------|----------|
| pip | Python 包管理器 | 随 Python 安装 |
| Playwright | 自动化浏览器 | 后续步骤安装 |
| pandoc | 公式转换工具 | 可选，但推荐安装 |

#### 安装 pandoc（macOS）

```bash
brew install pandoc
```

#### 安装 pandoc（Windows）

从 [pandoc 官网](https://pandoc.org/installing.html) 下载安装包，或使用 wingdo：

```bash
winget install pandoc.pandoc
```

---

## 安装步骤

### 第一步：获取项目代码

如果还没有获取项目代码，请先下载或克隆：

```bash
git clone <项目地址>
cd doubao-export
```

或者直接使用已有的项目文件夹。

### 第二步：安装 Python 依赖

在项目根目录下执行：

```bash
pip install -r requirements.txt
```

这会安装以下依赖包：

- **playwright**：自动化浏览器，用于抓取网页
- **python-docx**：Word 文档操作库
- **beautifulsoup4**：HTML 解析库
- **lxml**：XML/HTML 解析器
- **pytest**：测试框架（可选）

### 第三步：安装 Playwright 浏览器

Playwright 需要安装浏览器内核。执行：

```bash
playwright install chromium
```

这个命令会下载并安装 Chromium 浏览器（约 100MB）。安装完成后，环境就准备好了。

### 验证安装

可以通过以下命令检查环境是否就绪：

```bash
python -c "import playwright; print('Playwright OK')"
python -c "from docx import Document; print('python-docx OK')"
```

---

## 使用方法

### 基本用法

在终端中运行以下命令：

```bash
python -m src.cli <豆包聊天页面URL>
```

其中 `<豆包聊天页面URL>` 是您在豆包中打开的聊天页面的网址，类似于：

```
https://www.doubao.com/thread/ad8e9da8e8159
```

### 完整示例

```bash
# 导出单个聊天记录
python -m src.cli https://www.doubao.com/thread/ad8e9da8e8159

# 批量导出多个聊天记录（并发数默认3）
python -m src.cli url1 url2 url3

# 批量导出并指定并发数
python -m src.cli url1 url2 url3 url4 url5 --concurrency 5

# 使用高级反爬模式
python -m src.cli https://www.doubao.com/thread/ad8e9da8e8159 --level high

# 手动指定文档序号（仅单URL模式）
python -m src.cli https://www.doubao.com/thread/test --index 5
```

### 批量导出示例

```
[批次导出模式] 并发数: 3
总计 5 个 URL

[1/5] 正在导出: https://www.doubao.com/thread/abc
[2/5] 正在导出: https://www.doubao.com/thread/def
[3/5] 正在导出: https://www.doubao.com/thread/ghi
[✓] 完成: 260412-1 固定翼飞机设计.docx
[4/5] 正在导出: https://www.doubao.com/thread/jkl
...
```

### 进度输出示例

运行时会实时显示各阶段进度：

```
正在爬取: https://www.doubao.com/thread/xxx
反爬级别: medium
[✓] 启动浏览器成功 (2.3秒)
[✓] 访问页面成功 (1.5秒)
[✓] 滚动加载完成 (8次)
[✓] 代码块展开完成 (12个)
[✓] 爬取完成: 15条消息 (12.3秒)
[✓] 标题: xxx

--- 内容解析阶段 ---
[✓] 解析完成: 45个内容块 (0.8秒)
    段落: 30, 标题: 3, 代码: 8, 公式: 2, 表格: 1, 列表: 1, 引用: 0
[✓] 文档生成完成: data/export/260412/260412-1 测试.docx
总耗时: 13.5秒
```

### 命令行参数说明

| 参数 | 说明 | 可选值 | 默认值 |
|------|------|--------|--------|
| `urls` | 豆包聊天页面URL（支持多个） | - | 必填 |
| `--level` | 反爬检测级别 | low / medium / high | medium |
| `--index` | 手动指定文档序号（仅单URL模式） | 数字 | 自动分配 |
| `--concurrency` | 批量导出并发数 | 数字 | 3 |

#### 反爬级别说明

- **low（低）**：只使用随机 User-Agent，适合网络稳定的情况
- **medium（中）**：随机 User-Agent + 隐藏自动化特征，默认推荐
- **high（高）**：同 medium，可扩展更多反检测措施

---

## 输出说明

### 文件保存位置

导出的 Word 文档保存在项目目录下的 `data/export/` 文件夹中，按日期分类存放：

```
doubao-export/
└── data/
    └── export/
        └── 260412/                      ← 按日期分类的文件夹
            ├── 260412-1 固定翼飞机设计.docx
            ├── 260412-2 轻型教练机环控系统优化.docx
            └── 260412-3 3mm²软铜线绝缘表面风冷载流量分析.docx
```

### 文件命名规则

文件名格式为：`日期-序号 标题.docx`

- **日期**：导出时的日期，格式为 YYMMDD（如 260412 表示 2026年4月12日）
- **序号**：当天内递增的序号，用于区分同一天导出的不同文档
- **标题**：自动从聊天内容中提取的标题

### 索引文件

`data/link_index.json` 文件记录了所有已导出的文档索引，用于：

- 避免重复导出相同 URL 的内容
- 记录每个 URL 对应的序号和标题
- 自动清理超过 10 天的历史记录

---

## 项目结构

```
doubao-export/
├── src/                         # 源代码目录
│   ├── __init__.py
│   ├── config.py                # 全局配置
│   ├── cli.py                   # 命令行入口
│   ├── scraper/                 # 网页爬取模块
│   │   ├── __init__.py
│   │   ├── crawler.py           # 爬虫核心实现
│   │   └── anti_detect.py       # 反爬处理
│   ├── preprocessor/            # 数据解析模块
│   │   ├── __init__.py
│   │   └── doubao_parser.py     # HTML 解析器
│   └── generator/               # 文档生成模块
│       ├── __init__.py
│       ├── docx_builder.py      # Word 文档构建器
│       ├── latex_converter.py   # LaTeX 公式转换
│       └── doc_namer.py         # 文档命名器
├── data/                        # 数据输出目录
│   ├── export/                  # 导出的 Word 文档
│   └── link_index.json          # 链接索引文件
├── pyproject.toml               # 项目配置
├── requirements.txt             # Python 依赖列表
├── Makefile                     # 构建脚本
└── README.md                    # 项目说明文档
```

---

## 已知问题修复记录

| 修复日期 | 问题 | 文件 | 修改内容 |
|----------|------|------|----------|
| 2026-04-14 | 代码块展开等待时间单位错误 | scraper/crawler.py | wait_for_timeout 参数从秒改为毫秒 |
| 2026-04-14 | 批量导出序号并发冲突 | generator/doc_namer.py | 添加文件锁 (fcntl) 防止多进程序号冲突 |
| 2026-04-14 | 代码块中文显示字体不对 | generator/docx_builder.py | 使用 _set_run_font 方法设置中文字体 |

---

## 常见问题解答

### Q1: 运行命令后提示 "无效的豆包URL"

**原因**：提供的 URL 格式不正确。  
**解决方法**：请确保使用完整的豆包聊天页面 URL，格式类似：`https://www.doubao.com/thread/xxxxx`

### Q2: 提示 "playwright 未安装"

**原因**：Playwright 浏览器未安装。  
**解决方法**：运行 `playwright install chromium`

### Q3: 访问被拒绝或获取不到内容

**原因**：豆包的防爬机制可能检测到了自动化访问。  
**解决方法**：尝试使用 `--level high` 参数，或等待一段时间后重试。

### Q4: 公式没有正确显示

**原因**：pandoc 未正确安装。  
**解决方法**：确认已安装 pandoc：`pandoc --version`。如果已安装但仍有问题，公式会使用 Unicode 字符 fallback 显示。

### Q5: 导出很慢或卡住

**原因**：网络连接问题或页面加载超时。  
**解决方法**：检查网络连接，确认豆包网站可以正常访问。也可以尝试增加超时时间（需要修改代码）。

### Q6: 如何批量导出多个聊天记录？

支持批量导出多个 URL：

```bash
# 批量导出，默认并发数3
python -m src.cli url1 url2 url3

# 调整并发数
python -m src.cli url1 url2 url3 url4 url5 --concurrency 5
```

批量导出完成后会自动生成报告文件（`data/batch_report_*.txt`），记录成功/失败情况。

### Q7: 导出后的文档在哪里？

默认保存在 `data/export/YYYYMMDD/` 目录下（按日期分类）。如果目录不存在，程序会自动创建。

---

## 依赖说明

### Python 包依赖

| 包名 | 版本要求 | 用途 |
|------|----------|------|
| playwright | >= 1.40.0 | 自动化浏览器，用于抓取网页 |
| python-docx | >= 1.1.0 | 操作 Word 文档 |
| beautifulsoup4 | >= 4.12.0 | 解析 HTML 内容 |
| lxml | >= 5.0.0 | HTML 解析器底层库 |

### 系统依赖

| 软件 | 用途 | 备注 |
|------|------|------|
| Python | 运行环境 | 3.10+ |
| Chromium | 浏览器内核 | 通过 Playwright 安装 |
| pandoc | 公式转换 | 可选，建议安装 |

---

## 注意事项

1. **合法使用**：请仅导出您有权访问的聊天内容，不要用于非法抓取他人数据。
2. **网络要求**：需要能够正常访问豆包网站。
3. **登录状态**：如果聊天内容需要登录才能查看，需要确保运行工具的电脑可以访问这些内容。
4. **数据安全**：工具仅在本地运行，不会将您的数据上传到任何服务器。

---

## 后续扩展

如果您想进一步开发或定制这个工具，可以考虑：

- 添加更多输出格式（如 PDF、Markdown）
- 支持批量导出
- 添加图形界面
- 支持更多 AI 平台

---

如有问题，欢迎提交 Issue 或参与贡献！