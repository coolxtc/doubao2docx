"""
测试爬虫数据模型
"""
from src.scraper.models import ImageData, ChatMessage, ChatData


class TestImageData:
    """测试图片数据模型"""

    def test_init(self):
        """初始化"""
        img = ImageData(url="http://example.com/img.jpg", prev_text="prev", next_text="next")
        assert img.url == "http://example.com/img.jpg"
        assert img.prev_text == "prev"
        assert img.next_text == "next"


class TestChatMessage:
    """测试消息数据模型"""

    def test_init(self):
        """初始化基本消息"""
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.timestamp is None

    def test_init_with_timestamp(self):
        """带时间戳"""
        msg = ChatMessage(role="assistant", content="Hi there", timestamp="2026-04-25")
        assert msg.timestamp == "2026-04-25"

    def test_init_with_images(self):
        """带图片列表"""
        img = ImageData(url="http://example.com/1.jpg", prev_text="", next_text="")
        msg = ChatMessage(role="assistant", content=" Image", images=[img])
        assert len(msg.images) == 1

    def test_to_dict(self):
        """转换为字典"""
        msg = ChatMessage(role="user", content="Test")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "Test"


class TestChatData:
    """测试聊天记录数据模型"""

    def test_init(self):
        """初始化"""
        chat = ChatData(url="http://example.com/chat")
        assert chat.url == "http://example.com/chat"
        assert chat.title == ""
        assert len(chat.messages) == 0

    def test_init_with_title(self):
        """带标题"""
        chat = ChatData(url="http://example.com/chat", title="My Chat")
        assert chat.title == "My Chat"

    def test_init_with_messages(self):
        """带消息列表"""
        msg = ChatMessage(role="user", content="Hello")
        chat = ChatData(url="http://example.com/chat", messages=[msg])
        assert len(chat.messages) == 1

    def test_to_dict(self):
        """转换为字典"""
        chat = ChatData(url="http://example.com/chat", title="Test")
        d = chat.to_dict()
        assert d["url"] == "http://example.com/chat"
        assert d["title"] == "Test"