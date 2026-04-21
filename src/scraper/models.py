"""
数据模型定义

本模块定义了爬虫和解析模块使用的数据结构。
使用 dataclass 装饰器简化类的定义，自动生成 __init__、__repr__ 等方法。

为什么需要这个模块？
在爬取和解析过程中，需要统一的数据结构来表示聊天内容。
使用 dataclass 可以：
- 代码更简洁，省去手动定义 __init__
- 自动生成 __repr__，便于调试
- 支持类型提示，提高代码可靠性

主要数据结构：
- ImageData: 单张图片的信息（URL 和上下文文本）
- ChatMessage: 单条聊天消息（角色、内容、时间戳、图片）
- ChatData: 完整的聊天记录（包含标题和多条消息）
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImageData:
    """单张图片的数据模型"""
    url: str
    prev_text: str
    next_text: str


@dataclass
class ChatMessage:
    """单条聊天消息的数据模型"""
    role: str
    content: str
    timestamp: str | None = None
    images: list[ImageData] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """将消息转换为字典格式"""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "images": [
                {"url": img.url, "prev_text": img.prev_text, "next_text": img.next_text}
                for img in self.images
            ],
        }


@dataclass
class ChatData:
    """聊天记录数据模型"""
    url: str
    title: str = ""
    messages: list[ChatMessage] = field(default_factory=list)
    raw_html: str = ""

    def to_dict(self) -> dict[str, Any]:
        """将聊天记录转换为字典格式"""
        return {
            "url": self.url,
            "title": self.title,
            "messages": [msg.to_dict() for msg in self.messages],
        }