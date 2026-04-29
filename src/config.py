"""配置加载模块，YAML → dataclass 配置对象"""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Any, TypedDict, cast

try:
    import yaml
except ImportError:
    yaml = None

# YAML 库可用性标志
YAML_AVAILABLE: bool = yaml is not None


class CrawlerData(TypedDict):
    """爬虫配置数据类型"""
    page_load_timeout: int
    timeout: int
    scroll_wait_ms: int
    browser_close_delay: float
    user_agents: list[str]


class DocumentStyleData(TypedDict):
    """文档样式配置数据类型"""
    title_font_size: int
    code_font_size: int
    image_width: float
    inline_image_width: float
    footer_mark: str


class IndexData(TypedDict):
    """索引配置数据类型"""
    max_age_days: int


class PandocData(TypedDict):
    """Pandoc 配置数据类型"""
    timeout: int


class ParserData(TypedDict):
    """解析器配置数据类型"""
    latex_attr: str


class GlobalData(TypedDict):
    """全局配置数据类型"""
    url_fallback_length: int
    concurrency: int


class ConfigData(TypedDict):
    """完整配置数据类型"""
    crawler: CrawlerData
    document_style: DocumentStyleData
    index: IndexData
    pandoc: PandocData
    parser: ParserData
    global_: GlobalData


# 配置字典类型别名
_ConfigDict = dict[str, Any]  # 运行时配置字典类型


def _get_config_path() -> Path:
    """获取配置文件路径"""
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        base_path = Path(meipass)
    else:
        base_path = Path(__file__).parent.parent
    config_path = base_path / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    return config_path


def _load_yaml() -> ConfigData:
    """从 config.yaml 加载配置"""
    if yaml is None:
        raise RuntimeError("需要 pyyaml 库来读取配置，请运行: pip install pyyaml")
    config_path = _get_config_path()
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        if data is None:
            raise ValueError(f"配置文件为空: {config_path}")
    _validate_config(data)
    return cast(ConfigData, data)


def _validate_config(data: _ConfigDict) -> None:
    """验证配置包含所有必需节"""
    required_sections = ["crawler", "document_style", "index", "pandoc", "parser", "global"]
    missing = [s for s in required_sections if s not in data]
    if missing:
        raise KeyError(f"配置缺少必需节: {', '.join(missing)}")


def _require_keys(data: _ConfigDict, keys: list[str], section: str) -> None:
    """检查必需的字段，缺失则报错"""
    missing = [k for k in keys if k not in data]
    if missing:
        raise KeyError(f"配置缺少必需字段 [{section}]: {', '.join(missing)}")


@dataclass
class CrawlerConfig:
    """爬虫配置"""
    page_load_timeout: int  # 页面加载超时（毫秒）
    timeout: int  # 请求超时（毫秒）
    scroll_wait_ms: int  # 滚动等待时间（毫秒）
    browser_close_delay: float  # 浏览器关闭延迟（秒）
    user_agents: list[str]  # User-Agent 列表
    image_download_timeout: int = 15  # 图片下载超时（秒）


@dataclass
class DocumentStyleConfig:
    """文档样式配置"""
    title_font_size: int  # 标题字号
    code_font_size: int  # 代码字号
    image_width: float  # 独立图片宽度（英寸）
    inline_image_width: float  # 内联图片宽度（英寸）
    footer_mark: str  # 页脚标记


@dataclass
class IndexConfig:
    """索引管理配置"""
    max_age_days: int  # 历史记录保留天数


@dataclass
class PandocConfig:
    """Pandoc 公式转换配置"""
    timeout: int  # Pandoc 超时（秒）


@dataclass
class ParserConfig:
    """解析器配置"""
    latex_attr: str  # LaTeX 公式属性名


@dataclass
class GlobalConfig:
    """全局配置单例"""
    crawler: CrawlerConfig  # 爬虫配置
    document_style: DocumentStyleConfig  # 文档样式配置
    index: IndexConfig  # 索引配置
    pandoc: PandocConfig  # Pandoc 配置
    parser: ParserConfig  # 解析器配置
    url_fallback_length: int  # URL 截断长度
    concurrency: int  # 批量并发数

    @classmethod
    def load(cls) -> "GlobalConfig":
        """从 config.yaml 加载配置"""
        data = _load_yaml()

        crawler_data: _ConfigDict = dict(data["crawler"])
        _require_keys(crawler_data, [
            "page_load_timeout", "scroll_wait_ms", "browser_close_delay", "user_agents"
        ], "crawler")
        crawler_data.setdefault("timeout", crawler_data["page_load_timeout"])
        crawler_data.setdefault("image_download_timeout", 15)
        crawler = CrawlerConfig(**crawler_data)

        doc_style_data: _ConfigDict = dict(data["document_style"])
        _require_keys(doc_style_data, [
            "title_font_size", "code_font_size", "image_width", "inline_image_width", "footer_mark"
        ], "document_style")
        document_style = DocumentStyleConfig(**doc_style_data)

        index_data: _ConfigDict = dict(data["index"])
        _require_keys(index_data, ["max_age_days"], "index")
        index = IndexConfig(**index_data)

        pandoc_data: _ConfigDict = dict(data["pandoc"])
        _require_keys(pandoc_data, ["timeout"], "pandoc")
        pandoc = PandocConfig(**pandoc_data)

        parser_data: _ConfigDict = dict(data["parser"])
        _require_keys(parser_data, ["latex_attr"], "parser")
        parser = ParserConfig(**parser_data)

        global_data: _ConfigDict = dict(data.get("global", {}))
        _require_keys(global_data, ["url_fallback_length", "concurrency"], "global")

        return cls(
            crawler=crawler,
            document_style=document_style,
            index=index,
            pandoc=pandoc,
            parser=parser,
            url_fallback_length=global_data["url_fallback_length"],
            concurrency=global_data["concurrency"],
        )


# 全局配置单例
_config: GlobalConfig | None = None


def get_config() -> GlobalConfig:
    """获取全局配置单例"""
    global _config
    if _config is None:
        _config = GlobalConfig.load()
    return _config
