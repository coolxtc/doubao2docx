"""Flet 应用初始化"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

import flet as ft

from src.utils import windows_compat_setup, windows_compat_cleanup
from gui.pages.main_page import MainPage


def _get_app_root() -> Path:
    """
    获取应用根目录（用于定位内置资源）

    打包后（sys.frozen=True）：
        macOS: .app/Contents/MacOS
        Windows: exe 所在目录
    开发时：当前文件所在目录的上一级（即项目根目录）
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        # gui/app.py → gui/ → 项目根目录
        return Path(__file__).resolve().parent.parent


async def main_app(page: ft.Page) -> None:
    """
    主应用入口

    Args:
        page: Flet 页面实例
    """
    # 1. 将内置 pandoc 加入 PATH（如果存在）
    app_root = _get_app_root()
    pandoc_dir = app_root / "pandoc"
    pandoc_exec = pandoc_dir / ("pandoc.exe" if sys.platform == "win32" else "pandoc")
    if pandoc_exec.exists():
        # 确保可执行权限（macOS / Linux）
        if sys.platform != "win32":
            pandoc_exec.chmod(0o755)
        # 将 pandoc 所在目录临时添加到 PATH 最前面
        os.environ["PATH"] = str(pandoc_dir) + os.pathsep + os.environ.get("PATH", "")

    # 2. 检查 Playwright 浏览器，没有则自动下载
    browser_dir = Path.home() / ".cache" / "ms-playwright"
    if not browser_dir.exists() or not any(browser_dir.glob("chromium-*")):
        page.snack_bar = ft.SnackBar(ft.Text("正在下载浏览器组件，请稍候…"))
        page.update()
        try:
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError:
            page.snack_bar = ft.SnackBar(
                ft.Text("浏览器下载失败，请检查网络后重启应用")
            )
            page.update()
        else:
            page.snack_bar = ft.SnackBar(ft.Text("浏览器安装完成！"))
            page.update()

    # 3. 检查 Pandoc 是否可用（无论内置还是系统安装）
    if not shutil.which("pandoc"):
        page.snack_bar = ft.SnackBar(
            ft.Text("未检测到 Pandoc，公式将使用 Unicode 显示")
        )
        page.update()

    # 4. 初始化窗口
    page.title = "豆包聊天记录导出工具"
    page.window_width = 960
    page.window_height = 720
    page.theme_mode = ft.ThemeMode.SYSTEM
    windows_compat_setup()

    main = MainPage(page)
    page.add(main)

    # 退出清理
    page.on_close = lambda _: windows_compat_cleanup()
