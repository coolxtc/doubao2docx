"""Flet 应用初始化"""

import flet as ft

from src.utils import windows_compat_setup, windows_compat_cleanup
from gui.pages.main_page import MainPage


async def main_app(page: ft.Page) -> None:
    """
    主应用入口

    Args:
        page: Flet 页面实例
    """
    page.title = "豆包聊天记录导出工具"
    page.window_width = 960
    page.window_height = 720
    page.theme_mode = ft.ThemeMode.SYSTEM
    windows_compat_setup()

    main = MainPage(page)
    page.add(main)

    # 退出清理
    page.on_close = lambda _: windows_compat_cleanup()


ft.app(target=main_app)
