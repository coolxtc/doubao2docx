"""
批量导出报告生成器模块

生成批量导出的汇总报告，记录成功和失败情况。
使用 Rich 库实现终端彩色输出和可点击链接。
"""

import platform
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from rich.console import Console


@dataclass
class ExportResult:
    """单条导出结果的数据类"""
    url: str
    success: bool
    filename: Optional[str] = None
    file_path: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class BatchReport:
    """收集和管理多次导出结果，提供汇总报告"""
    results: list[ExportResult] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    latex_fallback_count: int = 0  # 公式识别回退计数

    def add_success(self, url: str, filename: str, file_path: Optional[str] = None) -> None:
        """记录成功的导出"""
        self.results.append(ExportResult(url=url, success=True, filename=filename, file_path=file_path))

    def add_failure(self, url: str, error: str) -> None:
        """记录失败的导出"""
        self.results.append(ExportResult(url=url, success=False, error_message=error))

    def _format_report(self) -> str:
        """格式化报告文本（用于日志）"""
        total = len(self.results)
        success_count = sum(1 for r in self.results if r.success)
        failure_count = total - success_count

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

        success_results = [r for r in self.results if r.success]
        if success_results:
            lines.append("成功:")
            for r in success_results:
                lines.append(f"  [✓] {r.filename}")
            lines.append("")

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
        """打印汇总报告到终端"""
        console = Console()
        success_results = [r for r in self.results if r.success]
        failure_results = [r for r in self.results if not r.success]

        elapsed_seconds = time.time() - self.start_time.timestamp()

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

        # 公式识别回退警告
        if self.latex_fallback_count > 0:
            console.print("")
            console.print(f"[yellow]⚠ [警告] 豆包页面更新，公式识别策略已回退（{self.latex_fallback_count}个公式），请重点检查文档中的公式[/yellow]")

        console.print("")
        console.print(f"[bold]本次任务共耗时: {elapsed_seconds:.1f} 秒[/bold]")


# 默认导出目录（项目 data/export/ 目录）
DEFAULT_EXPORT_DIR = Path(__file__).parent.parent.parent / "data" / "export"


def _build_file_link(file_path: str, text: str | None = None, style: str = "bold blue") -> str:
    """构建跨平台的文件链接"""
    system = platform.system()
    text = text or file_path

    # 统一路径分隔符
    normalized = file_path.replace("\\", "/")

    # Windows 路径转换：C:/Users -> /C:/Users
    if system == "Windows" and len(normalized) >= 2 and normalized[1] == ":":
        normalized = "/" + normalized[0] + normalized[2:]

    # URL 编码
    url = f"file://{quote(normalized)}"

    # Rich 格式的链接
    return f"[{style} link {url}]{text}[/]"


def _get_latest_export_folder() -> Path:
    """获取最新的导出文件夹"""
    export_base = DEFAULT_EXPORT_DIR.resolve()

    if not export_base.exists():
        return export_base

    today = datetime.now().strftime("%y%m%d")
    today_folder = export_base / today
    if today_folder.exists():
        return today_folder

    # 查找最近修改的文件夹
    folders = [f for f in export_base.iterdir() if f.is_dir()]
    if folders:
        return max(folders, key=lambda p: p.stat().st_mtime)
    return export_base


def print_folder_link() -> None:
    """打印导出文件夹链接"""
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
