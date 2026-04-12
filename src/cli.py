"""
命令行入口模块

这个模块是整个程序的入口点，负责：
1. 解析命令行参数（用户输入的选项）
2. 协调各个模块完成爬取、解析、导出流程
3. 处理错误并返回相应的退出码
"""

import argparse
import asyncio
import sys
from pathlib import Path

from src.scraper import DoubaoSpider
from src.preprocessor.doubao_parser import DoubaoHTMLParser, TextBlock
from src.generator import DocxBuilder, DocumentConfig, DocNamer


async def fetch_and_export(
    url: str, 
    output_dir: Path, 
    anti_detect_level: str = "medium",
    custom_index: int | None = None
) -> int:
    """爬取豆包聊天记录并导出为 Word 文档
    
    这是一个异步函数，是程序的核心处理流程。
    整个过程可以理解为"流水线"：爬取 -> 解析 -> 命名 -> 生成文档
    
    处理流程：
    1. 爬取阶段：使用 Playwright（自动化浏览器）访问豆包页面
    2. 解析阶段：从 HTML 中提取聊天内容，支持特殊格式（公式/代码/表格）
    3. 命名阶段：根据日期和标题生成唯一的文件名
    4. 生成阶段：用 python-docx 库创建 Word 文档并保存
    
    参数说明：
        url: 豆包聊天页面的完整 URL，类似 https://www.doubao.com/thread/abc123
        output_dir: 文档输出的文件夹路径
        anti_detect_level: 反爬虫检测级别，"low"/"medium"/"high"
        custom_index: 可选的手动序号，用于控制文档的排序
    
    返回值：
        - 返回 0 表示成功完成
        - 返回 1 表示发生错误
    """
    print(f"正在爬取: {url}")

    try:
        # async with 是异步上下文管理器，类似于普通代码的 "with"
        # 进入 with 块时初始化浏览器，退出时自动关闭浏览器、清理资源
        async with DoubaoSpider(anti_detect_level=anti_detect_level) as spider:
            # await 的作用：等待爬虫完成抓取后再继续执行
            chat_data = await spider.fetch(url)

        print(f"爬取完成，获取 {len(chat_data.messages)} 条消息")

        print("正在处理内容...")
        
        # 创建 HTML 解析器实例
        parser = DoubaoHTMLParser()
        
        # all_blocks 存储所有解析后的文本块
        # 每个元素是 (角色, 文本块) 的元组
        # 角色可以是 "user"（用户）或 "assistant"（AI）
        all_blocks: list[tuple[str, TextBlock]] = []
        
        # 遍历所有消息，逐条解析
        for msg in chat_data.messages:
            parsed = parser.parse(msg.content)
            for block in parsed.blocks:
                all_blocks.append((msg.role, block))

        # link_index.json 记录已导出的文档索引
        # DocNamer 负责根据 URL 和标题生成唯一且不重复的文件名
        index_file = output_dir / "link_index.json"
        namer = DocNamer(index_file)
        filename_base = namer.get_filename(url, chat_data.title, custom_index)
        
        # 完整的输出路径：output_dir/export/文件名.docx
        output_path = output_dir / "export" / f"{filename_base}.docx"
        
        # 确保目录存在，如果不存在就创建
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print("正在生成Word文档...")
        
        # 创建文档配置和构建器
        config = DocumentConfig(title=chat_data.title)
        builder = DocxBuilder(config)
        
        # build_blocks 遍历所有文本块，根据内容类型应用不同格式
        builder.build_blocks(chat_data.title, all_blocks, str(output_path))

        print(f"导出完成: {output_path}")
        return 0

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"错误: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """主入口函数
    
    负责：
    1. 定义命令行参数（--level, --index 等）
    2. 解析用户输入
    3. 调用异步函数执行实际工作
    """
    
    # argparse 是 Python 标准库，用于处理命令行界面
    parser = argparse.ArgumentParser(
        description="导出豆包聊天记录为Word文档",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m src.cli https://www.doubao.com/thread/ad8e9da8e8159
  python -m src.cli https://www.doubao.com/thread/test --level high
  python -m src.cli https://www.doubao.com/thread/test --index 5
        """,
    )

    # 添加位置参数（必须提供的参数）
    parser.add_argument(
        "url",
        nargs="?",
        help="豆包聊天页面URL",
    )

    # 添加可选参数（以 -- 开头）
    parser.add_argument(
        "--level",
        choices=["low", "medium", "high"],
        default="medium",
        help="反爬级别 (默认: medium)",
    )

    parser.add_argument(
        "--index",
        type=int,
        default=None,
        help="手动指定文档序号",
    )

    args = parser.parse_args()

    # 检查用户是否提供了 URL 参数
    if not args.url:
        parser.print_help()
        return 1

    # 输出目录设置：项目根目录下的 data 文件夹
    output_dir = Path(__file__).parent.parent / "data"

    # asyncio.run() 是启动异步函数的唯一方式
    # 它会创建一个事件循环并运行传入的协程
    return asyncio.run(fetch_and_export(
        args.url,
        output_dir,
        args.level,
        args.index
    ))


# if __name__ == "__main__" 是 Python 惯用法
# 确保代码只在直接运行此文件时执行，作为模块导入时不会执行
if __name__ == "__main__":
    sys.exit(main())