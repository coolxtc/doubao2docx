"""网页爬取模块"""

from .anti_detect import AntiDetectMiddleware, create_anti_detect_middleware

try:
    from .browser import BrowserManager
    from .crawler import DoubaoSpider, fetch_doubao_chat
    from .extractor import DataExtractor
    from .models import ChatData, ChatMessage, ImageData
    from .page_actions import PageActions
    from .steps import FetchStep, STEP_INDEX, FETCH_STEP_NAMES, reset_timer

    __all__ = [
        "DoubaoSpider",
        "fetch_doubao_chat",
        "ChatMessage",
        "ChatData",
        "ImageData",
        "FetchStep",
        "STEP_INDEX",
        "FETCH_STEP_NAMES",
        "reset_timer",
        "BrowserManager",
        "PageActions",
        "DataExtractor",
        "AntiDetectMiddleware",
        "create_anti_detect_middleware",
    ]
except ImportError:
    __all__ = ["AntiDetectMiddleware", "create_anti_detect_middleware"]
