"""
全局配置模块

所有配置从 config.yaml 读取，缺少必需配置时直接报错。
"""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Any, TypedDict

try:
    import yaml
except ImportError:
    yaml = None

YAML_AVAILABLE: bool = yaml is not None


class CrawlerData(TypedDict):
    page_load_timeout: int
    timeout: int
    scroll_wait_ms: int
    browser_close_delay: float
    user_agents: list[str]


class DocumentStyleData(TypedDict):
    title_font_size: int
    code_font_size: int
    image_width: float
    inline_image_width: float


class IndexData(TypedDict):
    max_age_days: int


class PandocData(TypedDict):
    timeout: int


class GlobalData(TypedDict):
    url_fallback_length: int
    concurrency: int


class ConfigData(TypedDict):
    crawler: CrawlerData
    document_style: DocumentStyleData
    index: IndexData
    pandoc: PandocData
    global_: GlobalData  # YAML 中为 global（Python 关键字需加下划线）


def _get_config_path() -> Path:
    """获取配置文件路径，不存在则报错"""
    if hasattr(sys, '_MEIPASS'):
        base_path = Path(sys._MEIPASS)  # pyright: ignore[reportAttributeAccessIssue]
    else:
        base_path = Path(__file__).parent.parent

    config_path = base_path / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    return config_path


def _load_yaml() -> ConfigData:
    """加载 YAML 配置，不存在或解析失败则报错"""
    if yaml is None:
        raise RuntimeError("需要 pyyaml 库来读取配置，请运行: pip install pyyaml")

    config_path = _get_config_path()
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        if data is None:
            raise ValueError(f"配置文件为空: {config_path}")
        return data  # type: ignore[return-value]


_ConfigDict = dict[str, Any]


def _require_keys(data: _ConfigDict, keys: list[str], section: str) -> None:
    """检查必需的配置键，缺失则报错"""
    missing = [k for k in keys if k not in data]
    if missing:
        raise KeyError(f"配置缺少必需字段 [{section}]: {', '.join(missing)}")


@dataclass
class CrawlerConfig:
    page_load_timeout: int
    timeout: int
    scroll_wait_ms: int
    browser_close_delay: float
    user_agents: list[str]


@dataclass
class DocumentStyleConfig:
    title_font_size: int
    code_font_size: int
    image_width: float
    inline_image_width: float


@dataclass
class IndexConfig:
    max_age_days: int


@dataclass
class PandocConfig:
    timeout: int


@dataclass
class GlobalConfig:
    crawler: CrawlerConfig
    document_style: DocumentStyleConfig
    index: IndexConfig
    pandoc: PandocConfig
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
            "title_font_size", "code_font_size", "image_width", "inline_image_width"
        ], "document_style")
        document_style = DocumentStyleConfig(**doc_style_data)

        index_data: _ConfigDict = dict(data["index"])
        _require_keys(index_data, ["max_age_days"], "index")
        index = IndexConfig(**index_data)

        pandoc_data: _ConfigDict = dict(data["pandoc"])
        _require_keys(pandoc_data, ["timeout"], "pandoc")
        pandoc = PandocConfig(**pandoc_data)

        global_data: _ConfigDict = dict(data.get("global", {}))
        _require_keys(global_data, ["url_fallback_length", "concurrency"], "global")

        return cls(
            crawler=crawler,
            document_style=document_style,
            index=index,
            pandoc=pandoc,
            url_fallback_length=global_data["url_fallback_length"],
            concurrency=global_data["concurrency"],
        )


_config: GlobalConfig | None = None


def get_config() -> GlobalConfig:
    """获取全局配置实例（单例）"""
    global _config
    if _config is None:
        _config = GlobalConfig.load()
    return _config
