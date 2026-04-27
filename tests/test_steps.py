"""
测试爬虫步骤枚举和工具
"""
import pytest
from src.scraper.steps import FetchStep, STEP_INDEX, FETCH_STEP_NAMES, STEP_COUNT, reset_timer


class TestFetchStep:
    """测试 FetchStep 枚举"""

    def test_enum_values(self):
        """枚举值应正确"""
        assert FetchStep.STARTING.value == "任务开始"
        assert FetchStep.LOADING_PAGE.value == "加载网页"
        assert FetchStep.LOADING_IMAGES.value == "加载图片"
        assert FetchStep.EXPANDING_CODE.value == "展开代码"

    def test_step_index(self):
        """步骤索引映射"""
        assert STEP_INDEX[FetchStep.STARTING] == 0
        assert STEP_INDEX[FetchStep.LOADING_PAGE] == 1
        assert STEP_INDEX[FetchStep.LOADING_IMAGES] == 2
        assert STEP_INDEX[FetchStep.EXPANDING_CODE] == 3

    def test_step_names(self):
        """步骤名称映射"""
        assert FETCH_STEP_NAMES["任务开始"] == 0
        assert FETCH_STEP_NAMES["加载网页"] == 1
        assert FETCH_STEP_NAMES["加载图片"] == 2
        assert FETCH_STEP_NAMES["展开代码"] == 3
        assert FETCH_STEP_NAMES["解析内容"] == 4
        assert FETCH_STEP_NAMES["生成文档"] == 5

    def test_step_count(self):
        """总步骤数"""
        assert STEP_COUNT == 6

    def test_reset_timer(self):
        """重置计时器"""
        reset_timer()
        assert True