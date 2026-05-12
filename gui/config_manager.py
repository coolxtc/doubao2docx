"""简单的用户配置管理（导出目录等）"""
import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".doubao_export"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_EXPORT_PATH = str(Path.home() / "Desktop" / "豆包对话导出")

# 配置类型别名
Config = dict[str, str]


def load_config() -> Config:
    """加载配置，若无则返回默认值"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)  # type: ignore[return-value]
        except Exception:
            pass
    return {"export_dir": DEFAULT_EXPORT_PATH}


def save_config(config: Config) -> None:
    """保存配置到文件"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_export_dir() -> str:
    """获取当前使用的导出目录"""
    config = load_config()
    return config.get("export_dir", DEFAULT_EXPORT_PATH)  # type: ignore[arg-type]


def set_export_dir(path: str) -> None:
    """设置并保存导出目录"""
    config = load_config()
    config["export_dir"] = path
    save_config(config)
