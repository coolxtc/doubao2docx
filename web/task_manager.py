"""导出任务管理器"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from src.cli import fetch_and_export_batch
from src.generator.batch_report import BatchReport
from web.sse_reporter import SSEReporter

logger = logging.getLogger("doubao.web.task_manager")

# 导出根目录：默认仓库 data/，容器部署时由 DOUBAO_OUTPUT_DIR 指向挂载卷
_EXPORT_DIR = Path(
    os.environ.get("DOUBAO_OUTPUT_DIR") or Path(__file__).resolve().parent.parent / "data"
)

# 内存中保留的任务数上限（NAS 长期运行时防止任务表无界增长）
TASK_HISTORY_LIMIT = 100


@dataclass
class ExportTask:
    """导出任务"""
    task_id: str  # 任务 ID（uuid4 hex）
    urls: list[str]  # 豆包聊天链接列表
    level: str  # 反爬级别（low/medium/high）
    concurrency: int  # 批量并发数
    status: str = "pending"  # 任务状态（pending/running/completed/timeout/failed）
    created_at: datetime = field(default_factory=datetime.now)  # 任务创建时间
    reporter: SSEReporter | None = None  # SSE 进度报告器
    report: BatchReport | None = None  # 批次导出结果（执行完成后保留）


class ExportTaskManager:
    """
    导出任务管理器

    通过 Semaphore 控制最大并发导出数，支持任务超时。
    """

    def __init__(self, max_concurrent: int, timeout: float) -> None:
        """
        初始化任务管理器

        Args:
            max_concurrent: 最大并发导出数
            timeout: 单任务超时（秒）
        """
        self._tasks: dict[str, ExportTask] = {}  # 任务表（task_id → 任务）
        self._max_concurrent: int = max_concurrent  # 最大并发导出数
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(max_concurrent)  # 并发控制信号量
        self._timeout: float = timeout  # 单任务超时（秒）
        self._background: set[asyncio.Task[None]] = set()  # 后台任务强引用（防 GC）

    @property
    def max_concurrent(self) -> int:
        """最大并发导出数"""
        return self._max_concurrent

    def create_task(self, urls: list[str], level: str, concurrency: int) -> str:
        """
        创建导出任务，返回 task_id

        Args:
            urls: 豆包聊天链接列表
            level: 反爬级别
            concurrency: 并发数

        Returns:
            str: 任务 ID
        """
        task_id = uuid4().hex  # 任务 ID
        reporter = SSEReporter()  # 该任务专属 SSE 报告器
        task = ExportTask(
            task_id=task_id,
            urls=urls,
            level=level,
            concurrency=concurrency,
            status="pending",
            created_at=datetime.now(),
            reporter=reporter,
        )
        self._tasks[task_id] = task
        self._prune_tasks()
        logger.info(f"创建导出任务 {task_id}: {len(urls)} 个 URL")
        return task_id

    def _prune_tasks(self) -> None:
        """
        淘汰超出上限的历史任务

        仅淘汰已结束任务并按创建时间从旧到新删除，避免运行中的任务
        及其 SSE 事件历史被误删；进行中的任务不计入淘汰范围。
        """
        overflow = len(self._tasks) - TASK_HISTORY_LIMIT
        if overflow <= 0:
            return
        finished = [
            task for task in self._tasks.values()
            if task.status not in ("pending", "running")
        ]  # 可淘汰的已结束任务
        finished.sort(key=lambda task: task.created_at)  # 最旧优先
        for task in finished[:overflow]:
            self._tasks.pop(task.task_id, None)
            logger.info(f"淘汰历史任务 {task.task_id} (status={task.status})")

    def start_task(self, task_id: str) -> None:
        """
        后台启动任务协程并保存强引用

        直接丢弃 create_task 返回值可能导致任务被 GC 回收，
        完成回调中移除引用以保持集合有界。

        Args:
            task_id: 任务 ID
        """
        future = asyncio.create_task(self.run_task(task_id))
        self._background.add(future)
        future.add_done_callback(self._background.discard)

    def get_task(self, task_id: str) -> ExportTask | None:
        """
        查询任务

        Args:
            task_id: 任务 ID

        Returns:
            ExportTask | None: 任务实例，不存在则返回 None
        """
        return self._tasks.get(task_id)

    def get_reporter(self, task_id: str) -> SSEReporter | None:
        """
        获取任务的 SSE 报告器

        Args:
            task_id: 任务 ID

        Returns:
            SSEReporter | None: 报告器实例，任务不存在则返回 None
        """
        task = self._tasks.get(task_id)
        return task.reporter if task else None

    async def run_task(self, task_id: str) -> None:
        """
        执行导出任务（受 Semaphore 控制）

        通过 Semaphore 限制并发数，通过 asyncio.wait_for 控制超时。

        Args:
            task_id: 任务 ID
        """
        task = self._tasks.get(task_id)
        # 任务已被清理或从未创建
        if task is None:
            logger.warning(f"任务 {task_id} 不存在")
            return

        async with self._semaphore:
            task.status = "running"
            try:
                await asyncio.wait_for(self._execute(task), timeout=self._timeout)
                task.status = "completed"
            # 用 asyncio.TimeoutError 而非内置 TimeoutError：Python 3.10 下两者并非同一异常，
            # 而项目 requires-python 声明 >=3.10，需保证超时不被误判为 failed
            except asyncio.TimeoutError:
                task.status = "timeout"
                logger.warning(f"任务 {task_id} 超时 ({self._timeout}s)")
                if task.reporter:
                    task.reporter.log_warning(f"导出超时 ({self._timeout}s)")
            except Exception as e:
                task.status = "failed"
                logger.error(f"任务 {task_id} 失败: {e}")
                if task.reporter:
                    task.reporter.log_warning(f"导出失败: {e}")
            finally:
                # 终止哨兵通知所有 SSE 订阅者收尾
                if task.reporter:
                    task.reporter.stop()

    async def _execute(self, task: ExportTask) -> None:
        """
        实际执行导出并保留批次报告

        Args:
            task: 导出任务
        """
        if task.reporter:
            task.reporter.start()
        report = await fetch_and_export_batch(
            urls=task.urls,
            output_dir=_EXPORT_DIR,
            anti_detect_level=task.level,
            concurrency=task.concurrency,
            reporter=task.reporter,
        )
        task.report = report
        self._publish_download_paths(task)

    def _publish_download_paths(self, task: ExportTask) -> None:
        """
        将批次报告中的文件路径换算为相对 data/export 的下载路径并推送 SSE

        fetch_and_export_batch 按 urls 下标顺序聚合结果，
        report.results[i] 即对应 task_index = i + 1。

        Args:
            task: 导出任务
        """
        if task.reporter is None or task.report is None:
            return
        export_root = (_EXPORT_DIR / "export").resolve()  # 导出根目录
        for task_index, result in enumerate(task.report.results, start=1):
            # 跳过失败项或无文件路径的结果
            if not result.success or not result.file_path:
                continue
            try:
                # 相对导出目录的路径，统一为正斜杠供前端拼接 URL
                download_path = Path(result.file_path).resolve().relative_to(export_root).as_posix()
            except ValueError:
                logger.warning(f"下载路径不在导出目录内，跳过: {result.file_path}")
                continue
            task.reporter.set_download_path(task_index, download_path)


def create_task_manager() -> ExportTaskManager:
    """
    从环境变量创建 ExportTaskManager 实例

    读取 MAX_CONCURRENT_EXPORTS 环境变量（默认 1），
    EXPORT_TIMEOUT 环境变量（默认 180s）。

    Returns:
        ExportTaskManager: 任务管理器实例
    """
    max_concurrent = int(os.environ.get("MAX_CONCURRENT_EXPORTS", "1"))  # 最大并发导出数
    timeout = float(os.environ.get("EXPORT_TIMEOUT", "180.0"))  # 单任务超时（秒）
    return ExportTaskManager(max_concurrent=max_concurrent, timeout=timeout)
