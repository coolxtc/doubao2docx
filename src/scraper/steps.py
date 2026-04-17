"""
爬虫步骤枚举和进度工具

本模块定义了爬虫的各个步骤阶段，以及相关的进度显示工具函数。
"""

import time
from enum import Enum


class FetchStep(str, Enum):
    """爬虫步骤枚举 - 用于进度跟踪
    
    每个枚举值代表爬虫流程中的一个阶段，
    可以用于进度回调、状态显示等场景。
    """
    STARTING = "任务开始"
    RECEIVED = "收到任务"
    LOADING_PAGE = "访问页面"
    PAGE_LOADED = "加载完成"
    SCROLLING = "滚动加载"
    EXPANDING_CODE = "展开代码"
    EXTRACTING = "提取数据"
    COMPLETED = "爬取完成"


# 步骤到索引的映射
STEP_INDEX = {
    FetchStep.STARTING: 0,
    FetchStep.RECEIVED: 1,
    FetchStep.LOADING_PAGE: 2,
    FetchStep.PAGE_LOADED: 3,
    FetchStep.SCROLLING: 4,
    FetchStep.EXPANDING_CODE: 5,
    FetchStep.EXTRACTING: 6,
    FetchStep.COMPLETED: 7,
}

# 字符串 key 版本（供 cli.py 使用）
FETCH_STEP_NAMES = {
    "任务开始": 0,
    "收到任务": 1,
    "访问页面": 2,
    "加载完成": 3,
    "滚动加载": 4,
    "展开代码": 5,
    "提取数据": 6,
    "爬取完成": 7,
    "解析内容": 8,
    "生成文档": 9,
}

# 任务开始时间（模块级变量）
_task_start_time = time.time()


def reset_timer() -> None:
    """重置计时器
    
    在开始新任务时调用，重置任务开始时间。
    """
    global _task_start_time
    _task_start_time = time.time()