"""Flet 进度报告器实现"""

from pathlib import Path
from typing import Any, Callable, Optional

import flet as ft

from src.cli import ProgressReporter

# 与 CLI 步骤数保持一致（src/scraper/steps.py 中的 STEP_COUNT）
TOTAL_STEPS = 6

class FletReporter(ProgressReporter):
    """
    Flet GUI 进度报告器

    实现 ProgressReporter 协议，用于实时更新 GUI 进度表格。
    """

    def __init__(
        self,
        data_table: ft.DataTable,
        page: ft.Page,
        log_callback: Optional[Callable[[str], None]] = None,
        base_path: Optional[Path] = None,
        file_opener: Optional[Callable[[Path], None]] = None,
    ) -> None:
        self.table = data_table
        self.page = page
        self.log_callback = log_callback
        # 导出目录根路径（用于拼接完整文件路径）
        self.base_path = base_path
        # 打开文件的回调函数
        self.file_opener = file_opener
        self._rows: dict[int, ft.DataRow] = {}

    def add_task(self, task_index: int, url_tag: str) -> Any:
        """
        添加一行任务到表格

        Args:
            task_index: 任务序号
            url_tag: URL 标签（thread ID 或截断的 URL）
        """
        # 截取 URL 标识（取最后一部分）
        tag_display = url_tag if len(url_tag) <= 20 else "..." + url_tag[-17:]
        # 初始进度：灰色全圆
        init_progress = ft.Text("○" * TOTAL_STEPS, color=ft.Colors.GREY, size=13)
        row = ft.DataRow(
            cells=[
                ft.DataCell(ft.Container(ft.Text(f"[{task_index}]{tag_display}", tooltip=url_tag), width=150)),
                ft.DataCell(ft.Container(init_progress, width=90)),
                ft.DataCell(ft.Container(ft.Text("等待中"), width=70)),
                ft.DataCell(ft.Container(ft.Text(""), width=40)),
                ft.DataCell(ft.Container(ft.Text(""), width=500)),
            ]
        )
        self.table.rows.append(row)
        self._rows[task_index] = row
        self.page.update()

    def update(
        self,
        task_index: int,
        step: int,
        status: str,
        result: str = "",
        elapsed: float = 0.0,
    ) -> None:
        """
        更新任务进度

        Args:
            task_index: 任务序号
            step: 步骤索引（0-10）
            status: 状态文本
            result: 结果或错误信息
            elapsed: 已耗时（秒）
        """
        row = self._rows.get(task_index)
        if not row:
            return

        # 构建彩色进度文本
        row.cells[1].content.content = self._build_progress_text(step)
        row.cells[2].content.content.value = status
        row.cells[3].content.content.value = f"{elapsed:.1f}s" if elapsed else ""

        # 结果列：根据完成状态切换显示模式
        if step >= TOTAL_STEPS and result:
            full_path = (self.base_path / result) if self.base_path else Path(result)
            open_btn = ft.IconButton(
                icon=ft.Icons.FOLDER_OPEN,
                icon_size=14,
                tooltip="打开文档",
                on_click=lambda e, p=full_path: self.file_opener(p) if self.file_opener else None,
            )
            result_text = ft.Text(result, size=12)
            row.cells[4].content.content = ft.Row(
                [open_btn, result_text],
                spacing=4,
                alignment=ft.MainAxisAlignment.START,
            )
        else:
            # 未完成或 result 为空 → 普通文本
            row.cells[4].content.content = ft.Text(result)
        self.page.update()

    def _build_progress_text(self, step: int) -> ft.Text:
        """根据当前步骤构建彩色进度文本"""
        done = min(step, TOTAL_STEPS)
        spans = []
        for _ in range(done):
            spans.append(ft.TextSpan("●", style=ft.TextStyle(color=ft.Colors.GREEN_600)))
        if step < TOTAL_STEPS:
            spans.append(ft.TextSpan("→", style=ft.TextStyle(color=ft.Colors.AMBER)))
            for _ in range(TOTAL_STEPS - done - 1):
                spans.append(ft.TextSpan("○", style=ft.TextStyle(color=ft.Colors.GREY_400)))
        else:
            # 已完成：全绿
            for _ in range(TOTAL_STEPS - done):
                spans.append(ft.TextSpan("●", style=ft.TextStyle(color=ft.Colors.GREEN_600)))
        return ft.Text(spans=spans, size=13)

    def log_warning(self, msg: str) -> None:
        """
        记录警告日志

        Args:
            msg: 警告消息
        """
        if self.log_callback:
            self.log_callback(msg)

    def start(self) -> None:
        """开始新的导出批次"""
        self.table.rows.clear()
        self._rows.clear()
        self.page.update()

    def stop(self) -> None:
        """结束导出批次"""
        self.page.update()
