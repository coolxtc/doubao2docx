"""批量导出报告生成器"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ExportResult:
    url: str
    success: bool
    filename: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class BatchReport:
    results: list[ExportResult] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)

    def add_success(self, url: str, filename: str) -> None:
        self.results.append(ExportResult(url=url, success=True, filename=filename))

    def add_failure(self, url: str, error: str) -> None:
        self.results.append(ExportResult(url=url, success=False, error_message=error))

    def _format_report(self) -> str:
        total = len(self.results)
        success_count = sum(1 for r in self.results if r.success)
        failure_count = total - success_count
        
        lines = [
            "=" * 50,
            f"批量导出报告 - {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
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
        print("\n" + self._format_report())
