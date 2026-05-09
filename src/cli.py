"""命令行入口模块"""

import argparse
import asyncio
import re
import sys
import time
from pathlib import Path
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    from playwright.async_api import Page

from rich.console import Console
from rich.live import Live
from rich.table import Table

from src.config import GlobalConfig
from src.scraper import DoubaoSpider, FetchStep, FETCH_STEP_NAMES, STEP_COUNT, reset_timer, BrowserPool
from src.preprocessor import DoubaoHTMLParser, TextBlock
from src.generator import DocxBuilder, DocumentConfig, DocNamer, LinkRecord
from src.generator.batch_report import BatchReport, print_folder_link
from src.exceptions import CrawlerError, ParseError, ExportError

# 全局配置实例
_config = GlobalConfig.load()

# 从 URL 提取 thread ID 的正则
THREAD_ID_PATTERN = re.compile(r'/thread/([a-zA-Z0-9]+)')

# 全局任务管理器（用于进度回调）
_task_manager: "TaskManager | None" = None


@runtime_checkable
class ProgressReporter(Protocol):
    """进度报告者协议，CI 和 GUI 均需实现此协议"""
    def add_task(self, task_index: int, url_tag: str) -> Any: ...
    def update(self, task_index: int, step: int, status: str, result: str = "", elapsed: float = 0.0) -> None: ...
    def log_warning(self, msg: str) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...


def _get_url_tag(url: str) -> str:
    """
    从 URL 提取 thread ID 作为标签

    Args:
        url: 完整的豆包 URL

    Returns:
        thread ID 或截断的 URL
    """
    match = THREAD_ID_PATTERN.search(url)
    return match.group(1) if match else url[:_config.url_fallback_length]


@dataclass
class TaskStatus:
    """单个任务的状态"""
    task_index: int  # 任务序号
    total: int  # 总任务数
    url_tag: str  # URL 标签（thread ID 或截断的 URL）
    step: int = 0  # 当前步骤索引
    status: str = "等待中"  # 状态文本
    result: str = ""  # 结果或错误信息
    elapsed: float = 0.0  # 已耗时（秒）

    def to_line(self) -> str:
        """转换为纯文本行"""
        total = STEP_COUNT
        dots = "●" * self.step + "○" * (total - self.step) if self.step < total else "●" * total
        elapsed_str = f"({self.elapsed:.1f}s)" if self.elapsed > 0 else ""
        return f"[{self.task_index}/{self.total}][{self.url_tag}] {dots} [{self.status}] {elapsed_str} {self.result}"


class TaskManager:
    """
    任务进度管理器

    支持交互式终端（Rich Live）和非交互式终端（纯文本）两种模式。
    """

    def __init__(self, total: int):
        self.total: int = total  # 总任务数
        self.tasks: list[TaskStatus] = []  # 任务列表
        self._live: Optional[Live] = None  # Rich Live 显示实例
        self._console = Console()  # Rich 控制台
        # 检测是否为交互式终端
        self._is_interactive = self._console.is_terminal  # 是否交互式终端

    def add_task(self, task_index: int, url_tag: str) -> TaskStatus:
        """添加任务"""
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
        """构建 Rich 进度表格"""
        table = Table(show_header=True, show_lines=False, box=None, pad_edge=False)
        table.add_column("序号", width=4)
        table.add_column("进度", width=6)
        table.add_column("状态", width=8)
        table.add_column("耗时", width=5)
        table.add_column("结果", no_wrap=True, max_width=40)

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
                refresh_per_second=4,
                transient=False,
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

    def log_warning(self, msg: str) -> None:
        """实现 ProgressReporter 协议的日志警告方法"""
        print(f"⚠️ {msg}")

    def print_all(self) -> None:
        """打印所有任务状态（非交互式终端）"""
        if not self._is_interactive:
            for task in self.tasks:
                print(task.to_line())


async def fetch_and_export_single(
    url: str,
    output_dir: Path,
    anti_detect_level: str = "medium",
    task_index: int = 0,
    total: int = 1,
    namer: Optional["DocNamer"] = None,
    external_page: "Page | None" = None,
    reporter: Optional[ProgressReporter] = None,
) -> tuple[str, bool, str, Optional[str], int, str]:
    """
    单个 URL 的导出流程

    Args:
        url: 豆包聊天页面 URL
        output_dir: 输出目录
        anti_detect_level: 反爬级别
        task_index: 任务序号
        total: 总任务数
        namer: 文档命名器（共享实例）
        external_page: 外部页面（浏览器池复用）
        reporter: 进度报告者（可选）

    Returns:
        (url, success, filename, file_path, latex_fallback_count, title) 元组
    """
    global _task_manager

    url_tag = _get_url_tag(url)
    tag = f"[{task_index}/{total}][{url_tag}]"
    reset_timer()
    total_start = time.time()

    def on_progress(step: str) -> None:
        """爬虫进度回调"""
        step_value = step.value if isinstance(step, FetchStep) else step
        elapsed = time.time() - total_start
        step_idx = FETCH_STEP_NAMES.get(step_value, -1)
        if reporter:
            reporter.update(task_index, step_idx, step_value, elapsed=elapsed)
        elif _task_manager and step_value in FETCH_STEP_NAMES:
            _task_manager.update(task_index, step_idx, step_value, elapsed=elapsed)

    def update_step(name: str) -> None:
        """更新解析/生成步骤"""
        elapsed = time.time() - total_start
        step_idx = FETCH_STEP_NAMES.get(name, -1)
        if reporter:
            reporter.update(task_index, step_idx, name, elapsed=elapsed)
        elif _task_manager and name in FETCH_STEP_NAMES:
            _task_manager.update(task_index, step_idx, name, elapsed=elapsed)

    try:
        # 爬取页面
        async with DoubaoSpider(anti_detect_level=anti_detect_level, tag=url_tag, progress_callback=on_progress, external_page=external_page) as spider:
            chat_data = await spider.fetch(url)

        # 解析 HTML
        update_step("解析内容")
        parser = DoubaoHTMLParser()
        all_blocks: list[tuple[str, TextBlock]] = []
        total_fallback: int = 0

        for msg in chat_data.messages:
            parsed = parser.parse(msg.content)
            total_fallback += parsed.latex_fallback_count
            for block in parsed.blocks:
                all_blocks.append((msg.role, block))

        # 初始化文档命名器
        index_file = output_dir / "link_index.json"
        output_dir.mkdir(parents=True, exist_ok=True)
        if namer is None:
            namer = DocNamer(index_file)

        # 生成文件名
        filename_base = namer.get_filename(url, chat_data.title, update_title=False)

        # 构建输出路径
        date_str = namer.get_date_str()
        output_path = output_dir / "export" / date_str / f"{filename_base}.docx"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 生成文档
        update_step("生成文档")
        if not all_blocks:
            raise CrawlerError("未能提取到任何消息内容，可能是页面加载失败、需要登录或反爬拦截")

        config = DocumentConfig(title=chat_data.title, style_config=_config.document_style)
        builder = DocxBuilder(config)
        _ = await asyncio.to_thread(
            builder.build_blocks,
            chat_data.title,
            all_blocks,
            str(output_path),
        )

        fail_count, fail_urls = builder.get_image_failures()
        if fail_count > 0:
            doc_title = chat_data.title[:20] + "..." if len(chat_data.title) > 20 else chat_data.title
            warning_msg = f"图片下载失败: {doc_title} ({fail_count}张)"
            if reporter:
                reporter.log_warning(warning_msg)
            else:
                print(f"{tag} ⚠️ {warning_msg}")
            for url in fail_urls[:3]:
                print(f"    {url[:60]}...")
            if fail_count > 3:
                print(f"    ...还有{fail_count - 3}张")

        # 完成
        elapsed = time.time() - total_start
        if reporter:
            reporter.update(task_index, 10, "导出完成", f"{filename_base}.docx", elapsed=elapsed)
        elif _task_manager:
            _task_manager.update(task_index, 10, "导出完成", f"{filename_base}.docx", elapsed=elapsed)

        return url, True, f"{filename_base}.docx", str(output_path), total_fallback, chat_data.title

    except (CrawlerError, ParseError, ExportError) as e:
        error_msg = str(e)
        display_msg = error_msg[:100] + "..." if len(error_msg) > 100 else error_msg
        error_type = type(e).__name__.replace("Error", "")
        print(f"{tag} [✗] {error_type}失败: {display_msg}")
        if reporter:
            reporter.update(task_index, 10, "导出失败", error_msg[:50])
        elif _task_manager:
            _task_manager.update(task_index, 10, "导出失败", error_msg[:50])
        raise
    except Exception as e:
        error_msg = str(e)
        display_msg = error_msg[:100] + "..." if len(error_msg) > 100 else error_msg
        print(f"{tag} [✗] 失败: {display_msg}")
        if reporter:
            reporter.update(task_index, 10, "导出失败", error_msg[:50])
        elif _task_manager:
            _task_manager.update(task_index, 10, "导出失败", error_msg[:50])
        raise


async def fetch_and_export_batch(
    urls: list[str],
    output_dir: Path,
    anti_detect_level: str = "medium",
    concurrency: int = 5,
    reporter: Optional[ProgressReporter] = None,
) -> BatchReport:
    """
    批量导出多个 URL

    Args:
        urls: URL 列表
        output_dir: 输出目录
        anti_detect_level: 反爬级别
        concurrency: 并发数
        reporter: 进度报告者（可选）

    Returns:
        BatchReport: 包含成功/失败统计的报告
    """
    report = BatchReport()
    total = len(urls)

    # 初始化文档命名器
    index_file = output_dir / "link_index.json"
    namer = DocNamer(index_file)
    namer.cleanup_old_entries()

    # 预分配序号（避免并发导致序号冲突）
    used_indices = set()
    url_to_index = {}

    for url in urls:
        records = namer.get_today_records()
        if url in records and records[url].index > 0:
            url_to_index[url] = records[url].index
            used_indices.add(records[url].index)
        else:
            idx = namer.get_today_max_index() + 1
            while idx in used_indices:
                idx += 1
            url_to_index[url] = idx
            used_indices.add(idx)
            records[url] = LinkRecord(index=idx, title="")

    namer.save()

    # 浏览器池
    pool = BrowserPool(anti_detect_level=anti_detect_level)
    await pool.initialize()

    async def bounded_export(task_index: int, url: str):
        """带浏览器池复用的导出函数"""
        page = None
        try:
            page = await pool.acquire(concurrency)
            return await fetch_and_export_single(
                url, output_dir, anti_detect_level, task_index, total, namer,
                external_page=page, reporter=reporter
            )
        except Exception as e:
            return (url, False, str(e), None, 0, "")
        finally:
            if page is not None:
                await pool.release(page)

    try:
        tasks = [
            bounded_export(i + 1, url)
            for i, url in enumerate(urls)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        url_title_map: dict[str, str] = {}
        for result in results:
            if isinstance(result, Exception):
                report.add_failure("未知URL", str(result))
                continue
            if isinstance(result, tuple) and len(result) == 6:
                url, success, filename, file_path, fallback_count, chat_title = result
                report.latex_fallback_count += fallback_count
                if success:
                    report.add_success(url, filename, file_path if file_path else None)
                    url_title_map[url] = chat_title
                else:
                    report.add_failure(url, filename or "未知错误")

        # 统一更新 title
        for url, title in url_title_map.items():
            namer.update_title(url, title)
        namer.save()
    finally:
        await pool.close()

    return report


def main() -> int:
    """
    主入口函数

    Args:
        urls: 豆包聊天页面 URL（必需，支持多个）
        --level: 反爬级别（low/medium/high，默认 medium）
        --concurrency: 批量并发数（默认 5）

    Returns:
        0: 全部成功，1: 有失败任务
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

    print()

    output_dir = Path(__file__).parent.parent / "data"
    output_dir.mkdir(parents=True, exist_ok=True)

    from src.utils import windows_compat_setup, windows_compat_cleanup
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

        # 单 URL 串行，多 URL 并发
        if total == 1:
            urls = [args.urls[0]]
            concurrency = 1
        else:
            urls = args.urls
            concurrency = args.concurrency if args.concurrency is not None else _config.concurrency

        report = asyncio.run(fetch_and_export_batch(
            urls, output_dir, args.level, concurrency
        ))

        manager.stop()
        manager.print_all()
        _task_manager = None

        report.print_summary()
        print_folder_link()

        failure_count = sum(1 for r in report.results if not r.success)
        return 0 if failure_count == 0 else 1
    finally:
        windows_compat_cleanup()


if __name__ == "__main__":
    sys.exit(main())
