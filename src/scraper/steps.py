"""
爬虫步骤枚举和进度工具

定义爬虫的各个步骤阶段，以及相关的进度显示工具函数。
"""

import time
from enum import Enum


class FetchStep(str, Enum):
    """爬虫步骤枚举"""
    STARTING = "任务开始"
    LOADING_PAGE = "加载网页"
    PAGE_LOADED = "加载完成"
    LOADING_IMAGES = "加载图片"
    EXPANDING_CODE = "展开代码"


# 步骤到索引的映射
STEP_INDEX = {
    FetchStep.STARTING: 0,
    FetchStep.LOADING_PAGE: 1,
    FetchStep.PAGE_LOADED: 2,
    FetchStep.LOADING_IMAGES: 3,
    FetchStep.EXPANDING_CODE: 4,
}

# 字符串 key 版本（供 cli.py 使用）
FETCH_STEP_NAMES = {
    "任务开始": 0,
    "加载网页": 1,
    "加载完成": 2,
    "加载图片": 3,
    "展开代码": 4,
    "解析内容": 5,
    "生成文档": 6,
}

STEP_COUNT = len(FETCH_STEP_NAMES)

# 任务开始时间（模块级变量）
_task_start_time = time.time()


def reset_timer() -> None:
    """重置计时器"""
    global _task_start_time
    _task_start_time = time.time()