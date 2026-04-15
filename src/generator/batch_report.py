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

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ExportResult:
    """单条导出结果 - 记录一次导出操作的结果
    
    用于汇总批量导出的各项结果，无论是成功还是失败都有记录。
    
    属性说明：
        url: 被导出的 URL
        success: 是否导出成功
        filename: 成功时为文件名，失败时为 None
        error_message: 失败时为错误原因，成功时为 None
    """
    url: str
    success: bool
    filename: Optional[str] = None
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

    def add_success(self, url: str, filename: str) -> None:
        """记录一次成功的导出
        
        Args:
            url: 被导出的 URL
            filename: 生成的文档文件名
        """
        self.results.append(ExportResult(url=url, success=True, filename=filename))

    def add_failure(self, url: str, error: str) -> None:
        """记录一次失败的导出
        
        Args:
            url: 被导出的 URL
            error: 错误原因描述
        """
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
        
        # 添加报告尾部
        lines.extend(["-" * 50, "=" * 50])
        return "\n".join(lines)

    def print_summary(self) -> None:
        """打印汇总报告
        
        将格式化后的报告内容打印到终端。
        报告只输出到终端，不保存本地文件。
        """
        print("\n" + self._format_report())
