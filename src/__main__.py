"""
Doubao Export 入口点

支持通过 python3 -m src 直接运行程序。
用于将豆包聊天记录导出为 Word 文档。
"""

# 导入主入口函数，供模块化调用使用
from src.cli import main

# 程序入口点：直接运行脚本时自动调用 main() 函数
if __name__ == "__main__":
    raise SystemExit(main())
