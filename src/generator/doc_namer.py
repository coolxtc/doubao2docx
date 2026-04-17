"""
文档名称生成器模块

为导出的 Word 文档生成唯一文件名，并维护索引记录。

核心功能：
1. 文件名生成：日期-序号 标题.docx
2. 索引维护：记录 URL -> 序号的映射，避免重复
3. 历史清理：自动删除过期的索引记录

索引文件（link_index.json）结构：
{
    "260412": {
        "https://...": {"index": 1, "title": "标题1"},
        "https://...": {"index": 2, "title": "标题2"}
    }
}
"""

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from ..config import get_config


class LinkRecord:
    """
    单条链接记录 - 存储一个已导出文档的信息

    属性说明：
    - index: 序号（同一天内的唯一标识，从1开始）
    - title: 文档标题（用于生成文件名）
    """
    index: int
    title: str

    def __init__(self, index: int, title: str = "") -> None:
        self.index = index
        self.title = title

    def to_dict(self) -> dict:
        """转换为字典格式（用于 JSON 序列化）"""
        return {"index": self.index, "title": self.title}

    @classmethod
    def from_dict(cls, data: dict) -> "LinkRecord":
        """从字典创建对象（用于 JSON 反序列化）"""
        return cls(index=data["index"], title=data.get("title", ""))


class DocNamer:
    """
    文档名称生成器 - 为文档生成唯一文件名并维护索引

    文件名格式：日期-序号 标题.docx
    示例：260412-1 固定翼飞机设计.docx

    设计要点：
    1. 线程安全：使用 threading.Lock 保证并发安全
    2. 历史追溯：同一 URL 始终使用相同序号
    3. 自动清理：删除超过 max_age_days 的历史记录
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
        self._max_age_days = config.index.max_age_days  # 过期天数，默认10天

        self._next_index = 0  # 内存中维护的下一个序号
        self._lock = threading.Lock()  # 线程锁，保证并发安全

        self._load()  # 加载索引文件

    def _load(self) -> None:
        """从文件加载索引数据"""
        if self.index_file.exists():
            with open(self.index_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
                # 将字典转换为 LinkRecord 对象
                self._data = {
                    date: {
                        url: LinkRecord.from_dict(record)
                        for url, record in records.items()
                    }
                    for date, records in raw.items()
                }

    def _save(self) -> None:
        """保存索引数据到文件"""
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

        格式：YYMMDD，例如 260412

        Args:
            dt: 日期时间，默认当前时间
        """
        if dt is None:
            dt = datetime.now()
        year = str(dt.year)[2:]  # 2026 -> 26
        month = f"{dt.month:02d}"  # 4 -> 04
        day = f"{dt.day:02d}"  # 12 -> 12
        return f"{year}{month}{day}"

    def get_date_str(self) -> str:
        """获取当前日期字符串 - 公共方法"""
        return self._get_date_str()

    def _get_today_records(self) -> dict[str, LinkRecord]:
        """获取今天的记录，不存在则创建空字典"""
        date_str = self._get_date_str()
        if date_str not in self._data:
            self._data[date_str] = {}
        return self._data[date_str]

    def _get_today_max_index(self) -> int:
        """获取今天最大的有效序号"""
        records = self._get_today_records()
        if not records:
            return 0
        valid_indices = [r.index for r in records.values() if r.index > 0]
        if not valid_indices:
            return 0
        return max(valid_indices)

    def _cleanup_old_entries(self) -> None:
        """清理过期的历史数据"""
        today = self._get_date_str()
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

        Windows 文件名不允许的字符：/ \\ : * ? " < > |
        这些字符会被移除。
        """
        invalid_chars = r'/\\:*?"<>|'
        for char in invalid_chars:
            title = title.replace(char, "")
        return title.strip()

    def get_filename(self, url: str, title: str) -> str:
        """
        获取文档文件名

        逻辑：
        1. 如果 URL 已有记录，返回相同序号（保持历史一致性）
        2. 否则分配新序号（递增）

        Args:
            url: 聊天页面的 URL
            title: 文档标题

        Returns:
            文件名，格式：日期-序号 标题
        """
        # 确保目录存在
        self.index_file.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:  # 线程安全
            date_str = self._get_date_str()
            records = self._get_today_records()
            clean_title = self._clean_title(title)

            # 检查 URL 是否已有记录
            if url in records and records[url].index > 0:
                # 已有记录，使用相同序号
                index = records[url].index
                records[url].title = clean_title  # 更新标题
            else:
                # 新 URL，分配新序号
                if self._next_index == 0:
                    self._next_index = self._get_today_max_index() + 1
                index = self._next_index
                self._next_index += 1
                records[url] = LinkRecord(index=index, title=clean_title)

            self._save()  # 保存索引

        return f"{date_str}-{index} {clean_title}"