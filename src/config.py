"""
全局配置模块

支持从以下来源加载配置（优先级从低到高）：
1. 代码默认值
2. YAML 配置文件（config.yaml）
3. 环境变量

配置加载顺序：
- 先从 YAML 加载基础配置
- 再用环境变量覆盖

环境变量命名规则：前缀_层级_键名，全部大写
例如：CRAWLER_TIMEOUT, INDEX_MAX_AGE_DAYS

配置结构：
- crawler: 爬虫相关配置
- index: 索引相关配置
- pandoc: 公式转换相关配置
- document_style: 文档样式配置
- global: 全局配置
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
    """
    获取配置文件路径

    查找顺序：
    1. PyInstaller 打包环境：sys._MEIPASS 目录
    2. 开发环境：项目根目录

    Returns:
        配置文件路径，如果不存在则返回 None
    """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包环境
        base_path = Path(sys._MEIPASS)
    else:
        # 开发环境：src/ 的父目录
        base_path = Path(__file__).parent.parent

    config_path = base_path / "config.yaml"
    return config_path if config_path.exists() else None


def _env_override(key: str, value, prefix: str = "") -> tuple[str, bool]:
    """
    检查环境变量覆盖，返回 (最终值, 是否被覆盖)

    环境变量命名规则：前缀_层级_键名，全部大写
    例如：CRAWLER_TIMEOUT, INDEX_MAX_AGE_DAYS

    Args:
        key: 配置键名
        value: 默认值（用于类型推断）
        prefix: 环境变量前缀

    Returns:
        (最终值, 是否被环境变量覆盖)
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
    """
    递归应用环境变量覆盖到配置字典

    Args:
        data: 配置字典
        prefix: 环境变量前缀（用于嵌套字典）

    Returns:
        应用环境变量覆盖后的字典
    """
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = _apply_env_overrides(value, f"{prefix}{key}_")
        else:
            result[key], _ = _env_override(key, value, prefix)
    return result


def load_yaml_config() -> dict:
    """
    从 YAML 文件加载配置

    Returns:
        配置字典，如果文件不存在或 YAML 不可用则返回空字典
    """
    config_path = _get_config_path()

    if config_path is None or not YAML_AVAILABLE:
        return {}

    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def get_config_overrides() -> dict:
    """
    获取所有配置覆盖（YAML + 环境变量）

    加载顺序：
    1. 从 YAML 加载基础配置
    2. 用环境变量覆盖

    Returns:
        配置字典
    """
    yaml_config = load_yaml_config()

    if yaml_config:
        return _apply_env_overrides(yaml_config)

    # 即使没有 YAML 配置，也从环境变量收集覆盖
    return _collect_env_overrides()


def _collect_env_overrides() -> dict:
    """
    仅从环境变量收集配置覆盖

    定义了所有支持的配置项及其环境变量前缀。
    用于在没有 YAML 配置文件时直接从环境变量加载。

    Returns:
        配置字典
    """
    result = {}

    # 整数字段定义
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

    # 浮点数字段定义
    float_fields = {
        "crawler": ["browser_close_delay", "retry_backoff_factor"],
    }

    # 环境变量前缀映射
    prefixes = {
        "crawler": "CRAWLER_",
        "index": "INDEX_",
        "pandoc": "PANDOC_",
        "document_style": "DOCUMENT_STYLE_",
        "global": "GLOBAL_",
    }

    # 收集整数字段
    for section, fields in int_fields.items():
        for field in fields:
            env_var = f"{prefixes[section]}{field.upper()}"
            env_value = os.environ.get(env_var)
            if env_value is not None:
                if section not in result:
                    result[section] = {}
                result[section][field] = int(env_value)

    # 收集浮点数字段
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
    """
    爬虫配置

    包含浏览器操作、超时、重试等配置。
    所有时间参数单位为毫秒（ms）。
    """
    # 分级超时配置（毫秒）
    page_load_timeout: int = 30000  # 页面加载超时
    scroll_timeout: int = 15000  # 滚动操作超时
    api_timeout: int = 10000  # API 请求超时

    # 统一超时（兼容旧配置）
    timeout: int = 30000
    scroll_max_attempts: int = 10  # 最大滚动次数
    scroll_wait_ms: int = 300  # 滚动后等待时间
    code_expand_settle_ms: int = 300  # 代码展开后稳定等待时间
    code_expand_base_ms: int = 300  # 代码展开基础等待时间
    code_expand_extra_ms: int = 300  # 代码展开额外等待时间（递增）
    code_expand_max_retries: int = 6  # 代码展开最大重试次数
    wait_for_selector: str = ".chat-content"  # 等待选择器
    browser_close_delay: float = 0.25  # 浏览器关闭延迟（秒）
    retry_max_attempts: int = 3  # 最大重试次数
    retry_base_delay_ms: int = 1000  # 重试基础延迟
    retry_max_delay_ms: int = 10000  # 重试最大延迟
    retry_backoff_factor: float = 2.0  # 重试退避因子
    user_agents: list[str] | None = None  # User-Agent 列表

    def __post_init__(self):
        """
        初始化后处理

        如果未提供 User-Agent 列表，则使用默认的真实浏览器 UA。
        这些 UA 来自真实的 Chrome、Firefox、Safari 浏览器，
        用于模拟真实用户访问，降低被反爬机制检测的概率。

        为什么需要多个 UA？
        - 单一 UA 容易被识别为机器人
        - 随机切换 UA 可以模拟不同用户的访问
        - 不同浏览器有不同的 HTTP 头特征
        """
        # 默认 User-Agent 列表
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
        """
        从字典创建实例

        只设置提供的字段，未提供的使用默认值。

        Args:
            data: 配置字典

        Returns:
            CrawlerConfig 实例
        """
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
    """
    文档样式配置

    包含 Word 文档的字体、字号等样式设置。
    """
    title_font_size: int = 18  # 标题字号
    code_font_size: int = 10  # 代码字号
    image_width: float = 5.0  # 独立图片宽度（英寸）
    inline_image_width: float = 4.0  # 内联图片宽度（英寸）

    @classmethod
    def from_dict(cls, data: dict) -> "DocumentStyleConfig":
        """
        从字典创建实例

        只设置提供的字段，未提供的使用默认值。
        这允许部分配置更新，不需要提供所有字段。

        Args:
            data: 配置字典，通常来自 YAML 或环境变量

        Returns:
            DocumentStyleConfig 实例
        """
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
    """
    索引配置

    包含 link_index.json 的管理配置。
    """
    max_age_days: int = 10  # 历史记录保留天数

    @classmethod
    def from_dict(cls, data: dict) -> "IndexConfig":
        """
        从字典创建实例

        只设置提供的字段，未提供的使用默认值。

        Args:
            data: 配置字典，通常来自 YAML 或环境变量

        Returns:
            IndexConfig 实例
        """
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
    """
    Pandoc 配置

    包含公式转换的设置。
    """
    timeout: int = 15  # Pandoc 超时时间（秒）

    @classmethod
    def from_dict(cls, data: dict) -> "PandocConfig":
        """
        从字典创建实例

        只设置提供的字段，未提供的使用默认值。

        Args:
            data: 配置字典，通常来自 YAML 或环境变量

        Returns:
            PandocConfig 实例
        """
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
    """
    全局配置

    包含所有子配置的单例入口。
    在 __post_init__ 中从 YAML 和环境变量加载配置。
    """
    crawler: CrawlerConfig | None = None
    document_style: DocumentStyleConfig | None = None
    index: IndexConfig | None = None
    pandoc: PandocConfig | None = None
    url_fallback_length: int = 20  # URL 截断长度
    enable_progress_bar: bool = True  # 是否启用进度条
    concurrency: int = 5  # 批量导出并发数

    def __post_init__(self):
        """
        初始化后处理 - 加载配置

        配置加载顺序（优先级从低到高）：
        1. 代码中的默认值
        2. YAML 配置文件 (config.yaml)
        3. 环境变量（可以覆盖 YAML）

        这样做的好处：
        - 默认值保证程序可以正常运行
        - YAML 允许用户自定义配置
        - 环境变量适合 CI/CD 或容器化部署场景
        """
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

        self.concurrency, _ = _env_override(
            "concurrency", self.concurrency, "GLOBAL_"
        )

    @classmethod
    def reload(cls) -> "GlobalConfig":
        """
        重新加载配置（从 YAML 和环境变量）

        Returns:
            新的 GlobalConfig 实例
        """
        return cls()


# 全局配置实例（延迟初始化，单例模式）
_config: GlobalConfig | None = None


def get_config() -> GlobalConfig:
    """
    获取全局配置实例（单例）

    Returns:
        GlobalConfig 实例
    """
    global _config
    if _config is None:
        _config = GlobalConfig()
    return _config
