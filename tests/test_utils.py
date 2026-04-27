"""
测试通用工具函数
"""
import pytest


class TestIsWindows:
    """测试 is_windows 函数"""

    def test_returns_true_on_windows(self, monkeypatch):
        """Windows 系统应返回 True"""
        monkeypatch.setattr("platform.system", lambda: "Windows")
        from src.utils import is_windows
        assert is_windows() is True

    def test_returns_false_on_darwin(self, monkeypatch):
        """macOS 系统应返回 False"""
        monkeypatch.setattr("platform.system", lambda: "Darwin")
        from src.utils import is_windows
        assert is_windows() is False

    def test_returns_false_on_linux(self, monkeypatch):
        """Linux 系统应返回 False"""
        monkeypatch.setattr("platform.system", lambda: "Linux")
        from src.utils import is_windows
        assert is_windows() is False


class TestWindowsCompatSetup:
    """测试 windows_compat_setup 函数"""

    def test_no_error_on_windows(self, monkeypatch):
        """Windows 上调用不应报错"""
        monkeypatch.setattr("platform.system", lambda: "Windows")
        from src.utils import windows_compat_setup
        windows_compat_setup()
        assert True

    def test_no_error_on_linux(self, monkeypatch):
        """Linux 上调用不应报错"""
        monkeypatch.setattr("platform.system", lambda: "Linux")
        from src.utils import windows_compat_setup
        windows_compat_setup()
        assert True


class TestWindowsCompatCleanup:
    """测试 windows_compat_cleanup 函数"""

    def test_no_error_on_windows(self, monkeypatch):
        """Windows 上调用不应报错"""
        monkeypatch.setattr("platform.system", lambda: "Windows")
        from src.utils import windows_compat_cleanup
        windows_compat_cleanup()
        assert True

    def test_no_error_on_linux(self, monkeypatch):
        """Linux 上调用不应报错"""
        monkeypatch.setattr("platform.system", lambda: "Linux")
        from src.utils import windows_compat_cleanup
        windows_compat_cleanup()
        assert True
