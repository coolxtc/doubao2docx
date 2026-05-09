"""Flet 进度报告器实现"""

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
    ) -> None:
        self.table = data_table
        self.page = page
        self.log_callback = log_callback
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
        row = ft.DataRow(
            cells=[
                ft.DataCell(ft.Text(str(task_index))),
                ft.DataCell(ft.Text(tag_display, tooltip=url_tag)),
                ft.DataCell(ft.Text("○" * TOTAL_STEPS)),
                ft.DataCell(ft.Text("等待中")),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text("")),
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

        # step 应该对应 FetchStep 索引（0-5），超过 TOTAL_STEPS 表示完成
        done = min(step, TOTAL_STEPS)
        if step < TOTAL_STEPS:
            # 进行中：已完成 ● + 当前 → + 未完成 ○
            dots = "●" * done + "→" + "○" * (TOTAL_STEPS - done - 1)
        else:
            # 已完成：全 ●
            dots = "●" * TOTAL_STEPS

        row.cells[2].content.value = dots
        row.cells[3].content.value = status
        row.cells[4].content.value = f"{elapsed:.1f}s" if elapsed else ""
        row.cells[5].content.value = result
        self.page.update()

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
