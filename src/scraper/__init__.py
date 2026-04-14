"""网页爬取模块"""
from .anti_detect import AntiDetectMiddleware, create_anti_detect_middleware

try:
    from .crawler import DoubaoSpider, fetch_doubao_chat, ChatMessage, ChatData, FetchStep, _format_progress, STEP_INDEX
    __all__ = ["DoubaoSpider", "ChatMessage", "ChatData", "fetch_doubao_chat", "FetchStep", "_format_progress", "STEP_INDEX", "AntiDetectMiddleware", "create_anti_detect_middleware"]
except ImportError:
    __all__ = ["AntiDetectMiddleware", "create_anti_detect_middleware"]