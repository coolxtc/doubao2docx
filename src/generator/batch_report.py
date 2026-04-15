"""批量导出报告生成器

本模块负责生成批量导出的汇总报告，记录导出成功和失败的情况。
主要功能：
- 记录每个 URL 的导出结果（成功/失败）
- 生成格式化的报告文本
- 提供打印功能

设计理念：
- 使用 dataclass 简化数据结构定义
- 报告内容直接打印到终端，不保存本地文件（简化用户操作）

使用示例：
    report = BatchReport()
    report.add_success("https://example.com", "文档标题.docx")
    report.add_failure("https://fail.com", "连接超时")
    report.print_summary()
"""

import os
import platform
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from rich.console import Console
from rich.style import Style
from rich.text import Text


@dataclass
class ExportResult:
    url: str
    success: bool
    filename: Optional[str] = None
    file_path: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class BatchReport:
    """批量导出报告 - 收集和管理多次导出结果
    
    工作原理：
    1. 创建实例时自动记录开始时间
    2. 每次导出完成后，调用 add_success() 或 add_failure() 记录结果
    3. 所有结果存储在 results 列表中
    4. 导出完成后，调用 print_summary() 打印汇总报告
    
    属性说明：
        results: 所有导出结果的列表，初始为空
        start_time: 批量操作开始时间，自动设置为当前时间
    """
    results: list[ExportResult] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)

    def add_success(self, url: str, filename: str, file_path: str = None) -> None:
        self.results.append(ExportResult(url=url, success=True, filename=filename, file_path=file_path))

    def add_failure(self, url: str, error: str) -> None:
        self.results.append(ExportResult(url=url, success=False, error_message=error))

    def _format_report(self) -> str:
        """格式化报告文本
        
        生成格式化的报告字符串，包含：
        - 报告标题和生成时间
        - 总计、成功、失败的数量统计
        - 成功和失败的详细列表
        
        Returns:
            格式化的报告文本字符串
        """
        # 统计总数和成功率
        total = len(self.results)
        success_count = sum(1 for r in self.results if r.success)
        failure_count = total - success_count
        
        # 构建报告头部
        lines = [
            "=" * 50,
            f"导出报告 - {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 50,
            "",
            f"总计: {total} 个 URL",
            f"成功: {success_count} 个",
            f"失败: {failure_count} 个",
            "",
            "-" * 50,
        ]
        
        # 添加成功列表
        success_results = [r for r in self.results if r.success]
        if success_results:
            lines.append("成功:")
            for r in success_results:
                lines.append(f"  [✓] {r.filename}")
            lines.append("")
        
        # 添加失败列表
        failure_results = [r for r in self.results if not r.success]
        if failure_results:
            lines.append("失败:")
            for r in failure_results:
                lines.append(f"  [✗] {r.url}")
                lines.append(f"      原因: {r.error_message}")
            lines.append("")
        
        lines.extend(["-" * 50, "=" * 50])
        return "\n".join(lines)

    def print_summary(self) -> None:
        console = Console()
        success_results = [r for r in self.results if r.success]
        failure_results = [r for r in self.results if not r.success]
        
        console.print("")
        console.print("[bold]成功:[/bold]")
        
        for r in success_results:
            if r.file_path and console.is_terminal:
                link = _build_file_link(r.file_path, r.filename)
                console.print(f"  [✓] {link}")
            else:
                console.print(f"  [✓] {r.filename}")
        
        if failure_results:
            console.print("[bold]失败:[/bold]")
            for r in failure_results:
                console.print(f"  [✗] {r.url}")
                console.print(f"      {r.error_message}")


# 默认导出目录（项目 data/export/ 目录）
DEFAULT_EXPORT_DIR = Path(__file__).parent.parent.parent / "data" / "export"


def _build_file_link(file_path: str, text: str = None, style: str = "bold blue") -> str:
    system = platform.system()
    text = text or file_path
    
    # 统一使用 file:// URL 格式
    normalized = file_path.replace("\\", "/")
    if system == "Windows" and len(normalized) >= 2 and normalized[1] == ":":
        # Windows: C:/Users -> /C:/Users
        normalized = "/" + normalized[0] + normalized[2:]
    url = f"file://{quote(normalized)}"
    
    return f"[{style} link {url}]{text}[/]"


def _get_latest_export_folder() -> Path:
    export_base = DEFAULT_EXPORT_DIR.resolve()
    
    if not export_base.exists():
        return export_base
    
    today = datetime.now().strftime("%y%m%d")
    today_folder = export_base / today
    if today_folder.exists():
        return today_folder
    
    folders = [f for f in export_base.iterdir() if f.is_dir()]
    if folders:
        return max(folders, key=lambda p: p.stat().st_mtime)
    return export_base


def print_folder_link() -> None:
    console = Console()
    export_dir = str(_get_latest_export_folder())
    
    if console.is_terminal:
        link = _build_file_link(export_dir, "点击打开文件夹", "bold blue")
        console.print("")
        console.print(link)
        console.print(f"[cyan]{export_dir}[/cyan]")
    else:
        console.print("")
        console.print(f"导出文件夹: {export_dir}")
