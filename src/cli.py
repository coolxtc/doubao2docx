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
from src.generator import DocxBuilder, DocumentConfig, DocNamer
from src.generator.batch_report import BatchReport
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
    "页面加载完成": 3,
    "滚动加载": 4,
    "展开代码块": 5,
    "提取数据": 6,
    "爬取完成": 7,
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
    status: str = "等待"
    result: str = ""
    elapsed: float = 0.0
    
    def to_line(self) -> str:
        dots = "●" * self.step + "○" * (9 - self.step) if self.step < 9 else "●●●●●●●●●"
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
        table.add_column("序号", width=None)
        table.add_column("进度", width=10)
        table.add_column("状态", width=None)
        table.add_column("耗时", width=6)
        table.add_column("结果", width=None)
        
        for task in self.tasks:
            if task.step >= 8:
                dots = "[green]●●●●●●●●[/green]"
                status_style = "green"
                result_style = "green"
                elapsed_style = "green"
            elif task.step == 0:
                dots = "[dim]○○○○○○○○[/dim]"
                status_style = "dim"
                result_style = "dim"
                elapsed_style = "dim"
            else:
                done = task.step
                current = "→"
                remaining = 8 - task.step - 1
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
    custom_index: int | None = None,
    task_index: int = 0,
    total: int = 1,
) -> tuple[str, bool, str | None, str | None]:
    """单个 URL 导出，返回 (url, success, filename, error)"""
    global _task_manager
    
    url_tag = _get_url_tag(url)
    tag = f"[{task_index}/{total}][{url_tag}]"
    reset_timer()
    total_start = time.time()
    _step_start_time = time.time()
    
    def on_progress(step: str) -> None:
        global _task_manager
        if _task_manager and step in FETCH_STEP_NAMES:
            # elapsed: 当前步骤完成后到现在的耗时（秒）
            elapsed = time.time() - _step_start_time
            step_idx = FETCH_STEP_NAMES[step]
            _task_manager.update(task_index, step_idx, step, elapsed=elapsed)
    
    try:
        async with DoubaoSpider(anti_detect_level=anti_detect_level, tag=url_tag, progress_callback=on_progress) as spider:
            chat_data = await spider.fetch(url)
        
        parser = DoubaoHTMLParser()
        all_blocks: list[tuple[str, TextBlock]] = []
        
        for msg in chat_data.messages:
            parsed = parser.parse(msg.content)
            for block in parsed.blocks:
                all_blocks.append((msg.role, block))
        
        index_file = output_dir / "link_index.json"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        namer = DocNamer(index_file)
        filename_base = namer.get_filename(url, chat_data.title, custom_index)
        
        date_str = namer.get_date_str()
        output_path = output_dir / "export" / date_str / f"{filename_base}.docx"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        config = DocumentConfig(title=chat_data.title)
        builder = DocxBuilder(config)
        builder.build_blocks(chat_data.title, all_blocks, str(output_path))
        
        elapsed = time.time() - total_start
        if _task_manager:
            _task_manager.update(task_index, 8, "完成", f"{filename_base}.docx", elapsed=elapsed)
        
        return url, True, f"{filename_base}.docx", None
        
    except CrawlerError as e:
        error_msg = str(e)
        display_msg = error_msg[:100] + "..." if len(error_msg) > 100 else error_msg
        print(f"{tag} [✗] 爬取失败: {display_msg}")
        if _task_manager:
            _task_manager.update(task_index, 8, "失败", error_msg[:50])
        raise
    except ParseError as e:
        error_msg = str(e)
        display_msg = error_msg[:100] + "..." if len(error_msg) > 100 else error_msg
        print(f"{tag} [✗] 解析失败: {display_msg}")
        if _task_manager:
            _task_manager.update(task_index, 8, "失败", error_msg[:50])
        raise
    except ExportError as e:
        error_msg = str(e)
        display_msg = error_msg[:100] + "..." if len(error_msg) > 100 else error_msg
        print(f"{tag} [✗] 导出失败: {display_msg}")
        if _task_manager:
            _task_manager.update(task_index, 8, "失败", error_msg[:50])
        raise
    except Exception as e:
        error_msg = str(e)
        display_msg = error_msg[:100] + "..." if len(error_msg) > 100 else error_msg
        print(f"{tag} [✗] 失败: {display_msg}")
        if _task_manager:
            _task_manager.update(task_index, 8, "失败", error_msg[:50])
        raise


async def bounded_export_with_retry(
    url: str,
    output_dir: Path,
    anti_detect_level: str,
    custom_index: int | None,
    task_index: int,
    total: int,
    config: GlobalConfig,
) -> tuple[str, bool, str | None, str | None]:
    crawler_cfg = config.crawler
    max_attempts = crawler_cfg.retry_max_attempts
    
    if max_attempts <= 0:
        return await fetch_and_export_single(
            url, output_dir, anti_detect_level, custom_index, task_index, total
        )
    
    base_delay = crawler_cfg.retry_base_delay_ms / 1000
    max_delay = crawler_cfg.retry_max_delay_ms / 1000
    backoff_factor = crawler_cfg.retry_backoff_factor
    
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await fetch_and_export_single(
                url, output_dir, anti_detect_level, custom_index, task_index, total
            )
        except (CrawlerError, ParseError, ExportError) as e:
            last_error = e
            if attempt < max_attempts:
                delay = min(base_delay * (backoff_factor ** (attempt - 1)), max_delay)
                url_tag = _get_url_tag(url)
                tag = f"[{task_index}/{total}][{url_tag}]"
                print(f"{tag} [!] 第 {attempt} 次重试失败: {str(e)[:50]}, {delay:.1f}s 后重试...")
                await asyncio.sleep(delay)
    
    raise last_error


async def fetch_and_export_batch(
    urls: list[str],
    output_dir: Path,
    anti_detect_level: str = "medium",
    concurrency: int = 5,
) -> BatchReport:
    """批量导出多个 URL"""
    report = BatchReport()
    total = len(urls)
    
    print(f"[批次导出模式] 并发数: {concurrency}")
    print(f"总计 {total} 个 URL\n")
    
    # 预分配序号：已有 URL 复用序号，新 URL 按顺序分配
    # 按入参顺序遍历，仅对未记录的新 URL 分配序号
    index_file = Path("data/link_index.json")
    namer = DocNamer(index_file)
    namer._cleanup_old_entries()
    namer._load()  # 确保读取最新状态
    records = namer._get_today_records()
    
    # 已有 URL 集合（用于判断是否需要分配新序号）
    existing_urls = set(records.keys())
    # 新 URL 按入参顺序分配序号，起始值为当天最大序号+1
    next_new_index = namer._get_today_max_index() + 1
    url_to_index: dict[str, int] = {}
    
    for url in urls:
        if url not in existing_urls:
            url_to_index[url] = next_new_index
            next_new_index += 1
    
    global _task_manager
    manager = TaskManager(total)
    _task_manager = manager
    for i, url in enumerate(urls):
        url_tag = _get_url_tag(url)
        manager.add_task(i + 1, url_tag)
    manager.start()
    
    semaphore = asyncio.Semaphore(concurrency)
    
    async def bounded_export(task_index: int, url: str, custom_index: int | None):
        async with semaphore:
            return await fetch_and_export_single(
                url, output_dir, anti_detect_level, custom_index, task_index, total
            )
    
    tasks = [
        bounded_export(i + 1, url, url_to_index.get(url))
        for i, url in enumerate(urls)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    manager.stop()
    manager.print_all()
    _task_manager = None
    
    for result in results:
        if isinstance(result, Exception):
            error_type = type(result).__name__
            report.add_failure(str(result), f"{error_type}")
        else:
            url, success, filename, error = result
            if success:
                report.add_success(url, filename)
            else:
                report.add_failure(url, error or "未知错误")
    
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
    parser.add_argument("--index", type=int, default=None, help="手动指定文档序号（仅单URL模式）")
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
        if len(args.urls) == 1:
            result = asyncio.run(bounded_export_with_retry(
                args.urls[0], output_dir, args.level, args.index, 1, 1, _config
            ))
            return 0 if result[1] else 1
        else:
            report = asyncio.run(fetch_and_export_batch(
                args.urls, output_dir, args.level, args.concurrency
            ))
            report.print_summary()
            failure_count = sum(1 for r in report.results if not r.success)
            return 0 if failure_count == 0 else 1
    finally:
        if platform.system() == "Windows":
            gc.collect()


if __name__ == "__main__":
    sys.exit(main())
