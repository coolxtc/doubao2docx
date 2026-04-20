"""
通用工具函数模块

提供 Windows 平台的兼容性处理和资源清理功能：
- 延迟关闭：关闭浏览器后等待一段时间再退出
- 强制回收：显式调用 gc.collect() 触发垃圾回收
- 警告过滤：过滤 Python 的 ResourceWarning

使用方式：
- 程序开始时调用 windows_compat_setup() 进行初始化
- 程序结束时调用 windows_compat_cleanup() 进行清理
"""

import asyncio
import gc
import platform
import warnings


def is_windows() -> bool:
    """
    检查当前是否为 Windows 平台

    Returns:
        True 如果是 Windows 系统，否则 False
    """
    return platform.system() == "Windows"


def windows_compat_setup() -> None:
    """
    Windows 平台兼容性初始化

    在程序开始时调用，设置 Python 警告过滤器，
    避免显示 ResourceWarning 等与资源清理相关的警告。
    """
    if is_windows():
        warnings.filterwarnings("ignore", category=ResourceWarning)


def windows_compat_cleanup() -> None:
    """
    Windows 平台资源清理

    在程序结束时调用，触发 Python 垃圾回收器，
    确保所有 Playwright 创建的资源被正确释放。
    """
    if is_windows():
        gc.collect()


async def windows_compat_close(delay: float) -> None:
    """
    Windows 平台浏览器关闭延迟

    在关闭浏览器后等待一段时间，然后执行垃圾回收。
    这个延迟确保操作系统有足够时间释放与浏览器进程相关的资源。

    Args:
        delay: 等待时间（秒）
    """
    if is_windows():
        gc.collect()
        await asyncio.sleep(delay)
