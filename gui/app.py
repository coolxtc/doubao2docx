"""Flet 应用初始化（最终内置版）"""

import ctypes
import os
import sys
import shutil
import logging
import asyncio
from pathlib import Path

import flet as ft

from src.utils import windows_compat_setup, windows_compat_cleanup
from gui.pages.main_page import MainPage
from gui import config_manager

def hide_console():
    """在 Windows 上释放控制台窗口（解决 subprocess 弹窗问题）"""
    if sys.platform == "win32":
        try:
            # 释放当前进程的控制台
            kernel32 = ctypes.WinDLL('kernel32')
            kernel32.FreeConsole()
        except Exception:
            pass  # 如果本来就没有控制台，忽略错误

# ----- 日志配置：写入 ~/.doubao_export/doubao_export.log -----
config_manager.CONFIG_DIR.mkdir(parents=True, exist_ok=True)  # 确保目录存在
LOG_FILE = config_manager.CONFIG_DIR / "doubao_export.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("doubao.gui")

def _get_app_root() -> Path:
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后，所有通过 --add-data 添加的资源都解压到此目录
        return Path(sys._MEIPASS)
    else:
        return Path(__file__).resolve().parent.parent

def _setup_builtin_resources():
    """配置内置 Pandoc 和 Playwright 浏览器的路径"""
    app_root = _get_app_root()

    # 内置 Pandoc
    pandoc_exec = app_root / ("pandoc.exe" if sys.platform == "win32" else "pandoc")
    if pandoc_exec.exists():
        if sys.platform != "win32":
            pandoc_exec.chmod(0o755)
        os.environ["PATH"] = str(pandoc_exec.parent) + os.pathsep + os.environ.get("PATH", "")
        logger.info(f"Pandoc 找到: {pandoc_exec}")
    else:
        logger.warning("Pandoc 未找到，公式将使用 Unicode 显示")

    # 内置 Playwright 浏览器
    browsers_path = app_root / "playwright_browsers"
    if browsers_path.exists():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_path)
        logger.info("使用内置浏览器")
        return True
    else:
        logger.warning("未找到内置浏览器")
        return False


async def main_app(page: ft.Page):
    logger.info("应用启动")
    hide_console()  # 必须在任何 subprocess 调用之前执行

    os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)  # 清除可能干扰的环境变量

    has_builtin = _setup_builtin_resources()

    # 窗口初始化
    page.title = "豆包聊天记录导出工具"
    page.window_width = 960
    page.window_height = 720
    page.theme_mode = ft.ThemeMode.SYSTEM
    windows_compat_setup()

    main = MainPage(page)
    page.add(main)

    # 如果内置资源不存在，提示用户（正常打包后不会走到这里）
    if not has_builtin:
        page.snack_bar = ft.SnackBar(ft.Text("浏览器组件缺失，请重新安装应用"))
        page.update()
    if not shutil.which("pandoc"):
        page.snack_bar = ft.SnackBar(ft.Text("未检测到 Pandoc，公式将使用 Unicode 显示"))
        page.update()

    page.on_close = lambda _: windows_compat_cleanup()