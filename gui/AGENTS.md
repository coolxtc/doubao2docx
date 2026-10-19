# gui/

## 模块职责

Flet 图形界面层：用户交互、配置管理、实时进度展示。

## 入口

`gui/__main__.py` —— 跨平台单实例锁 + Flet 应用启动。

```bash
python3 -m gui                          # 开发模式
doubao-export-gui                       # 安装后
```

## 关键模块

| 文件 | 类/函数 | 用途 |
|------|---------|------|
| `__main__.py` | `main()`, `acquire_lock()` | 入口 + 跨平台文件锁（Windows msvcrt / Unix fcntl） |
| `app.py` | `main_app()`, `_setup_builtin_resources()` | Flet 应用初始化，内置 Pandoc/浏览器路径配置 |
| `config_manager.py` | `load_config()`, `save_config()` | 用户配置持久化（JSON，`~/.doubao_export/config.json`） |
| `reporter.py` | `FletReporter` | 进度报告器，与 CLI 的 `TaskManager` 对接 |
| `pages/main_page.py` | `MainPage` | 主界面（URL 输入、反爬设置、进度表格、日志面板） |

## 与 CLI 的关系

GUI 复用 CLI 的核心流程：

```
gui/main_page.py  →  src.cli.fetch_and_export_batch()
                     src.cli._get_url_tag()
```

所有导出逻辑在 `src/` 中，GUI 仅提供交互层。

## 内置资源路径

打包后（PyInstaller），Pandoc 和 Playwright 浏览器位于 exe 同级目录：

```
app_root/
├── pandoc[.exe]
└── playwright_browsers/
    └── chromium-1217/
```

`_get_app_root()` 自动检测开发环境 vs 打包环境。

## 单实例锁

通过文件锁防止重复启动：

- **Windows**：`msvcrt.locking()` 独占非阻塞锁
- **Unix**：`fcntl.flock()` 独占非阻塞锁
- 锁文件：`~/.doubao_export.lock`

## 配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| 导出目录 | `~/Desktop/豆包对话导出` | 可在界面中修改并持久化 |
| 反爬级别 | `medium` | low / medium / high |
| 并发数 | `5` | 批量导出时生效 |
| 日志文件 | `~/.doubao_export/doubao_export.log` | 同时输出到终端 |

## 导出

```python
from gui.app import main_app
from gui.config_manager import load_config, set_export_dir
from gui.reporter import FletReporter
```