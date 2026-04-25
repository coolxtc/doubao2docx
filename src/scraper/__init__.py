"""
网页爬取模块

负责 Playwright 浏览器自动化层，实现以下功能：
- 启动和管理浏览器实例
- 访问豆包聊天页面
- 执行页面交互（滚动加载、展开代码）
- 提取聊天数据

模块架构：
- BrowserManager: 浏览器生命周期管理
- DoubaoSpider: 爬虫核心，异步上下文管理器
- BrowserPool: 浏览器池（单浏览器多标签页模式）
- DataExtractor: 数据提取器
- PageActions: 页面交互操作
- AntiDetectMiddleware: 反爬检测中间件
"""

import warnings

from .anti_detect import AntiDetectMiddleware, create_anti_detect_middleware

try:
    from .browser import BrowserManager
    from .crawler import DoubaoSpider
    from .extractor import DataExtractor
    from .models import ChatData, ChatMessage, ImageData
    from .page_actions import PageActions
    from .pool import BrowserPool
    from .steps import FetchStep, STEP_INDEX, FETCH_STEP_NAMES, STEP_COUNT, reset_timer

    __all__ = [
        "DoubaoSpider",
        "ChatMessage",
        "ChatData",
        "ImageData",
        "FetchStep",
        "STEP_INDEX",
        "FETCH_STEP_NAMES",
        "STEP_COUNT",
        "reset_timer",
        "BrowserManager",
        "BrowserPool",
        "PageActions",
        "DataExtractor",
        "AntiDetectMiddleware",
        "create_anti_detect_middleware",
    ]
except ImportError as e:
    warnings.warn(f"部分爬虫模块导入失败（Playwright 未安装？）: {e}", ImportWarning)
    __all__ = ["AntiDetectMiddleware", "create_anti_detect_middleware"]
