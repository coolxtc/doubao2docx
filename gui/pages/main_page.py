"""主界面页面"""

import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import flet as ft

from src.cli import fetch_and_export_batch
from gui.reporter import FletReporter


class MainPage(ft.Column):
    """
    主界面组件

    包含 URL 输入区、选项栏、进度表格、结果区和日志区。
    """

    def __init__(self, page: ft.Page) -> None:
        super().__init__()
        self._page = page
        self.expand = True
        self.scroll = ft.ScrollMode.AUTO

        # URL 输入区
        self.url_field = ft.TextField(
            label="豆包链接（每行一个）",
            hint_text="https://www.doubao.com/chat/...",
            multiline=True,
            min_lines=3,
            max_lines=8,
            border_color=ft.Colors.OUTLINE,
        )

        # 选项区
        self.level_dd = ft.Dropdown(
            label="反爬级别",
            options=[
                ft.dropdown.Option("low", "低"),
                ft.dropdown.Option("medium", "中"),
                ft.dropdown.Option("high", "高"),
            ],
            value="medium",
            width=120,
        )
        self.concurrency_field = ft.TextField(
            label="并发数",
            value="5",
            width=80,
            input_filter=ft.NumbersOnlyInputFilter(),
        )

        # 导出目录选择
        self.dir_button = ft.ElevatedButton(
            "选择导出目录",
            icon=ft.Icons.FOLDER_OPEN,
            on_click=self._pick_directory,  # 指向新异步函数
        )
        self.dir_text = ft.Text("data")

        # 进度表格
        self.progress_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("#")),
                ft.DataColumn(ft.Text("任务")),
                ft.DataColumn(ft.Text("进度")),
                ft.DataColumn(ft.Text("状态")),
                ft.DataColumn(ft.Text("耗时")),
                ft.DataColumn(ft.Text("结果")),
            ],
            rows=[],
            heading_row_color=ft.Colors.SURFACE,
            column_spacing=10,
        )
        self.reporter: Optional[FletReporter] = None

        # 日志区
        self.log_area = ft.Column(
            controls=[],
            scroll=ft.ScrollMode.AUTO,
            height=100,
            visible=False,
        )

        # 结果区
        self.result_text = ft.Text("")
        self.open_folder_btn = ft.ElevatedButton(
            "打开导出文件夹",
            icon=ft.Icons.FOLDER_OPEN,
            visible=False,
            on_click=self._open_folder,
        )

        # 导出按钮
        self.export_btn = ft.ElevatedButton(
            "🚀 开始导出",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._start_export,
        )
        self.status_text = ft.Text("就绪", size=12, color=ft.Colors.OUTLINE)

        # 布局
        self.controls = self._build_layout()

    def _build_layout(self) -> list[ft.Control]:
        """
        构建页面布局

        Returns:
            控件列表
        """
        return [
            # 标题
            ft.Text(
                "豆包聊天记录导出工具",
                size=24,
                weight=ft.FontWeight.BOLD,
            ),
            ft.Divider(),
            # URL 输入
            self.url_field,
            ft.Row(
                [
                    ft.ElevatedButton(
                        "清空",
                        icon=ft.Icons.CLEAR,
                        on_click=self._clear,
                    ),
                    ft.ElevatedButton(
                        "从剪贴板粘贴",
                        icon=ft.Icons.CONTENT_PASTE,
                        on_click=self._paste,
                    ),
                ]
            ),
            ft.Divider(),
            # 选项区
            ft.Row([self.level_dd, self.concurrency_field, self.dir_button]),
            self.dir_text,
            ft.Divider(),
            # 导出按钮和状态
            ft.Row([self.export_btn, self.status_text]),
            # 进度表格
            ft.Container(
                content=self.progress_table,
                padding=10,
                border=ft.Border(
                    top=ft.BorderSide(1, ft.Colors.OUTLINE),
                    bottom=ft.BorderSide(1, ft.Colors.OUTLINE),
                    left=ft.BorderSide(1, ft.Colors.OUTLINE),
                    right=ft.BorderSide(1, ft.Colors.OUTLINE)
                ),
                border_radius=8,
            ),
            # 日志区
            ft.Container(
                content=ft.Column([self.log_area], scroll=ft.ScrollMode.AUTO),
                padding=10,
                border=ft.Border(
                    top=ft.BorderSide(1, ft.Colors.OUTLINE),
                    bottom=ft.BorderSide(1, ft.Colors.OUTLINE),
                    left=ft.BorderSide(1, ft.Colors.OUTLINE),
                    right=ft.BorderSide(1, ft.Colors.OUTLINE)
                ),
                border_radius=8,
                visible=False,
            ),
            # 结果区
            self.result_text,
            self.open_folder_btn,
        ]

    def _clear(self, e: ft.ControlEvent) -> None:
        """
        清空输入

        Args:
            e: 控制事件
        """
        self.url_field.value = ""
        self.url_field.update()

    async def _paste(self, e: ft.ControlEvent) -> None:
        """
        从剪贴板粘贴

        Args:
            e: 控制事件
        """
        try:
            clipboard_data = await ft.Clipboard().get()
            if clipboard_data:
                self.url_field.value = clipboard_data
                self.url_field.update()
        except Exception:
            pass

    def _add_log(self, msg: str) -> None:
        """
        添加日志消息

        Args:
            msg: 日志消息
        """
        # 确保日志区可见
        if not self.log_area.visible:
            self.log_area.visible = True
            self.log_area.parent.visible = True
            self._page.update()
        self.log_area.controls.append(ft.Text(msg, size=11))
        self.log_area.update()

    async def _start_export(self, e: ft.ControlEvent) -> None:
        """
        开始导出

        Args:
            e: 控制事件
        """
        urls = [u.strip() for u in self.url_field.value.splitlines() if u.strip()]
        if not urls:
            self._page.snack_bar = ft.SnackBar(ft.Text("请至少输入一个链接"))
            self._page.update()
            return

        # 禁用导出按钮
        self.export_btn.disabled = True
        self.status_text.value = "导出中..."
        self.result_text.value = ""
        self.open_folder_btn.visible = False
        self._page.update()

        # 初始化 reporter
        self.reporter = FletReporter(self.progress_table, self._page, log_callback=self._add_log)
        self.reporter.start()

        # 为每个 URL 添加任务行
        for i, url in enumerate(urls, 1):
            self.reporter.add_task(i, url)

        output_dir = Path(self.dir_text.value or "data")

        try:
            report = await fetch_and_export_batch(
                urls=urls,
                output_dir=output_dir,
                anti_detect_level=self.level_dd.value or "medium",
                concurrency=int(self.concurrency_field.value or "5"),
                reporter=self.reporter,
            )
            # 显示汇总结果
            success_count = sum(1 for r in report.results if r.success)
            fail_count = len(report.results) - success_count
            self.result_text.value = (
                f"✅ 成功 {success_count} 个"
                f"{f'，失败 {fail_count} 个' if fail_count > 0 else ''}"
            )
            self._last_export_dir = output_dir / "export" / datetime.now().strftime("%y%m%d")
            self.open_folder_btn.visible = True

        except Exception as ex:
            self.result_text.value = f"❌ 导出失败: {ex}"
            self._add_log(f"错误: {ex}")

        finally:
            self.reporter.stop()
            self.export_btn.disabled = False
            self.status_text.value = "完成"
            self._page.update()

    async def _pick_directory(self, e):
        """使用静态方法弹出目录选择对话框"""
        try:
            dir_path = await ft.FilePicker().get_directory_path()
            if dir_path:
                self.dir_text.value = dir_path
                self.dir_text.update()
        except Exception as ex:
            self._add_log(f"目录选择失败: {ex}")

    def _open_folder(self, e: ft.ControlEvent) -> None:
        """
        打开导出文件夹

        Args:
            e: 控制事件
        """        
        
        folder = self._last_export_dir
        system = platform.system()
        if system == "Darwin":
            subprocess.run(["open", str(folder)])
        elif system == "Windows":
            subprocess.run(["explorer", str(folder)])
        else:
            subprocess.run(["xdg-open", str(folder)])
