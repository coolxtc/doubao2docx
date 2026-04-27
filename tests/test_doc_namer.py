import json
import tempfile
from datetime import datetime
from pathlib import Path
from src.generator.doc_namer import DocNamer, LinkRecord


class TestLinkRecord:
    """测试 LinkRecord 数据类"""

    def test_init(self):
        """初始化应成功"""
        record = LinkRecord(index=1, title="测试标题")
        assert record.index == 1
        assert record.title == "测试标题"

    def test_init_default_title(self):
        """默认标题为空"""
        record = LinkRecord(index=1)
        assert record.title == ""

    def test_to_dict(self):
        """转换为字典"""
        record = LinkRecord(index=1, title="测试标题")
        d = record.to_dict()
        assert d == {"index": 1, "title": "测试标题"}

    def test_from_dict(self):
        """从字典创建"""
        d = {"index": 1, "title": "测试标题"}
        record = LinkRecord.from_dict(d)
        assert record.index == 1
        assert record.title == "测试标题"

    def test_from_dict_missing_title(self):
        """缺少标题字段时应使用默认值"""
        d = {"index": 1}
        record = LinkRecord.from_dict(d)
        assert record.index == 1
        assert record.title == ""


class TestDocNamer:
    """测试 DocNamer 文档命名器"""

    def test_init_with_temp_file(self):
        """使用临时文件初始化"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_file = Path(tmpdir) / "link_index.json"
            namer = DocNamer(index_file)
            assert namer is not None
            assert namer.index_file == index_file

    def test_init_loads_existing_data(self):
        """初始化时加载已有数据"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_file = Path(tmpdir) / "link_index.json"
            data = {"260412": {"http://example.com": {"index": 1, "title": "Test"}}}
            with open(index_file, "w", encoding="utf-8") as f:
                json.dump(data, f)

            namer = DocNamer(index_file)
            assert "260412" in namer._data

    def test_get_date_str(self):
        """获取日期字符串"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_file = Path(tmpdir) / "link_index.json"
            namer = DocNamer(index_file)
            date_str = namer.get_date_str()
            assert len(date_str) == 6
            assert date_str.isdigit()

    def test_get_date_str_with_datetime(self):
        """使用指定日期"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_file = Path(tmpdir) / "link_index.json"
            namer = DocNamer(index_file)
            dt = datetime(2026, 4, 12)
            date_str = namer._get_date_str(dt)
            assert date_str == "260412"

    def test_get_filename_new_url(self):
        """新 URL 生成文件名"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_file = Path(tmpdir) / "link_index.json"
            namer = DocNamer(index_file)
            filename = namer.get_filename("http://example.com/1", "Test Title")
            assert "1" in filename
            assert "Test Title" in filename

    def test_get_filename_existing_url(self):
        """已有 URL 复用原有序号"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_file = Path(tmpdir) / "link_index.json"
            namer = DocNamer(index_file)
            namer.get_filename("http://example.com/1", "Title A")
            filename = namer.get_filename("http://example.com/1", "Title B")
            assert "Title A" in filename or "Title B" in filename

    def test_clean_title_removes_invalid_chars(self):
        """清理非法字符"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_file = Path(tmpdir) / "link_index.json"
            namer = DocNamer(index_file)
            cleaned = namer._clean_title("Test / : * ? \" < > | Title")
            assert "/" not in cleaned
            assert ":" not in cleaned
            assert "*" not in cleaned

    def test_save_and_load(self):
        """保存和加载数据"""
        with tempfile.TemporaryDirectory() as tmpdir:
            index_file = Path(tmpdir) / "link_index.json"
            namer = DocNamer(index_file)
            namer.get_filename("http://example.com/1", "Title 1")
            namer.save()

            assert index_file.exists()

            namer2 = DocNamer(index_file)
            assert len(namer2._data) > 0