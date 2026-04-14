"""命令行入口模块"""

import argparse
import asyncio
import re
import sys
import time
from pathlib import Path

from src.config import GlobalConfig
from src.scraper import DoubaoSpider
from src.scraper.crawler import reset_timer
from src.preprocessor.doubao_parser import DoubaoHTMLParser, TextBlock
from src.generator import DocxBuilder, DocumentConfig, DocNamer
from src.generator.batch_report import BatchReport

# 全局配置实例
_config = GlobalConfig()

# 预编译的正则表达式，用于从 URL 提取 thread ID
THREAD_ID_PATTERN = re.compile(r'/thread/([a-zA-Z0-9]+)')


def _get_url_tag(url: str) -> str:
    """提取 URL 中的 thread ID 作为标签"""
    match = THREAD_ID_PATTERN.search(url)
    return match.group(1) if match else url[:_config.url_fallback_length]


async def fetch_and_export_single(
    url: str,
    output_dir: Path,
    anti_detect_level: str = "medium",
    custom_index: int | None = None,
    task_index: int = 0,
    total: int = 1,
) -> tuple[str, bool, str | None, str | None]:
    """单个 URL 导出，返回 (url, success, filename, error)"""
    url_tag = _get_url_tag(url)
    tag = f"[{task_index}/{total}][{url_tag}]"
    reset_timer()
    total_start = time.time()
    print(f"{tag} 开始导出")
    
    try:
        async with DoubaoSpider(anti_detect_level=anti_detect_level, tag=url_tag) as spider:
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
        
        date_str = filename_base[:6]
        output_path = output_dir / "export" / date_str / f"{filename_base}.docx"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        config = DocumentConfig(title=chat_data.title)
        builder = DocxBuilder(config)
        builder.build_blocks(chat_data.title, all_blocks, str(output_path))
        
        elapsed = time.time() - total_start
        print(f"{tag} [✓] {filename_base}.docx ({elapsed:.1f}秒)")
        
        return url, True, f"{filename_base}.docx", None
        
    except Exception as e:
        error_msg = str(e)
        display_msg = error_msg[:100] + "..." if len(error_msg) > 100 else error_msg
        print(f"{tag} [✗] 失败: {display_msg}")
        return url, False, None, error_msg


async def fetch_and_export_batch(
    urls: list[str],
    output_dir: Path,
    anti_detect_level: str = "medium",
    concurrency: int = 3,
) -> BatchReport:
    """批量导出多个 URL"""
    report = BatchReport()
    total = len(urls)
    
    print(f"[批次导出模式] 并发数: {concurrency}")
    print(f"总计 {total} 个 URL\n")
    
    semaphore = asyncio.Semaphore(concurrency)
    
    async def bounded_export(index: int, url: str):
        async with semaphore:
            return await fetch_and_export_single(
                url, output_dir, anti_detect_level, None, index, total
            )
    
    tasks = [bounded_export(i + 1, url) for i, url in enumerate(urls)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for result in results:
        if isinstance(result, Exception):
            report.add_failure(str(result), "未知错误")
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
    parser.add_argument("--concurrency", type=int, default=3, help="并发数（默认: 3）")
    
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
            result = asyncio.run(fetch_and_export_single(
                args.urls[0], output_dir, args.level, args.index, 1, 1
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
