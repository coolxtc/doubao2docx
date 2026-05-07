"""爬虫数据模型"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImageData:
    """单张图片数据"""
    url: str  # 图片 URL
    prev_text: str  # 图片前相邻的标题文本
    next_text: str  # 图片后相邻的标题文本


@dataclass
class ChatMessage:
    """单条聊天消息"""
    role: str  # 消息角色（user/assistant）
    content: str  # 消息 HTML 内容
    timestamp: str | None = None  # 时间戳
    images: list[ImageData] = field(default_factory=list)  # 图片列表

    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典格式

        Returns:
            dict[str, Any]: 消息字典
        """
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
    """完整聊天记录"""
    url: str  # 聊天页面 URL
    title: str = ""  # 聊天标题
    messages: list[ChatMessage] = field(default_factory=list)  # 消息列表
    raw_html: str = ""  # 原始 HTML

    def to_dict(self, include_raw_html: bool = False) -> dict[str, Any]:
        """
        转换为字典格式

        Args:
            include_raw_html: 是否包含原始 HTML

        Returns:
            dict[str, Any]: 聊天记录字典
        """
        result: dict[str, Any] = {
            "url": self.url,
            "title": self.title,
            "messages": [msg.to_dict() for msg in self.messages],
        }
        if include_raw_html:
            result["raw_html"] = self.raw_html
        return result
