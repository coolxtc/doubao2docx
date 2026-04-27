"""文档名称生成器模块"""

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from ..config import get_config


class LinkRecord:
    """单条链接记录"""
    index: int  # 序号（从1开始递增）
    title: str  # 文档标题

    def __init__(self, index: int, title: str = "") -> None:
        """
        创建链接记录

        Args:
            index: 序号（从1开始递增）
            title: 文档标题
        """
        self.index = index
        self.title = title

    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典

        Returns:
            dict[str, Any]: 字典表示
        """
        return {"index": self.index, "title": self.title}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LinkRecord":
        """
        从字典创建对象

        Args:
            data: 字典数据

        Returns:
            LinkRecord: 实例对象
        """
        return cls(index=data["index"], title=data.get("title", ""))


class DocNamer:
    """
    文档名称生成器

    为文档生成唯一文件名并维护索引。文件名格式：日期-序号 标题.docx
    """

    def __init__(self, index_file: Path) -> None:
        """
        初始化文档命名器

        Args:
            index_file: 索引文件路径（link_index.json）
        """
        self.index_file = index_file
        # 数据结构: {日期字符串: {URL: LinkRecord}}
        self._data: dict[str, dict[str, LinkRecord]] = {}

        config = get_config()
        self._max_age_days: int = config.index.max_age_days if config.index else 10  # 过期天数

        self._next_index = 0  # 内存中维护的下一个序号
        self._lock = threading.Lock()  # 线程锁，保证并发安全

        self._load()

    def _load(self) -> dict[str, dict[str, LinkRecord]]:
        """
        从 JSON 加载索引数据

        Returns:
            按日期分组的链接记录字典
        """
        result: dict[str, dict[str, LinkRecord]] = {}
        if self.index_file.exists():
            with open(self.index_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # 从 JSON 加载数据：按日期分组，按 URL 建索引
            result = {
                date: {
                    url: LinkRecord.from_dict(record)
                    for url, record in records.items()
                }
            for date, records in raw.items()
            }
        self._data = result
        return result

    def save(self) -> None:
        """
        保存索引数据到 JSON 文件
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

        Args:
            dt: datetime 对象，为 None 时使用当前时间

        Returns:
            str: YYMMDD 格式日期字符串
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

        Returns:
            str: YYMMDD 格式日期字符串
        """
        return self._get_date_str()

    def get_today_records(self) -> dict[str, LinkRecord]:
        """
        获取今天的记录

        Returns:
            dict[str, LinkRecord]: 今天记录的字典
        """
        date_str = self._get_date_str()
        if date_str not in self._data:
            self._data[date_str] = {}
        return self._data[date_str]

    def get_today_max_index(self) -> int:
        """
        获取今天最大的有效序号

        Returns:
            int: 最大序号，无记录返回 0
        """
        records = self.get_today_records()
        if not records:
            return 0
        valid_indices = [r.index for r in records.values() if r.index > 0]
        if not valid_indices:
            return 0
        return max(valid_indices)

    def cleanup_old_entries(self) -> int:
        """
        清理过期记录

        Returns:
            删除的记录数量
        """
        cutoff = self._get_date_str(datetime.now() - timedelta(days=self._max_age_days))

        dates_to_remove = [
            d for d in self._data.keys()
            if d < cutoff
        ]
        removed_count = len(dates_to_remove)
        for date in dates_to_remove:
            del self._data[date]
        return removed_count

    def _clean_title(self, title: str) -> str:
        """
        清理标题中的非法字符

        Args:
            title: 原始标题

        Returns:
            str: 清理后的标题
        """
        invalid_chars = r'/\\:*?"<>|'
        for char in invalid_chars:
            title = title.replace(char, "")
        return title.strip()

    def get_filename(self, url: str, title: str, update_title: bool = True) -> str:
        """
        获取文档文件名

        Args:
            url: 文档 URL
            title: 文档标题
            update_title: 是否更新已有记录中的标题

        Returns:
            str: 文件名（不含扩展名）
        """
        self.index_file.parent.mkdir(parents=True, exist_ok=True)

        date_str = self._get_date_str()
        records = self.get_today_records()
        clean_title = self._clean_title(title)

        # 已有记录：复用序号
        if url in records and records[url].index > 0:
            index = records[url].index
            if update_title:
                records[url].title = clean_title
        else:
            # 新记录：分配新序号
            with self._lock:
                if self._next_index == 0:
                    self._next_index = self.get_today_max_index() + 1
                index = self._next_index
                self._next_index += 1
                records[url] = LinkRecord(index=index, title=clean_title)

        return f"{date_str}-{index} {clean_title}"

    def update_title(self, url: str, title: str) -> None:
        """
        更新已有记录的标题

        Args:
            url: 文档 URL
            title: 新标题
        """
        records = self.get_today_records()
        with self._lock:
            if url in records:
                records[url].title = self._clean_title(title)
