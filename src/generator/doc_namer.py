"""
文档名称生成器

这个模块负责为导出的 Word 文档生成唯一的文件名。
同时维护一个索引文件（link_index.json）记录已导出的文档。

主要功能：
- 生成唯一文件名：日期-序号 标题.docx
- 维护链接索引，记录已导出的文档
- 自动清理过期数据（10天前的记录）

核心概念：
- 日期格式：260412（YYMMDD）
- 序号：同一天内递增
- 索引文件：JSON格式，存储链接和对应的序号/标题
"""

import json
import fcntl
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


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
    
    工作原理：
    1. 读取索引文件，获取当天已有记录
    2. 如果 URL 已存在，使用已有的序号
    3. 如果是新 URL，使用当天最大序号 +1
    4. 保存更新后的索引
    5. 返回生成的文件名
    
    自动清理：
    - 超过 10 天的记录会被自动删除
    """
    
    # 过期数据保留天数
    MAX_AGE_DAYS = 10
    
    def __init__(self, index_file: Path) -> None:
        """初始化
        
        Args:
            index_file: 索引文件路径（link_index.json）
        """
        self.index_file = index_file
        self._data: dict[str, dict[str, LinkRecord]] = {}
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
        """获取今天最大的序号"""
        records = self._get_today_records()
        if not records:
            return 0
        return max(r.index for r in records.values())
    
    def _cleanup_old_entries(self) -> None:
        """清理过期数据 - 删除超过10天的记录"""
        today = self._get_date_str()
        cutoff = self._get_date_str(datetime.now() - timedelta(days=self.MAX_AGE_DAYS))
        
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
    
    def get_filename(
        self, 
        url: str, 
        title: str, 
        custom_index: Optional[int] = None
    ) -> str:
        """生成文件名 - 主方法
        
        规则：
        1. 如果指定了 custom_index，使用该序号
        2. 如果 URL 之前已导出，使用已有序号
        3. 否则，使用当天最大序号 +1
        
        Args:
            url: 链接地址
            title: 文档标题
            custom_index: 手动指定的序号，None 则自动分配
            
        Returns:
            文件名（不含扩展名），格式：日期-序号 标题
        """
        lock_file = self.index_file.with_suffix(".lock")
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_file, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                date_str = self._get_date_str()
                records = self._get_today_records()
                clean_title = self._clean_title(title)
                
                if custom_index is not None:
                    index = custom_index
                    records[url] = LinkRecord(index=index, title=clean_title)
                elif url in records:
                    index = records[url].index
                    records[url].title = clean_title
                else:
                    index = self._get_today_max_index() + 1
                    records[url] = LinkRecord(index=index, title=clean_title)
                
                self._save()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        
        return f"{date_str}-{index} {clean_title}"