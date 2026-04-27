"""
测试反爬中间件

注意：AntiDetectMiddleware 需要访问配置，需要 mock。
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch


class TestAntiDetectMiddleware:
    """测试反爬中间件"""

    @pytest.fixture
    def mock_config(self):
        """Mock 配置"""
        mock = Mock()
        mock.crawler = Mock()
        mock.crawler.user_agents = ["Mozilla/5.0 (Test)"]
        return mock

    def test_init_default(self, mock_config):
        """默认初始化"""
        with patch("src.config.get_config", return_value=mock_config):
            from src.scraper.anti_detect import AntiDetectMiddleware
            middleware = AntiDetectMiddleware(random_user_agent=True, disableAutomation=True)
            assert middleware.random_user_agent is True
            assert middleware.disableAutomation is True

    def test_init_with_user_agents(self, mock_config):
        """带 User-Agent 列表"""
        with patch("src.config.get_config", return_value=mock_config):
            from src.scraper.anti_detect import AntiDetectMiddleware
            middleware = AntiDetectMiddleware(random_user_agent=True, disableAutomation=False)
            assert len(middleware.user_agents) == 1

    @pytest.mark.asyncio
    async def test_apply(self, mock_config):
        """应用反爬措施"""
        with patch("src.config.get_config", return_value=mock_config):
            from src.scraper.anti_detect import AntiDetectMiddleware
            middleware = AntiDetectMiddleware(random_user_agent=False, disableAutomation=False)
            context = AsyncMock()
            await middleware.apply(context)


class TestCreateAntiDetectMiddleware:
    """测试工厂函数"""

    def test_create_low(self):
        """low 级别"""
        from src.scraper.anti_detect import create_anti_detect_middleware
        middleware = create_anti_detect_middleware("low")
        assert middleware.random_user_agent is True
        assert middleware.disableAutomation is False

    def test_create_medium(self):
        """medium 级别"""
        from src.scraper.anti_detect import create_anti_detect_middleware
        middleware = create_anti_detect_middleware("medium")
        assert middleware.random_user_agent is True
        assert middleware.disableAutomation is True

    def test_create_high(self):
        """high 级别"""
        from src.scraper.anti_detect import create_anti_detect_middleware
        middleware = create_anti_detect_middleware("high")
        assert middleware.random_user_agent is True
        assert middleware.disableAutomation is True

    def test_create_unknown_uses_medium(self):
        """未知级别使用 medium"""
        from src.scraper.anti_detect import create_anti_detect_middleware
        middleware = create_anti_detect_middleware("unknown")
        assert middleware.disableAutomation is True