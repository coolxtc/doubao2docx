"""数据模型定义"""

from dataclasses import dataclass, field
from typing import Optional


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
    timestamp: Optional[str] = None
    images: list[ImageData] = field(default_factory=list)

    def to_dict(self) -> dict:
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

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "messages": [msg.to_dict() for msg in self.messages],
        }
