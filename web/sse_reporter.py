"""SSE 进度报告器，实现 ProgressReporter Protocol"""

import asyncio
import json
from collections import deque
from collections.abc import AsyncGenerator

from src.scraper.steps import FETCH_STEP_NAMES, STEP_COUNT

# SSE 事件载荷（值为字符串/整数/浮点数的混合字典）
_EventPayload = dict[str, str | int | float]

# 订阅队列载荷（None 为流终止哨兵）
_SSEEvent = _EventPayload | None

# 历史事件环形缓冲上限（供断线重连回放）
HISTORY_LIMIT = 500

# 步骤索引到步骤名的反向映射（供 task_update 事件补充 step_name）
STEP_NAME_BY_INDEX: dict[int, str] = {index: name for name, index in FETCH_STEP_NAMES.items()}


class SSEReporter:
    """
    SSE 进度报告器

    多订阅者广播：每个 HTTP 订阅者持有独立队列，事件向全部队列扇出；
    另保留历史事件环形缓冲，新订阅者先回放历史再收实时事件。
    实现 ProgressReporter Protocol。
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[_SSEEvent]] = set()  # 各订阅者独立队列
        self._history: deque[_EventPayload] = deque(maxlen=HISTORY_LIMIT)  # 历史事件环形缓冲
        self._latest: dict[int, _EventPayload] = {}  # 每个 task_index 的最新 task_update 快照
        self._stopped: bool = False  # 流是否已终止（done 已广播）
        self._task_count: int = 0  # 已添加的任务行数

    def _enqueue(self, event: _SSEEvent) -> None:
        """
        线程安全入队（同步方法中安全调用）

        Args:
            event: 待广播事件，None 为终止哨兵
        """
        loop = asyncio.get_running_loop()
        loop.call_soon_threadsafe(self._broadcast, event)

    def _broadcast(self, event: _SSEEvent) -> None:
        """
        在事件循环内向所有订阅者扇出事件

        Args:
            event: 待扇出事件，None 为终止哨兵
        """
        # 收到哨兵：标记终止并向所有队列投递结束信号
        if event is None:
            self._stopped = True
            for queue in self._subscribers:
                queue.put_nowait(None)
            return
        self._history.append(event)
        for queue in self._subscribers:
            queue.put_nowait(event)

    def subscribe(self) -> asyncio.Queue[_SSEEvent]:
        """
        注册一个新的事件订阅者

        Returns:
            asyncio.Queue[_SSEEvent]: 订阅者专属队列，已按序预载历史事件
        """
        queue: asyncio.Queue[_SSEEvent] = asyncio.Queue()
        # 预载历史事件，保证重连客户端不丢失已发生的进度
        for event in self._history:
            queue.put_nowait(event)
        # 任务已结束时补投终止哨兵，使回放后立即收尾
        if self._stopped:
            queue.put_nowait(None)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[_SSEEvent]) -> None:
        """
        注销事件订阅者

        Args:
            queue: subscribe() 返回的订阅队列
        """
        self._subscribers.discard(queue)

    def add_task(self, task_index: int, url_tag: str) -> None:
        """
        添加导出任务行

        注意：fetch_and_export_batch 不会调用本方法（仅桌面 GUI 路径使用），
        前端进度不依赖 task_add 事件。

        Args:
            task_index: 任务序号
            url_tag: URL 标签（thread ID 或截断的 URL）
        """
        event: _EventPayload = {"type": "task_add", "task_index": task_index, "url_tag": url_tag}
        self._enqueue(event)
        self._task_count += 1

    def update(
        self,
        task_index: int,
        step: int,
        status: str,
        result: str = "",
        elapsed: float = 0.0,
    ) -> None:
        """
        更新导出任务进度（线程安全）

        Args:
            task_index: 任务序号
            step: 步骤索引（0-10，>= STEP_COUNT 为完成态）
            status: 状态文本
            result: 结果或错误信息
            elapsed: 已耗时（秒）
        """
        # 归一到最大有效步骤索引
        normalized_step = min(step, STEP_COUNT)
        # 完成态（索引 STEP_COUNT）不在步骤名映射中，回退空字符串
        step_name = STEP_NAME_BY_INDEX.get(normalized_step, "")
        event: _EventPayload = {
            "type": "task_update",
            "task_index": task_index,
            "step": normalized_step,
            "step_name": step_name,
            "status": status,
            "result": result,
            "elapsed": round(elapsed, 1),
            # 下载路径在批次结束后由 set_download_path() 补发填充
            "download_path": "",
        }
        self._latest[task_index] = event
        self._enqueue(event)

    def set_download_path(self, task_index: int, download_path: str) -> None:
        """
        为已完成任务补发下载路径（重新广播该任务最新进度）

        Args:
            task_index: 任务序号
            download_path: 相对 data/export 的文件路径，空串时不处理
        """
        latest = self._latest.get(task_index)
        # 该任务尚无进度快照或无路径时跳过
        if latest is None or not download_path:
            return
        # 复制新字典，避免改写已进入历史缓冲的旧事件
        enriched = dict(latest)
        enriched["download_path"] = download_path
        self._latest[task_index] = enriched
        self._enqueue(enriched)

    def log_warning(self, msg: str) -> None:
        """
        记录警告日志

        Args:
            msg: 警告消息
        """
        event: _EventPayload = {"type": "warning", "message": msg}
        self._enqueue(event)

    def start(self) -> None:
        """清空历史缓冲，准备新的导出批次"""
        self._history.clear()
        self._latest.clear()

    def stop(self) -> None:
        """推送完成事件并投递 None 哨兵终止所有订阅者"""
        done_event: _EventPayload = {"type": "done"}
        self._enqueue(done_event)
        self._enqueue(None)

    async def events(self, queue: asyncio.Queue[_SSEEvent]) -> AsyncGenerator[str, None]:
        """
        SSE 事件异步迭代器

        从订阅队列取出事件，格式化为 SSE 帧 ``data: {json}\\n\\n``；
        收到 None 哨兵值时结束迭代。

        Args:
            queue: subscribe() 返回的订阅队列

        Yields:
            str: SSE 格式的事件字符串
        """
        while True:
            event = await queue.get()
            # None 哨兵表示流终止
            if event is None:
                return
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
