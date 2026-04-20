"""
通用工具函数模块

本模块提供跨平台兼容性处理和资源清理功能。

为什么需要这个模块？
在 Windows 平台上，Playwright 关闭浏览器后可能会出现资源未完全释放的问题，
表现为运行时报错 "ResourceWarning: coroutine was never awaited" 或
其他与资源清理相关的警告。这个模块通过以下方式解决：

1. 延迟关闭：关闭浏览器后等待一段时间再退出
2. 强制回收：显式调用 gc.collect() 触发垃圾回收
3. 警告过滤：过滤 Python 的 ResourceWarning

使用方式：
在程序开始时调用 windows_compat_setup() 进行初始化，
在程序结束时调用 windows_compat_cleanup() 进行清理。
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

    ResourceWarning 小科普：
    - Python 3.x 会在检测到资源未正确释放时发出警告
    - 在 Playwright 等异步库中，协程可能因为各种原因未被正确等待
    - 这些警告不影响程序功能，但可能干扰用户查看日志
    """
    if is_windows():
        warnings.filterwarnings("ignore", category=ResourceWarning)


def windows_compat_cleanup() -> None:
    """
    Windows 平台资源清理

    在程序结束时调用，触发 Python 垃圾回收器，
    确保所有 Playwright 创建的资源被正确释放。

    gc.collect() 小科普：
    - Python 使用自动垃圾回收机制（引用计数 + 循环垃圾回收）
    - 但有时候对象可能形成循环引用，导致无法立即释放
    - gc.collect() 强制执行垃圾回收，可以立即释放这些资源
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

    为什么需要延迟？
    - 操作系统关闭进程需要时间
    - 如果立即执行 gc.collect()，进程可能还没完全退出
    - 延迟确保资源真正释放后再进行垃圾回收
    """
    if is_windows():
        gc.collect()
        await asyncio.sleep(delay)
