"""
全局配置模块

所有配置从 config.yaml 读取，缺少必需配置时直接报错。
"""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Any, TypedDict, cast

try:
    import yaml
except ImportError:
    yaml = None

YAML_AVAILABLE: bool = yaml is not None


class CrawlerData(TypedDict):
    """
    爬虫配置数据类型
    
    定义爬虫相关配置项的类型约束，用于 YAML 配置解析时的类型检查。
    """
    page_load_timeout: int      # 页面加载超时时间（毫秒）
    timeout: int                # 请求超时时间（毫秒）
    scroll_wait_ms: int         # 滚动后等待时间（毫秒）
    browser_close_delay: float   # 浏览器关闭延迟（秒）
    user_agents: list[str]      # 可用的 User-Agent 列表


class DocumentStyleData(TypedDict):
    title_font_size: int        # 标题字号
    code_font_size: int         # 代码字号
    image_width: float          # 独立图片宽度（英寸）
    inline_image_width: float    # 内联图片宽度（英寸）
    footer_mark: str            # 文档末尾标注


class IndexData(TypedDict):
    """
    索引配置数据类型
    
    定义链接索引文件的管理配置。
    """
    max_age_days: int           # 历史记录保留天数


class PandocData(TypedDict):
    timeout: int


class ParserData(TypedDict):
    latex_attr: str


class GlobalData(TypedDict):
    """
    全局配置数据类型
    
    定义全局通用配置项。
    """
    url_fallback_length: int    # URL 截断长度
    concurrency: int            # 批量并发数


class ConfigData(TypedDict):
    """
    完整配置数据类型
    
    包含所有配置节的总类型定义。
    """
    crawler: CrawlerData
    document_style: DocumentStyleData
    index: IndexData
    pandoc: PandocData
    parser: ParserData
    global_: GlobalData


def _get_config_path() -> Path:
    """获取配置文件路径，不存在则报错"""
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
    required_sections = ["crawler", "document_style", "index", "pandoc", "parser", "global"]
    missing = [s for s in required_sections if s not in data]
    if missing:
        raise KeyError(f"配置缺少必需节: {', '.join(missing)}")


# 配置字典类型别名，用于类型注解
_ConfigDict = dict[str, Any]


def _require_keys(data: _ConfigDict, keys: list[str], section: str) -> None:
    """检查必需的配置键，缺失则报错"""
    missing = [k for k in keys if k not in data]
    if missing:
        raise KeyError(f"配置缺少必需字段 [{section}]: {', '.join(missing)}")


@dataclass
class CrawlerConfig:
    """
    爬虫配置数据类
    
    存储运行时爬虫配置，从 YAML 配置加载。
    """
    page_load_timeout: int      # 页面加载超时时间（毫秒）
    timeout: int                # 请求超时时间（毫秒）
    scroll_wait_ms: int         # 滚动后等待时间（毫秒）
    browser_close_delay: float   # 浏览器关闭延迟（秒）
    user_agents: list[str]      # 可用的 User-Agent 列表


@dataclass
class DocumentStyleConfig:
    title_font_size: int        # 标题字号
    code_font_size: int         # 代码字号
    image_width: float         # 独立图片宽度（英寸）
    inline_image_width: float   # 内联图片宽度（英寸）
    footer_mark: str        # 文档末尾标注


@dataclass
class IndexConfig:
    """
    索引配置数据类
    
    存储链接索引管理配置。
    """
    max_age_days: int           # 历史记录保留天数


@dataclass
class PandocConfig:
    """
    Pandoc 配置数据类
    
    存储公式转换工具配置。
    """
    timeout: int


@dataclass
class ParserConfig:
    latex_attr: str


@dataclass
class GlobalConfig:
    crawler: CrawlerConfig
    document_style: DocumentStyleConfig
    index: IndexConfig
    pandoc: PandocConfig
    parser: ParserConfig
    url_fallback_length: int
    concurrency: int

    @classmethod
    def load(cls) -> "GlobalConfig":
        """从 config.yaml 加载配置"""
        data = _load_yaml()

        crawler_data: _ConfigDict = dict(data["crawler"])
        _require_keys(crawler_data, [
            "page_load_timeout", "scroll_wait_ms", "browser_close_delay", "user_agents"
        ], "crawler")
        crawler_data.setdefault("timeout", crawler_data["page_load_timeout"])
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


# 全局配置实例缓存（单例模式）
_config: GlobalConfig | None = None


def get_config() -> GlobalConfig:
    """获取全局配置实例（单例）"""
    global _config
    if _config is None:
        _config = GlobalConfig.load()
    return _config
