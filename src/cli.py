"""
命令行入口模块

本模块是整个程序的入口点，负责：
1. 解析命令行参数
2. 管理批量任务执行
3. 显示实时进度（Rich Live）
4. 生成最终报告

主要流程：
1. main() 解析参数，创建 TaskManager
2. fetch_and_export_batch() 批量执行导出任务
3. fetch_and_export_single() 单个任务执行
4. TaskManager 管理进度显示
"""

import argparse
import asyncio
import re
import sys
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.table import Table

from src.config import GlobalConfig
from src.scraper import DoubaoSpider, FetchStep, FETCH_STEP_NAMES, STEP_COUNT, reset_timer
from src.preprocessor import DoubaoHTMLParser, TextBlock
from src.generator import DocxBuilder, DocumentConfig, DocNamer, LinkRecord
from src.generator.batch_report import BatchReport, print_folder_link
from src.exceptions import CrawlerError, ParseError, ExportError

# 全局配置实例
_config = GlobalConfig()

# 预编译的正则表达式，用于从 URL 提取 thread ID
THREAD_ID_PATTERN = re.compile(r'/thread/([a-zA-Z0-9]+)')

# 全局任务管理器（用于进度回调）
_task_manager: "TaskManager | None" = None


def _get_url_tag(url: str) -> str:
    """
    从 URL 中提取 thread ID 作为简短标签

    用于在进度显示中标识不同的任务。

    Args:
        url: 完整的豆包 URL

    Returns:
        thread ID 或 URL 的前 N 个字符
    """
    match = THREAD_ID_PATTERN.search(url)
    return match.group(1) if match else url[:_config.url_fallback_length]


@dataclass
class TaskStatus:
    """
    单个任务的状态

    用于 TaskManager 追踪每个 URL 的导出进度。
    """
    task_index: int  # 任务序号（1-based）
    total: int  # 总任务数
    url_tag: str  # URL 标签（thread ID）
    step: int = 0  # 当前步骤（0-6）
    status: str = "等待中"  # 状态文本
    result: str = ""  # 结果或错误信息
    elapsed: float = 0.0  # 已耗时（秒）

    def to_line(self) -> str:
        """转换为纯文本行（非交互式终端使用）"""
        total = STEP_COUNT
        dots = "●" * self.step + "○" * (total - self.step) if self.step < total else "●" * total
        elapsed_str = f"({self.elapsed:.1f}s)" if self.elapsed > 0 else ""
        return f"[{self.task_index}/{self.total}][{self.url_tag}] {dots} [{self.status}] {elapsed_str} {self.result}"


class TaskManager:
    """
    任务管理器 - 管理批量任务的进度显示

    支持两种显示模式：
    1. 交互式终端：使用 Rich Live 动态刷新表格
    2. 非交互式终端：降级为纯文本打印

    使用方式：
    1. 创建实例并调用 start()
    2. 使用 add_task() 添加任务
    3. 使用 update() 更新进度
    4. 使用 stop() 停止显示
    """

    def __init__(self, total: int):
        self.total = total
        self.tasks: list[TaskStatus] = []
        self._live: Optional[Live] = None
        self._console = Console()
        # 检测是否为交互式终端
        self._is_interactive = self._console.is_terminal

    def add_task(self, task_index: int, url_tag: str) -> TaskStatus:
        """添加一个新任务"""
        task = TaskStatus(task_index=task_index, total=self.total, url_tag=url_tag)
        self.tasks.append(task)
        return task

    def update(self, task_index: int, step: int, status: str, result: str = "", elapsed: float = 0.0) -> None:
        """
        更新任务状态

        Args:
            task_index: 任务序号
            step: 步骤索引（0-6）
            status: 状态文本
            result: 结果或错误信息
            elapsed: 已耗时（秒）
        """
        for task in self.tasks:
            if task.task_index == task_index:
                task.step = step
                task.status = status
                task.result = result
                task.elapsed = elapsed
                break

        # 交互式终端使用 Live 刷新
        if self._is_interactive and self._live is not None:
            self._live.update(self._build_table())

    def _build_table(self) -> Table:
        """
        构建 Rich 表格

        使用 Unicode 字符显示进度：
        - ●: 已完成步骤
        - →: 当前步骤
        - ○: 未完成步骤
        """
        table = Table(show_header=True, show_lines=False, box=None, pad_edge=False)
        table.add_column("序号", width=4)
        table.add_column("进度", width=10)
        table.add_column("状态", width=8)
        table.add_column("耗时", width=5)
        table.add_column("结果", no_wrap=True, max_width=30)

        for task in self.tasks:
            total = STEP_COUNT
            if task.step >= total:
                # 完成状态 - 全绿
                dots = f"[green]{'●' * total}[/green]"
                status_style = "green"
                result_style = "green"
                elapsed_style = "green"
            elif task.step == 0:
                # 等待状态 - 全灰
                dots = f"[dim]{'○' * total}[/dim]"
                status_style = "dim"
                result_style = "dim"
                elapsed_style = "dim"
            else:
                # 进行中状态 - 绿点 + 黄箭头 + 灰点
                done = task.step
                current = "→"
                remaining = total - task.step - 1
                dots = f"[green]{'●' * done}[/green][yellow]{current}[/yellow][dim]{'○' * remaining}[/dim]"
                status_style = "yellow"
                result_style = "dim"
                elapsed_style = "yellow"

            status_text = f"[{status_style}]{task.status}[/{status_style}]"
            elapsed_text = f"[{elapsed_style}]{task.elapsed:.1f}s[/{elapsed_style}]" if task.elapsed > 0 else ""
            result_text = f"[{result_style}]{task.result}[/{result_style}]" if task.result else ""

            table.add_row(
                f"[cyan][{task.task_index}][{task.url_tag}][/cyan]",
                dots,
                status_text,
                elapsed_text,
                result_text,
            )

        return table

    def start(self) -> None:
        """启动进度显示"""
        if self._is_interactive:
            self._live = Live(
                self._build_table(),
                console=self._console,
                refresh_per_second=4,  # 每秒刷新4次
                transient=False,  # 停止时保留最终状态
            )
            self._live.start()

    def stop(self) -> None:
        """停止进度显示"""
        if self._live is not None:
            self._live.stop()
            self._live = None

    def clear(self) -> None:
        """清除进度显示"""
        if self._live is not None:
            self._live.stop()
            self._live = None

    def print_all(self) -> None:
        """打印所有任务状态（非交互式终端）"""
        if self._is_interactive:
            pass  # 交互式终端已通过 Live 显示
        else:
            for task in self.tasks:
                print(task.to_line())


async def fetch_and_export_single(
    url: str,
    output_dir: Path,
    anti_detect_level: str = "medium",
    task_index: int = 0,
    total: int = 1,
    namer: Optional["DocNamer"] = None,
) -> tuple[str, bool, str, Optional[str]]:
    """
    单个 URL 的导出流程

    执行步骤：
    1. 使用 DoubaoSpider 爬取页面内容
    2. 使用 DoubaoHTMLParser 解析 HTML
    3. 使用 DocxBuilder 生成 Word 文档
    4. 更新 TaskManager 进度

    Args:
        url: 豆包聊天页面 URL
        output_dir: 输出目录
        anti_detect_level: 反爬级别
        task_index: 任务序号
        total: 总任务数
        namer: 文档命名器（共享实例用于批量操作）

    Returns:
        (url, success, filename, file_path) 元组
    """
    global _task_manager

    url_tag = _get_url_tag(url)
    tag = f"[{task_index}/{total}][{url_tag}]"
    reset_timer()
    total_start = time.time()

    def on_progress(step: str) -> None:
        """爬虫进度回调"""
        step_value = step.value if isinstance(step, FetchStep) else step
        if _task_manager:
            elapsed = time.time() - total_start
            if step_value in FETCH_STEP_NAMES:
                step_idx = FETCH_STEP_NAMES[step_value]
            elif step_value.startswith("滚动"):
                step_idx = FETCH_STEP_NAMES["滚动加载"]
            else:
                return
            _task_manager.update(task_index, step_idx, step_value, elapsed=elapsed)

    def update_step(name: str) -> None:
        """更新解析/生成步骤"""
        if _task_manager and name in FETCH_STEP_NAMES:
            elapsed = time.time() - total_start
            step_idx = FETCH_STEP_NAMES[name]
            _task_manager.update(task_index, step_idx, name, elapsed=elapsed)

    try:
        # 步骤 1-7: 爬取页面
        async with DoubaoSpider(anti_detect_level=anti_detect_level, tag=url_tag, progress_callback=on_progress) as spider:
            chat_data = await spider.fetch(url)

        # 步骤 8: 解析 HTML
        update_step("解析内容")

        parser = DoubaoHTMLParser()
        all_blocks: list[tuple[str, TextBlock]] = []

        # 将消息按角色分类
        for msg in chat_data.messages:
            parsed = parser.parse(msg.content)
            for block in parsed.blocks:
                all_blocks.append((msg.role, block))

        # 创建输出目录
        index_file = output_dir / "link_index.json"
        output_dir.mkdir(parents=True, exist_ok=True)

        # 共享文档命名器（用于批量操作保持序号一致）
        if namer is None:
            namer = DocNamer(index_file)

        # 生成文件名
        filename_base = namer.get_filename(url, chat_data.title)

        # 构建输出路径
        date_str = namer.get_date_str()
        output_path = output_dir / "export" / date_str / f"{filename_base}.docx"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 步骤 9: 生成文档
        update_step("生成文档")

        config = DocumentConfig(title=chat_data.title)
        builder = DocxBuilder(config)
        builder.build_blocks(chat_data.title, all_blocks, str(output_path))

        fail_count, fail_urls = builder.get_image_failures()
        if fail_count > 0:
            doc_title = chat_data.title[:20] + "..." if len(chat_data.title) > 20 else chat_data.title
            print(f"{tag} ⚠️ 图片下载失败: {doc_title} ({fail_count}张)")
            for url in fail_urls[:3]:
                print(f"    {url[:60]}...")
            if fail_count > 3:
                print(f"    ...还有{fail_count - 3}张")

        # 步骤 10: 完成
        elapsed = time.time() - total_start
        if _task_manager:
            _task_manager.update(task_index, 10, "导出完成", f"{filename_base}.docx", elapsed=elapsed)

        return url, True, f"{filename_base}.docx", str(output_path)

    except (CrawlerError, ParseError, ExportError) as e:
        error_msg = str(e)
        display_msg = error_msg[:100] + "..." if len(error_msg) > 100 else error_msg
        error_type = type(e).__name__.replace("Error", "")
        print(f"{tag} [✗] {error_type}失败: {display_msg}")
        if _task_manager:
            _task_manager.update(task_index, 10, "导出失败", error_msg[:50])
        raise
    except Exception as e:
        error_msg = str(e)
        display_msg = error_msg[:100] + "..." if len(error_msg) > 100 else error_msg
        print(f"{tag} [✗] 失败: {display_msg}")
        if _task_manager:
            _task_manager.update(task_index, 10, "导出失败", error_msg[:50])
        raise


async def fetch_and_export_batch(
    urls: list[str],
    output_dir: Path,
    anti_detect_level: str = "medium",
    concurrency: int = 5,
) -> BatchReport:
    """
    批量导出多个 URL

    使用 asyncio.Semaphore 控制并发数，实现批量并发导出。

    Args:
        urls: URL 列表
        output_dir: 输出目录
        anti_detect_level: 反爬级别
        concurrency: 并发数

    Returns:
        BatchReport: 包含成功/失败统计的报告
    """
    report = BatchReport()
    total = len(urls)

    # 初始化文档命名器（共享实例保证序号一致）
    index_file = Path("data/link_index.json")
    namer = DocNamer(index_file)
    namer.cleanup_old_entries()

    # 预分配序号（避免并发导致序号冲突）
    used_indices = set()
    url_to_index = {}

    for url in urls:
        records = namer.get_today_records()
        if url in records and records[url].index > 0:
            # URL 已有记录，复用序号
            url_to_index[url] = records[url].index
            used_indices.add(records[url].index)
        else:
            # 新 URL，分配新序号
            idx = namer.get_today_max_index() + 1
            while idx in used_indices:
                idx += 1
            url_to_index[url] = idx
            used_indices.add(idx)
            records[url] = LinkRecord(index=idx, title="")

    namer.save()

    # 创建信号量限制并发数
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded_export(task_index: int, url: str):
        """带并发限制的导出函数"""
        async with semaphore:
            return await fetch_and_export_single(
                url, output_dir, anti_detect_level, task_index, total, namer
            )

    # 创建所有任务
    tasks = [
        bounded_export(i + 1, url)
        for i, url in enumerate(urls)
    ]

    # 并发执行
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 收集结果
    for result in results:
        if isinstance(result, Exception):
            error_type = type(result).__name__
            report.add_failure(str(result), f"{error_type}")
        elif isinstance(result, tuple) and len(result) == 4:
            url, success, filename, file_path = result
            if success:
                report.add_success(url, filename, file_path if file_path else None)
            else:
                report.add_failure(url, filename or "未知错误")

    return report


def main() -> int:
    """
    主入口函数

    命令行参数：
    - urls: 豆包聊天页面 URL（必需，支持多个）
    - --level: 反爬级别（low/medium/high，默认 medium）
    - --concurrency: 批量并发数（默认 5）

    返回值：
    - 0: 全部成功
    - 1: 有失败的任务
    """
    parser = argparse.ArgumentParser(
        description="导出豆包聊天记录为Word文档",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 -m src.cli https://www.doubao.com/thread/ad8e9da8e8159
  python3 -m src.cli url1 url2 url3
  python3 -m src.cli https://www.doubao.com/thread/test --level high
  python3 -m src.cli https://www.doubao.com/thread/test --concurrency 5

注意: Windows PowerShell 用户可使用 'py -3 -m src.cli' 或 'python3'
      中文显示异常时，先运行 'chcp 65001' 切换到 UTF-8
        """,
    )

    parser.add_argument("urls", nargs="+", help="豆包聊天页面URL（支持多个）")
    parser.add_argument("--level", choices=["low", "medium", "high"], default="medium", help="反爬级别")
    parser.add_argument("--concurrency", type=int, default=None, help="并发数（默认: 5）")

    args = parser.parse_args()

    # 输出空行，避免日志直接贴在命令行后面
    print()

    output_dir = Path(__file__).parent.parent / "data"
    output_dir.mkdir(parents=True, exist_ok=True)

    from src.utils import windows_compat_setup, windows_compat_cleanup

    # Windows 平台兼容性处理
    windows_compat_setup()

    try:
        total = len(args.urls)

        # 初始化任务管理器
        global _task_manager
        manager = TaskManager(total)
        _task_manager = manager
        for i, url in enumerate(args.urls):
            url_tag = _get_url_tag(url)
            manager.add_task(i + 1, url_tag)
        manager.start()

        # 单 URL 使用串行，多 URL 使用并发
        if total == 1:
            urls = [args.urls[0]]
            concurrency = 1
        else:
            urls = args.urls
            # 命令行参数 > 配置文件 > 默认值
            concurrency = args.concurrency if args.concurrency is not None else _config.concurrency

        # 执行批量导出
        report = asyncio.run(fetch_and_export_batch(
            urls, output_dir, args.level, concurrency
        ))

        manager.stop()
        manager.print_all()
        _task_manager = None

        # 打印汇总报告
        report.print_summary()
        print_folder_link()

        failure_count = sum(1 for r in report.results if not r.success)
        return 0 if failure_count == 0 else 1
    finally:
        # Windows 平台资源清理
        windows_compat_cleanup()


if __name__ == "__main__":
    sys.exit(main())
