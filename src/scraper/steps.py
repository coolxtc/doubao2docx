"""
爬虫步骤枚举和进度工具

定义爬虫的各个步骤阶段，以及相关的进度显示工具函数。
用于在 CLI 中显示任务执行进度。
"""

import time
from enum import Enum


class FetchStep(str, Enum):
    """
    爬虫步骤枚举
    
    定义爬虫执行过程中的各个阶段，用于进度追踪和显示。
    """
    STARTING = "任务开始"       # 任务初始化阶段
    LOADING_PAGE = "加载网页"   # 访问页面并等待加载完成
    LOADING_IMAGES = "加载图片"  # 滚动触发懒加载图片
    EXPANDING_CODE = "展开代码"  # 点击展开代码块


# 步骤到索引的映射（枚举版本，用于爬虫内部）
STEP_INDEX = {
    FetchStep.STARTING: 0,
    FetchStep.LOADING_PAGE: 1,
    FetchStep.LOADING_IMAGES: 2,
    FetchStep.EXPANDING_CODE: 3,
}

# 字符串 key 版本（供 cli.py 进度显示使用，与 STEP_INDEX 互补）
FETCH_STEP_NAMES = {
    "任务开始": 0,
    "加载网页": 1,
    "加载图片": 2,
    "展开代码": 3,
    "解析内容": 4,
    "生成文档": 5,
}

# 总步骤数，用于进度条显示
STEP_COUNT = len(FETCH_STEP_NAMES)

# 任务开始时间（模块级变量，用于计算已耗时）
_task_start_time = time.time()


def reset_timer() -> None:
    """
    重置计时器
    
    在开始新的导出任务时调用，重置计时起点。
    """
    global _task_start_time
    _task_start_time = time.time()