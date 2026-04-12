"""网页爬取模块"""
from .anti_detect import AntiDetectMiddleware, create_anti_detect_middleware

try:
    from .crawler import DoubaoSpider, fetch_doubao_chat, ChatMessage, ChatData
    __all__ = ["DoubaoSpider", "ChatMessage", "ChatData", "fetch_doubao_chat", "AntiDetectMiddleware", "create_anti_detect_middleware"]
except ImportError:
    __all__ = ["AntiDetectMiddleware", "create_anti_detect_middleware"]