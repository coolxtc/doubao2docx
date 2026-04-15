"""
全局配置模块 - 支持 YAML 文件和环境变量加载
"""

import os
import sys
from dataclasses import dataclass, fields
from pathlib import Path

# 尝试导入 yaml，失败时使用默认值
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


# ============================================================
# 配置加载器
# ============================================================

def _get_config_path() -> Path | None:
    """获取配置文件路径"""
    # 优先查找项目根目录的 config.yaml
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包环境
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent.parent
    
    config_path = base_path / "config.yaml"
    return config_path if config_path.exists() else None


def _env_override(key: str, value, prefix: str = "") -> tuple[str, bool]:
    """
    检查环境变量覆盖，返回 (最终值, 是否被覆盖)
    
    环境变量命名规则：前缀_层级_键名，全部大写
    例如：CRAWLER_TIMEOUT, INDEX_MAX_AGE_DAYS
    """
    env_key = f"{prefix}{key}".upper()
    env_value = os.environ.get(env_key)
    
    if env_value is None:
        return value, False
    
    # 根据原始值类型转换环境变量
    if isinstance(value, bool):
        return env_value.lower() in ('true', '1', 'yes'), True
    elif isinstance(value, int):
        return int(env_value), True
    elif isinstance(value, float):
        return float(env_value), True
    elif isinstance(value, list):
        # 列表类型从 YAML 加载，不从环境变量覆盖
        return value, False
    else:
        return env_value, True


def _apply_env_overrides(data: dict, prefix: str = "") -> dict:
    """递归应用环境变量覆盖到配置字典"""
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = _apply_env_overrides(value, f"{prefix}{key}_")
        else:
            result[key], _ = _env_override(key, value, prefix)
    return result


def load_yaml_config() -> dict:
    """从 YAML 文件加载配置"""
    config_path = _get_config_path()
    
    if config_path is None or not YAML_AVAILABLE:
        return {}
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def get_config_overrides() -> dict:
    """获取所有配置覆盖（YAML + 环境变量）"""
    yaml_config = load_yaml_config()
    
    if yaml_config:
        return _apply_env_overrides(yaml_config)
    
    # 即使没有 YAML 配置，也从环境变量收集覆盖
    return _collect_env_overrides()


def _collect_env_overrides() -> dict:
    """仅从环境变量收集配置覆盖"""
    result = {}
    
    int_fields = {
        "crawler": ["page_load_timeout", "scroll_timeout", "api_timeout",
                    "timeout", "scroll_max_attempts", "scroll_wait_ms",
                    "code_expand_settle_ms", "code_expand_base_ms", "code_expand_extra_ms",
                    "code_expand_max_retries",
                    "retry_max_attempts", "retry_base_delay_ms", "retry_max_delay_ms"],
        "index": ["max_age_days"],
        "pandoc": ["timeout"],
        "document_style": ["title_font_size", "code_font_size"],
        "global": ["url_fallback_length"],
    }
    float_fields = {
        "crawler": ["browser_close_delay", "retry_backoff_factor"],
    }
    
    prefixes = {
        "crawler": "CRAWLER_",
        "index": "INDEX_",
        "pandoc": "PANDOC_",
        "document_style": "DOCUMENT_STYLE_",
        "global": "GLOBAL_",
    }
    
    for section, fields in int_fields.items():
        for field in fields:
            env_var = f"{prefixes[section]}{field.upper()}"
            env_value = os.environ.get(env_var)
            if env_value is not None:
                if section not in result:
                    result[section] = {}
                result[section][field] = int(env_value)
    
    for section, fields in float_fields.items():
        for field in fields:
            env_var = f"{prefixes[section]}{field.upper()}"
            env_value = os.environ.get(env_var)
            if env_value is not None:
                if section not in result:
                    result[section] = {}
                result[section][field] = float(env_value)
    
    # 字符串类型（wait_for_selector）
    env_value = os.environ.get("CRAWLER_WAIT_FOR_SELECTOR")
    if env_value is not None:
        result.setdefault("crawler", {})["wait_for_selector"] = env_value
    
    return result


# ============================================================
# 爬虫配置类
# ============================================================

@dataclass
class CrawlerConfig:
    # 分级超时配置（毫秒）
    page_load_timeout: int = 30000
    scroll_timeout: int = 15000
    api_timeout: int = 10000
    
    # 统一超时（兼容旧配置）
    timeout: int = 30000
    scroll_max_attempts: int = 10
    scroll_wait_ms: int = 1000
    code_expand_settle_ms: int = 2000
    code_expand_base_ms: int = 2500
    code_expand_extra_ms: int = 2000
    code_expand_max_retries: int = 6
    wait_for_selector: str = ".chat-content"
    browser_close_delay: float = 0.25
    retry_max_attempts: int = 3
    retry_base_delay_ms: int = 1000
    retry_max_delay_ms: int = 10000
    retry_backoff_factor: float = 2.0
    user_agents: list[str] | None = None

    def __post_init__(self):
        if self.user_agents is None:
            self.user_agents = [
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            ]

    @classmethod
    def from_dict(cls, data: dict) -> "CrawlerConfig":
        """从字典创建实例，只设置提供的字段"""
        if data is None:
            return cls()
        
        valid_fields = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


# ============================================================
# 文档样式配置类
# ============================================================

@dataclass
class DocumentStyleConfig:
    title_font_size: int = 18
    code_font_size: int = 10

    @classmethod
    def from_dict(cls, data: dict) -> "DocumentStyleConfig":
        """从字典创建实例，只设置提供的字段"""
        if data is None:
            return cls()
        
        valid_fields = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


# ============================================================
# 索引配置类
# ============================================================

@dataclass
class IndexConfig:
    max_age_days: int = 10

    @classmethod
    def from_dict(cls, data: dict) -> "IndexConfig":
        """从字典创建实例，只设置提供的字段"""
        if data is None:
            return cls()
        
        valid_fields = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


# ============================================================
# Pandoc 配置类
# ============================================================

@dataclass
class PandocConfig:
    timeout: int = 15

    @classmethod
    def from_dict(cls, data: dict) -> "PandocConfig":
        """从字典创建实例，只设置提供的字段"""
        if data is None:
            return cls()
        
        valid_fields = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


# ============================================================
# 全局配置类
# ============================================================

@dataclass 
class GlobalConfig:
    crawler: CrawlerConfig | None = None
    document_style: DocumentStyleConfig | None = None
    index: IndexConfig | None = None
    pandoc: PandocConfig | None = None
    url_fallback_length: int = 20
    enable_progress_bar: bool = True

    def __post_init__(self):
        overrides = get_config_overrides()
        
        if self.crawler is None:
            crawler_data = overrides.get("crawler", {})
            self.crawler = CrawlerConfig.from_dict(crawler_data)
        
        if self.document_style is None:
            self.document_style = DocumentStyleConfig.from_dict(overrides.get("document_style"))
        
        if self.index is None:
            self.index = IndexConfig.from_dict(overrides.get("index"))
        
        if self.pandoc is None:
            self.pandoc = PandocConfig.from_dict(overrides.get("pandoc"))
        
        # 全局配置项（支持环境变量覆盖）
        self.url_fallback_length, _ = _env_override(
            "url_fallback_length", self.url_fallback_length, "GLOBAL_"
        )
        
        self.enable_progress_bar, _ = _env_override(
            "enable_progress_bar", self.enable_progress_bar, "GLOBAL_"
        )

    @classmethod
    def reload(cls) -> "GlobalConfig":
        """重新加载配置（从 YAML 和环境变量）"""
        return cls()


# 全局配置实例（延迟初始化）
_config: GlobalConfig | None = None


def get_config() -> GlobalConfig:
    """获取全局配置实例（单例）"""
    global _config
    if _config is None:
        _config = GlobalConfig()
    return _config
