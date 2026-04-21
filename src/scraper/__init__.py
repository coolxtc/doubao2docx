"""网页爬取模块"""

import warnings

from .anti_detect import AntiDetectMiddleware, create_anti_detect_middleware

try:
    from .browser import BrowserManager
    from .crawler import DoubaoSpider, fetch_doubao_chat
    from .extractor import DataExtractor
    from .models import ChatData, ChatMessage, ImageData
    from .page_actions import PageActions
    from .steps import FetchStep, STEP_INDEX, FETCH_STEP_NAMES, STEP_COUNT, reset_timer  # noqa: F401

    __all__ = [
        "DoubaoSpider",
        "fetch_doubao_chat",
        "ChatMessage",
        "ChatData",
        "ImageData",
        "FetchStep",
        "STEP_INDEX",
        "FETCH_STEP_NAMES",
        "STEP_COUNT",
        "reset_timer",
        "BrowserManager",
        "PageActions",
        "DataExtractor",
        "AntiDetectMiddleware",
        "create_anti_detect_middleware",
    ]
except ImportError as e:
    warnings.warn(f"部分爬虫模块导入失败（Playwright 未安装？）: {e}", ImportWarning)
    __all__ = ["AntiDetectMiddleware", "create_anti_detect_middleware"]
