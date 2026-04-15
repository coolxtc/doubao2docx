"""文档名称生成器 - 为导出的 Word 文档生成唯一文件名"""

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from ..config import get_config


class LinkRecord:
    """单条链接记录 - 存储一个已导出文档的信息
    
    属性：
        index: 序号（同一天内的唯一标识）
        title: 文档标题
    """
    index: int
    title: str
    
    def __init__(self, index: int, title: str = "") -> None:
        self.index = index
        self.title = title
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {"index": self.index, "title": self.title}
    
    @classmethod
    def from_dict(cls, data: dict) -> "LinkRecord":
        """从字典创建对象"""
        return cls(index=data["index"], title=data.get("title", ""))


class DocNamer:
    """文档名称生成器 - 为文档生成唯一文件名并维护索引
    
    文件名格式：日期-序号 标题.docx
    示例：260412-1 固定翼飞机设计.docx
    """
    
    def __init__(self, index_file: Path) -> None:
        """初始化
        
        Args:
            index_file: 索引文件路径（link_index.json）
        """
        self.index_file = index_file
        self._data: dict[str, dict[str, LinkRecord]] = {}
        
        config = get_config()
        self._max_age_days = config.index.max_age_days
        
        self._next_index = 0
        self._lock = threading.Lock()
        
        self._load()
    
    def _load(self) -> None:
        """加载索引文件"""
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
    
    def _save(self) -> None:
        """保存索引文件"""
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
        """获取日期字符串
        
        格式：YYMMDD，例如 260412
        
        Args:
            dt: 日期时间，默认当前时间
        """
        if dt is None:
            dt = datetime.now()
        year = str(dt.year)[2:]
        month = f"{dt.month:02d}"
        day = f"{dt.day:02d}"
        return f"{year}{month}{day}"
    
    def get_date_str(self) -> str:
        """获取当前日期字符串 - 公共方法
        
        Returns:
            当前日期，格式：YYMMDD
        """
        return self._get_date_str()
    
    def get_next_base_index(self) -> int:
        """获取下一个可用序号（从1开始）
        
        用于预分配序号，确保批量导出时按顺序分配。
        
        Returns:
            下一个可用的序号
        """
        return self._get_today_max_index() + 1
    
    def _get_today_records(self) -> dict[str, LinkRecord]:
        """获取今天的记录，不存在则创建"""
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
        return max(r.index for r in records.values())
    
    def _cleanup_old_entries(self) -> None:
        """清理过期数据"""
        today = self._get_date_str()
        cutoff = self._get_date_str(datetime.now() - timedelta(days=self._max_age_days))
        
        dates_to_remove = [
            d for d in self._data.keys() 
            if d < cutoff
        ]
        for date in dates_to_remove:
            del self._data[date]
    
    def _clean_title(self, title: str) -> str:
        """清理标题中的非法字符
        
        Windows 文件名不允许的字符：/ \\ : * ? " < > |
        """
        invalid_chars = r'/\\:*?"<>|'
        for char in invalid_chars:
            title = title.replace(char, "")
        return title.strip()
    
    def set_next_index(self, index: int) -> None:
        with self._lock:
            self._next_index = index
    
    def get_filename(self, url: str, title: str) -> str:
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        
        with self._lock:
            date_str = self._get_date_str()
            records = self._get_today_records()
            clean_title = self._clean_title(title)
            
            if url in records and records[url].index > 0:
                index = records[url].index
                records[url].title = clean_title
            else:
                if self._next_index == 0:
                    self._next_index = self._get_today_max_index() + 1
                index = self._next_index
                self._next_index += 1
                records[url] = LinkRecord(index=index, title=clean_title)
            
            self._save()
        
        return f"{date_str}-{index} {clean_title}"
    
    def get_filename_by_order(self, order: int, url: str, title: str) -> str:
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        
        with self._lock:
            date_str = self._get_date_str()
            records = self._get_today_records()
            clean_title = self._clean_title(title)
            
            if url in records and records[url].index > 0:
                index = records[url].index
                records[url].title = clean_title
            else:
                index = order
                records[url] = LinkRecord(index=index, title=clean_title)
            
            self._save()
        
        return f"{date_str}-{index} {clean_title}"