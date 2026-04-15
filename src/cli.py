"""命令行入口模块"""

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
from src.scraper import DoubaoSpider
from src.scraper.crawler import reset_timer
from src.preprocessor import DoubaoHTMLParser, TextBlock
from src.generator import DocxBuilder, DocumentConfig, DocNamer, LinkRecord
from src.generator.batch_report import BatchReport, print_folder_link
from src.exceptions import CrawlerError, ParseError, ExportError

# 全局配置实例
_config = GlobalConfig()

# 预编译的正则表达式，用于从 URL 提取 thread ID
THREAD_ID_PATTERN = re.compile(r'/thread/([a-zA-Z0-9]+)')

# 步骤名称 (与 FetchStep 对应)
FETCH_STEP_NAMES = {
    "任务开始": 0,
    "收到任务": 1,
    "访问页面": 2,
    "加载完成": 3,
    "滚动加载": 4,
    "展开代码": 5,
    "提取数据": 6,
    "爬取完成": 7,
    "解析内容": 8,
    "生成文档": 9,
}


# 全局任务管理器
_task_manager: "TaskManager | None" = None


def _get_url_tag(url: str) -> str:
    """提取 URL 中的 thread ID 作为标签"""
    match = THREAD_ID_PATTERN.search(url)
    return match.group(1) if match else url[:_config.url_fallback_length]


@dataclass
class TaskStatus:
    task_index: int
    total: int
    url_tag: str
    step: int = 0
    status: str = "等待中"
    result: str = ""
    elapsed: float = 0.0
    
    def to_line(self) -> str:
        dots = "●" * self.step + "○" * (10 - self.step) if self.step < 10 else "●●●●●●●●●●"
        elapsed_str = f"({self.elapsed:.1f}s)" if self.elapsed > 0 else ""
        return f"[{self.task_index}/{self.total}][{self.url_tag}] {dots} [{self.status}] {elapsed_str} {self.result}"


class TaskManager:
    """支持交互式终端动态刷新，非交互式终端降级为纯文本"""
    
    def __init__(self, total: int):
        self.total = total
        self.tasks: list[TaskStatus] = []
        self._live: Optional[Live] = None
        self._console = Console()
        self._is_interactive = self._console.is_terminal
    
    def add_task(self, task_index: int, url_tag: str) -> TaskStatus:
        task = TaskStatus(task_index=task_index, total=self.total, url_tag=url_tag)
        self.tasks.append(task)
        return task
    
    def update(self, task_index: int, step: int, status: str, result: str = "", elapsed: float = 0.0) -> None:
        for task in self.tasks:
            if task.task_index == task_index:
                task.step = step
                task.status = status
                task.result = result
                task.elapsed = elapsed
                break
        
        if self._is_interactive and self._live is not None:
            self._live.update(self._build_table())
    
    def _build_table(self) -> Table:
        table = Table(show_header=True, show_lines=False, box=None, pad_edge=False)
        table.add_column("序号", width=4)
        table.add_column("进度", width=10)
        table.add_column("状态", width=8)
        table.add_column("耗时", width=5)
        table.add_column("结果", no_wrap=True, max_width=30)
        
        for task in self.tasks:
            if task.step >= 10:
                dots = "[green]●●●●●●●●●●[/green]"
                status_style = "green"
                result_style = "green"
                elapsed_style = "green"
            elif task.step == 0:
                dots = "[dim]○○○○○○○○○○[/dim]"
                status_style = "dim"
                result_style = "dim"
                elapsed_style = "dim"
            else:
                done = task.step
                current = "→"
                remaining = 10 - task.step - 1
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
        if self._is_interactive:
            self._live = Live(
                self._build_table(),
                console=self._console,
                refresh_per_second=4,
                transient=False,
            )
            self._live.start()
    
    def stop(self) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None
    
    def clear(self) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None
    
    def print_all(self) -> None:
        if self._is_interactive:
            pass
        else:
            for task in self.tasks:
                print(task.to_line())


async def fetch_and_export_single(
    url: str,
    output_dir: Path,
    anti_detect_level: str = "medium",
    task_index: int = 0,
    total: int = 1,
    namer: "DocNamer" = None,
) -> tuple[str, bool, str, str | None]:
    global _task_manager
    
    url_tag = _get_url_tag(url)
    tag = f"[{task_index}/{total}][{url_tag}]"
    reset_timer()
    total_start = time.time()
    
    def on_progress(step: str) -> None:
        if _task_manager and step in FETCH_STEP_NAMES:
            elapsed = time.time() - total_start
            step_idx = FETCH_STEP_NAMES[step]
            _task_manager.update(task_index, step_idx, step, elapsed=elapsed)
    
    def update_step(name: str) -> None:
        if _task_manager and name in FETCH_STEP_NAMES:
            elapsed = time.time() - total_start
            step_idx = FETCH_STEP_NAMES[name]
            _task_manager.update(task_index, step_idx, name, elapsed=elapsed)
    
    try:
        async with DoubaoSpider(anti_detect_level=anti_detect_level, tag=url_tag, progress_callback=on_progress) as spider:
            chat_data = await spider.fetch(url)
        
        update_step("解析内容")
        
        parser = DoubaoHTMLParser()
        all_blocks: list[tuple[str, TextBlock]] = []
        
        for msg in chat_data.messages:
            parsed = parser.parse(msg.content)
            for block in parsed.blocks:
                all_blocks.append((msg.role, block))
        
        index_file = output_dir / "link_index.json"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if namer is None:
            namer = DocNamer(index_file)
        
        filename_base = namer.get_filename(url, chat_data.title)
        
        date_str = namer.get_date_str()
        output_path = output_dir / "export" / date_str / f"{filename_base}.docx"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        update_step("生成文档")
        
        config = DocumentConfig(title=chat_data.title)
        builder = DocxBuilder(config)
        builder.build_blocks(chat_data.title, all_blocks, str(output_path))
        
        elapsed = time.time() - total_start
        if _task_manager:
            _task_manager.update(task_index, 10, "导出完成", f"{filename_base}.docx", elapsed=elapsed)
        
        return url, True, f"{filename_base}.docx", str(output_path)
        
    except CrawlerError as e:
        error_msg = str(e)
        display_msg = error_msg[:100] + "..." if len(error_msg) > 100 else error_msg
        print(f"{tag} [✗] 爬取失败: {display_msg}")
        if _task_manager:
            _task_manager.update(task_index, 10, "导出失败", error_msg[:50])
        raise
    except ParseError as e:
        error_msg = str(e)
        display_msg = error_msg[:100] + "..." if len(error_msg) > 100 else error_msg
        print(f"{tag} [✗] 解析失败: {display_msg}")
        if _task_manager:
            _task_manager.update(task_index, 10, "导出失败", error_msg[:50])
        raise
    except ExportError as e:
        error_msg = str(e)
        display_msg = error_msg[:100] + "..." if len(error_msg) > 100 else error_msg
        print(f"{tag} [✗] 导出失败: {display_msg}")
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
    """批量导出多个 URL（TaskManager 由调用方管理）"""
    report = BatchReport()
    total = len(urls)
    
    index_file = Path("data/link_index.json")
    namer = DocNamer(index_file)
    namer._cleanup_old_entries()
    namer._load()
    
    used_indices = set()
    url_to_index = {}
    
    for url in urls:
        records = namer._get_today_records()
        if url in records and records[url].index > 0:
            url_to_index[url] = records[url].index
            used_indices.add(records[url].index)
        else:
            idx = namer._get_today_max_index() + 1
            while idx in used_indices:
                idx += 1
            url_to_index[url] = idx
            used_indices.add(idx)
            records[url] = LinkRecord(index=idx, title="")
    
    namer._save()
    
    semaphore = asyncio.Semaphore(concurrency)
    
    async def bounded_export(task_index: int, url: str):
        async with semaphore:
            return await fetch_and_export_single(
                url, output_dir, anti_detect_level, task_index, total, namer
            )
    
    tasks = [
        bounded_export(i + 1, url)
        for i, url in enumerate(urls)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for result in results:
        if isinstance(result, Exception):
            error_type = type(result).__name__
            report.add_failure(str(result), f"{error_type}")
        else:
            url, success, filename, file_path = result
            if success:
                report.add_success(url, filename, file_path)
            else:
                report.add_failure(url, filename or "未知错误")
    
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="导出豆包聊天记录为Word文档",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m src.cli https://www.doubao.com/thread/ad8e9da8e8159
  python -m src.cli url1 url2 url3
  python -m src.cli https://www.doubao.com/thread/test --level high
  python -m src.cli https://www.doubao.com/thread/test --concurrency 5
        """,
    )
    
    parser.add_argument("urls", nargs="+", help="豆包聊天页面URL（支持多个）")
    parser.add_argument("--level", choices=["low", "medium", "high"], default="medium", help="反爬级别")
    parser.add_argument("--concurrency", type=int, default=5, help="并发数（默认: 5）")
    
    args = parser.parse_args()
    
    output_dir = Path(__file__).parent.parent / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    import platform
    import warnings
    import gc
    
    if platform.system() == "Windows":
        warnings.filterwarnings("ignore", category=ResourceWarning)
    
    try:
        total = len(args.urls)
        
        global _task_manager
        manager = TaskManager(total)
        _task_manager = manager
        for i, url in enumerate(args.urls):
            url_tag = _get_url_tag(url)
            manager.add_task(i + 1, url_tag)
        manager.start()
        
        if total == 1:
            urls = [args.urls[0]]
            concurrency = 1
        else:
            urls = args.urls
            concurrency = args.concurrency
        
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
        if platform.system() == "Windows":
            gc.collect()


if __name__ == "__main__":
    sys.exit(main())
