"""主界面页面 - 现代化优化版（底部设置抽屉）"""

import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import flet as ft

from src.cli import fetch_and_export_batch
from gui.reporter import FletReporter
from src.cli import _get_url_tag


# 配色方案
PRIMARY = ft.Colors.BLUE_600
PRIMARY_CONTAINER = ft.Colors.BLUE_50
ON_PRIMARY_CONTAINER = ft.Colors.BLUE_900
SURFACE = ft.Colors.WHITE
OUTLINE = ft.Colors.GREY_300
BACKGROUND = ft.Colors.GREY_100


class MainPage(ft.Column):
    """
    主界面组件（底部设置抽屉）
    """

    def __init__(self, page: ft.Page) -> None:
        super().__init__()
        self._page = page
        self.expand = True
        self.scroll = ft.ScrollMode.AUTO

        # ---------- URL 输入区 ----------
        self.url_field = ft.TextField(
            label="豆包链接（每行一个）",
            hint_text="https://www.doubao.com/chat/...",
            multiline=True,
            min_lines=3,
            max_lines=8,
            border_color=OUTLINE,
            border_radius=12,
            filled=True,
            fill_color=SURFACE,
            text_style=ft.TextStyle(size=14),
            content_padding=ft.Padding(left=16, right=16, top=12, bottom=12),
            expand=True,   # 添加这一行
        )

        # ---------- 设置控件（不直接放入布局，将通过底部表展示） ----------
        self.level_dd = ft.Dropdown(
            label="反爬级别",
            options=[
                ft.dropdown.Option("low", "低"),
                ft.dropdown.Option("medium", "中"),
                ft.dropdown.Option("high", "高"),
            ],
            value="medium",
            width=200,
            border_radius=10,
            filled=True,
            fill_color=SURFACE,
        )
        self.concurrency_field = ft.TextField(
            label="并发数",
            value="5",
            width=200,
            input_filter=ft.NumbersOnlyInputFilter(),
            border_radius=10,
            filled=True,
            fill_color=SURFACE,
            text_align=ft.TextAlign.CENTER,
        )
        self.dir_text = ft.Text(
            "data/export/",
            size=13,
            italic=True,
            color=ft.Colors.GREY_700,
        )
        self.dir_button = ft.ElevatedButton(
            "选择导出目录",
            icon=ft.Icons.FOLDER_OPEN,
            on_click=self._pick_directory,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.Padding(left=12, right=12, top=8, bottom=8),
            ),
        )

        # ---------- 进度表格 ----------
        self.progress_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("#", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("任务", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("进度", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("状态", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("耗时", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("结果", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            heading_row_color=ft.Colors.GREY_200,
            column_spacing=12,
            data_row_max_height=40,
            expand=True,   # 表格撑满其所在 Column
        )
        self.reporter: Optional[FletReporter] = None

        # ---------- 日志区 ----------
        self.log_area = ft.Column(
            controls=[],
            scroll=ft.ScrollMode.AUTO,
            height=100,
            visible=False,
        )

        # ---------- 结果区 ----------
        self.result_text = ft.Text(
            "",
            size=14,
            weight=ft.FontWeight.W_500,
        )
        self.open_folder_btn = ft.ElevatedButton(
            "打开导出文件夹",
            icon=ft.Icons.FOLDER_OPEN,
            visible=False,
            on_click=self._open_folder,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )

        # ---------- 结果卡片 ----------
        self.result_card = ft.Card(
            elevation=3,
            shape=ft.RoundedRectangleBorder(radius=16),
            visible=False,
            content=ft.Container(
                padding=24,
                bgcolor=SURFACE,
                border_radius=16,
                expand=True,               # ← 让 Container 撑满卡片宽度
                content=ft.Column(
                    spacing=12,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,  # ← 新增
                    controls=[
                        ft.Text(
                            "✅ 导出完成",
                            size=18,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.GREEN_700,
                        ),
                        self.result_text,
                        self.open_folder_btn,
                    ],
                ),
            ),
        )

        # ---------- 导出按钮 ----------
        self.export_btn = ft.FilledButton(
            "开始导出",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._start_export,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=12),
                bgcolor=PRIMARY,
                color=ft.Colors.WHITE,
                padding=ft.Padding(left=24, right=24, top=12, bottom=12),
                elevation=2,
            ),
        )
        self.status_text = ft.Text(
            "就绪",
            size=12,
            color=ft.Colors.GREY_500,
        )

        # ---------- 布局组装 ----------
        self.controls = self._build_layout()

    def _build_layout(self) -> list[ft.Control]:
        """构建卡片化布局，右上角添加设置齿轮图标"""
        return [
            # 顶部卡片：输入区 + 设置图标
            ft.Card(
                elevation=3,
                shape=ft.RoundedRectangleBorder(radius=16),
                content=ft.Container(
                    padding=24,
                    bgcolor=SURFACE,
                    border_radius=16,
                    content=ft.Column(
                        spacing=16,
                        controls=[
                            ft.Row(
                                [
                                    ft.Text(
                                        "📦 任务配置",
                                        size=18,
                                        weight=ft.FontWeight.BOLD,
                                        color=ON_PRIMARY_CONTAINER,
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.SETTINGS,
                                        tooltip="导出设置",
                                        on_click=self._open_settings,
                                        icon_color=ft.Colors.GREY_700,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            # URL 输入
                            ft.Column(
                                spacing=8,
                                controls=[
                                    ft.Text("聊天链接", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_700),
                                    self.url_field,
                                    ft.Row(
                                        [
                                            ft.TextButton(
                                                "清空",
                                                icon=ft.Icons.CLEAR,
                                                on_click=self._clear,
                                                style=ft.ButtonStyle(color=ft.Colors.GREY_600),
                                            ),
                                            ft.TextButton(
                                                "从剪贴板粘贴",
                                                icon=ft.Icons.CONTENT_PASTE,
                                                on_click=self._paste,
                                                style=ft.ButtonStyle(color=ft.Colors.GREY_600),
                                            ),
                                            ft.Container(expand=True),  # 空白填充，撑开左右
                                            self.export_btn,
                                        ],
                                        spacing=8,
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
            ),

            # 操作卡片：导出按钮 + 进度
            ft.Card(
                elevation=3,
                shape=ft.RoundedRectangleBorder(radius=16),
                content=ft.Container(
                    padding=24,
                    bgcolor=SURFACE,
                    border_radius=16,
                    expand=True,               # 让进度容器也撑满
                    content=ft.Column(
                        spacing=16,
                        controls=[
                            ft.Row(
                                [
                                    ft.Container(expand=True),
                                    self.status_text,
                                ],
                                alignment=ft.MainAxisAlignment.END,
                            ),
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Text(
                                            "导出进度",
                                            size=14,
                                            weight=ft.FontWeight.W_600,
                                            color=ft.Colors.GREY_600,
                                        ),
                                        self.progress_table,
                                    ],
                                    spacing=8,
                                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,  # ← 新增这一行
                                ),
                                padding=ft.Padding(top=8, right=0, bottom=0, left=0),
                                expand=True,               # 让进度容器也撑满
                            ),
                        ],
                    ),
                ),
            ),

            # 结果卡片
            self.result_card,

            # 日志卡片（折叠）
            ft.Card(
                elevation=1,
                shape=ft.RoundedRectangleBorder(radius=16),
                visible=False,
                content=ft.Container(
                    padding=16,
                    bgcolor=SURFACE,
                    border_radius=16,
                    content=ft.Column(
                        [
                            ft.Text(
                                "📋 运行日志",
                                size=14,
                                weight=ft.FontWeight.W_600,
                            ),
                            self.log_area,
                        ],
                    ),
                ),
            ),
        ]

    def _open_settings(self, e):
        """打开设置对话框（调试版）"""

        # 创建设置内容
        settings_content = ft.Column(
            tight=True,
            spacing=16,
            controls=[
                self.level_dd,
                self.concurrency_field,
                ft.Row([self.dir_button, self.dir_text], spacing=12),
            ],
        )

        dlg = ft.AlertDialog(
            title=ft.Text("导出设置", weight=ft.FontWeight.BOLD),
            content=settings_content,
            actions=[ft.TextButton("完成", on_click=lambda e: self._page.pop_dialog())],
        )

        self._page.show_dialog(dlg)

    # ========== 功能方法（无变化） ==========
    def _clear(self, e: ft.ControlEvent) -> None:
        self.url_field.value = ""
        self.url_field.update()

    async def _paste(self, e: ft.ControlEvent) -> None:
        try:
            clipboard_data = await ft.Clipboard().get()
            if clipboard_data:
                self.url_field.value = clipboard_data
                self.url_field.update()
        except Exception:
            pass

    def _add_log(self, msg: str) -> None:
        if not self.log_area.visible:
            self.log_area.visible = True
            self.log_area.parent.visible = True
            self._page.update()
        self.log_area.controls.append(ft.Text(msg, size=11))
        self.log_area.update()

    async def _start_export(self, e: ft.ControlEvent) -> None:

        urls = [u.strip() for u in self.url_field.value.splitlines() if u.strip()]
        if not urls:
            self._page.snack_bar = ft.SnackBar(ft.Text("请至少输入一个链接"))
            self._page.update()
            return

        self.export_btn.disabled = True
        self.status_text.value = "导出中..."
        self.status_text.update()

        # 隐藏结果卡片
        self.result_card.visible = False

        self.reporter = FletReporter(self.progress_table, self._page, log_callback=self._add_log)
        self.reporter.start()
        for i, url in enumerate(urls, 1):
            tag = _get_url_tag(url)
            self.reporter.add_task(i, tag)

        dir_str = self.dir_text.value.rstrip("/\\")
        output_dir = Path(dir_str if dir_str else "data")

        try:
            report = await fetch_and_export_batch(
                urls=urls,
                output_dir=output_dir,
                anti_detect_level=self.level_dd.value or "medium",
                concurrency=int(self.concurrency_field.value or "5"),
                reporter=self.reporter,
            )
            success_count = sum(1 for r in report.results if r.success)
            fail_count = len(report.results) - success_count
            self.result_text.value = f"成功 {success_count} 个，失败 {fail_count} 个"
            self._last_export_dir = output_dir / "export" / datetime.now().strftime("%y%m%d")
            self.open_folder_btn.visible = True
            self.result_card.visible = True
        except Exception as ex:
            self.result_text.value = f"❌ 导出失败: {ex}"
            self._add_log(f"错误: {ex}")
        finally:
            self.reporter.stop()
            self.export_btn.disabled = False
            self.status_text.value = "就绪"
            self.status_text.update()
            self._page.update()

    async def _pick_directory(self, e):
        try:
            dir_path = await ft.FilePicker().get_directory_path()
            if dir_path:
                self.dir_text.value = dir_path
                self.dir_text.update()
        except Exception as ex:
            self._add_log(f"目录选择失败: {ex}")

    def _open_folder(self, e: ft.ControlEvent) -> None:
        folder = getattr(self, "_last_export_dir", None)
        if not folder:
            folder = Path(self.dir_text.value.rstrip("/\\"))
        folder = Path(folder).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        system = platform.system()
        if system == "Darwin":
            subprocess.run(["open", str(folder)])
        elif system == "Windows":
            subprocess.run(["explorer", str(folder)])
        else:
            subprocess.run(["xdg-open", str(folder)])