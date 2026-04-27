"""Windows 平台兼容性工具"""

import asyncio
import gc
import os
import platform
import warnings


def is_windows() -> bool:
    """检测当前是否为 Windows 平台"""
    return platform.system() == "Windows"


def windows_compat_setup() -> None:
    """Windows 平台兼容性初始化"""
    if is_windows():
        warnings.filterwarnings("ignore", category=ResourceWarning)
        os.environ['PYTHONUTF8'] = '1'


def windows_compat_cleanup() -> None:
    """Windows 平台资源清理"""
    if is_windows():
        gc.collect()


async def windows_compat_close(delay: float) -> None:
    """
    浏览器关闭后延迟回收

    Args:
        delay: 等待时间（秒）
    """
    if is_windows():
        gc.collect()
        await asyncio.sleep(delay)
