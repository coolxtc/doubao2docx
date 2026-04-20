"""通用工具函数"""

import asyncio
import gc
import platform
import warnings


def is_windows() -> bool:
    """检查当前是否为 Windows 平台"""
    return platform.system() == "Windows"


def windows_compat_setup() -> None:
    """Windows 平台兼容性初始化，处理 ResourceWarning"""
    if is_windows():
        warnings.filterwarnings("ignore", category=ResourceWarning)


def windows_compat_cleanup() -> None:
    """Windows 平台资源清理，调用 gc.collect() 释放资源"""
    if is_windows():
        gc.collect()


async def windows_compat_close(delay: float) -> None:
    """Windows 平台浏览器关闭延迟"""
    if is_windows():
        gc.collect()
        await asyncio.sleep(delay)