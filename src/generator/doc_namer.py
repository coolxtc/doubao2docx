"""
文档名称生成器模块

为导出的 Word 文档生成唯一文件名，并维护索引记录。

为什么需要这个模块？
1. 文件名唯一性：同一天导出的多个文档需要不同的序号
2. 历史追溯：同一 URL 再次导出时，应使用相同序号（便于查找）
3. 自动清理：避免索引文件无限膨胀

文件名格式：日期-序号 标题.docx
示例：260412-1 固定翼飞机设计.docx

索引文件（link_index.json）结构：
{
    "260412": {
        "https://...": {"index": 1, "title": "标题1"},
        "https://...": {"index": 2, "title": "标题2"}
    }
}

索引小科普：
- 使用日期作为第一层 key，便于按天查找
- URL 作为第二层 key，确保同一 URL 映射到同一序号
- 超过 max_age_days 的记录会被清理
"""

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from ..config import get_config


class LinkRecord:
    """
    单条链接记录 - 存储一个已导出文档的信息

    为什么使用 dataclass？
    - 简单的数据结构，使用 dataclass 可以减少样板代码
    - 自动实现 __init__、__repr__、to_dict 等方法
    """
    index: int
    title: str

    def __init__(self, index: int, title: str = "") -> None:
        """
        创建链接记录

        Args:
            index: 序号，同一天内的唯一标识（从1开始递增）
            title: 文档标题，用于生成文件名
        """
        self.index = index
        self.title = title

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式（用于 JSON 序列化）"""
        return {"index": self.index, "title": self.title}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LinkRecord":
        """从字典创建对象（用于 JSON 反序列化）"""
        return cls(index=data["index"], title=data.get("title", ""))


class DocNamer:
    """
    文档名称生成器 - 为文档生成唯一文件名并维护索引

    文件名格式：日期-序号 标题.docx
    示例：260412-1 固定翼飞机设计.docx

    为什么需要这个类？
    1. 文件名唯一性：同一天导出的多个文档需要不同的序号
    2. 历史追溯：同一 URL 再次导出时，应使用相同序号（便于查找）
    3. 自动清理：避免索引文件无限膨胀

    设计要点：
    1. 线程安全：使用 threading.Lock 保证并发安全
    2. 历史追溯：同一 URL 始终使用相同序号
    3. 自动清理：删除超过 max_age_days 的历史记录
    """

    def __init__(self, index_file: Path) -> None:
        """
        初始化文档命名器

        初始化时会：
        1. 设置索引文件路径
        2. 加载已有索引数据
        3. 清理过期记录
        4. 初始化线程锁

        Args:
            index_file: 索引文件路径（link_index.json）
        """
        self.index_file = index_file
        # 数据结构: {日期字符串: {URL: LinkRecord}}
        self._data: dict[str, dict[str, LinkRecord]] = {}

        config = get_config()
        self._max_age_days: int = config.index.max_age_days if config.index else 10  # 过期天数，默认10天

        self._next_index = 0  # 内存中维护的下一个序号
        self._lock = threading.Lock()  # 线程锁，保证并发安全

        self._load()

    def _load(self) -> None:
        """从索引文件加载数据"""
        if self.index_file.exists():
            with open(self.index_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
                self._data = {
                    date: {
                        url: LinkRecord.from_dict(record)
                        for url, record in records.items()
                    }
                    for date, records in raw.items()
                }

    def save(self) -> None:
        """
        保存索引数据到文件

        将 LinkRecord 对象转换为字典，然后写入 JSON 文件。
        """
        raw = {
            date: {
                url: record.to_dict()
                for url, record in records.items()
            }
            for date, records in self._data.items()
        }
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)

    def _get_date_str(self, dt: Optional[datetime] = None) -> str:
        """
        获取日期字符串

        格式：YYMMDD，例如 260412 表示 2026 年 4 月 12 日

        为什么使用 YYMMDD？
        简短且可排序，适合作为文件名和索引的日期标识。
        """
        if dt is None:
            dt = datetime.now()
        year = str(dt.year)[2:]  # 2026 -> 26
        month = f"{dt.month:02d}"  # 4 -> 04
        day = f"{dt.day:02d}"  # 12 -> 12
        return f"{year}{month}{day}"

    def get_date_str(self) -> str:
        """
        获取当前日期字符串

        对外暴露的公共方法。
        """
        return self._get_date_str()

    def get_today_records(self) -> dict[str, LinkRecord]:
        """
        获取今天的记录

        如果今天的记录不存在，则创建空字典。
        """
        date_str = self._get_date_str()
        if date_str not in self._data:
            self._data[date_str] = {}
        return self._data[date_str]

    def get_today_max_index(self) -> int:
        """
        获取今天最大的有效序号

        用于确定下一个新文档应该使用什么序号。
        """
        records = self.get_today_records()
        if not records:
            return 0
        valid_indices = [r.index for r in records.values() if r.index > 0]
        if not valid_indices:
            return 0
        return max(valid_indices)

    def cleanup_old_entries(self) -> None:
        """
        清理过期的历史数据

        删除超过 max_age_days 天的记录，避免索引文件无限膨胀。
        """
        cutoff = self._get_date_str(datetime.now() - timedelta(days=self._max_age_days))

        # 删除 cutoff 日期之前的所有记录
        dates_to_remove = [
            d for d in self._data.keys()
            if d < cutoff
        ]
        for date in dates_to_remove:
            del self._data[date]

    def _clean_title(self, title: str) -> str:
        """
        清理标题中的非法字符

        为什么需要清理？
        Windows 文件名不允许某些字符，这些字符会被移除。
        同时去除首尾空白字符。

        Windows 文件名非法字符小科普：
        / \\ : * ? " < > |
        这些字符在 Windows 上有特殊含义，不能用于文件名。
        """
        invalid_chars = r'/\\:*?"<>|'
        for char in invalid_chars:
            title = title.replace(char, "")
        return title.strip()

    def get_filename(self, url: str, title: str, update_title: bool = True) -> str:
        """获取文档文件名，预分配模式传入 update_title=False"""
        self.index_file.parent.mkdir(parents=True, exist_ok=True)

        date_str = self._get_date_str()
        records = self.get_today_records()
        clean_title = self._clean_title(title)

        if url in records and records[url].index > 0:
            index = records[url].index
            if update_title:
                records[url].title = clean_title
        else:
            with self._lock:
                if self._next_index == 0:
                    self._next_index = self.get_today_max_index() + 1
                index = self._next_index
                self._next_index += 1
                records[url] = LinkRecord(index=index, title=clean_title)

        return f"{date_str}-{index} {clean_title}"

    def update_title(self, url: str, title: str) -> None:
        records = self.get_today_records()
        with self._lock:
            if url in records:
                records[url].title = self._clean_title(title)
