"""导出 API 路由"""

import os
import tempfile
import zipfile
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from web.sse_reporter import SSEReporter
from web.task_manager import ExportTaskManager, _EXPORT_DIR

router = APIRouter()

# 导出文件下载根目录（相对 data/export）
_DOWNLOAD_ROOT = (_EXPORT_DIR / "export").resolve()

# 单次 zip 打包的文件数上限
_ZIP_MAX_FILES = 50

# zip 临时文件前缀（便于排查残留）
_ZIP_TMP_PREFIX = "doubao-export-zip-"


class ExportRequest(BaseModel):
    """导出请求体"""
    urls: list[str]  # 豆包聊天链接列表
    level: Literal["low", "medium", "high"] = "medium"  # 反爬级别
    concurrency: int = Field(default=3, ge=1, le=10)  # 批量并发数


class ExportItemView(BaseModel):
    """单条导出结果的结构化视图"""
    task_index: int  # 任务序号（从 1 开始，与 SSE 事件一致）
    url: str  # 来源链接
    success: bool  # 是否导出成功
    filename: str = ""  # 输出文件名
    download_path: str = ""  # 相对 data/export 的下载路径
    error: str = ""  # 失败原因


class TaskStatusView(BaseModel):
    """任务状态查询响应"""
    task_id: str  # 任务 ID
    status: str  # 任务状态（pending/running/completed/timeout/failed）
    created_at: datetime  # 创建时间
    results: list[ExportItemView]  # 各 URL 的结构化结果


def _get_task_manager(request: Request) -> ExportTaskManager:
    """
    从 app.state 获取 ExportTaskManager

    Args:
        request: FastAPI 请求对象

    Returns:
        ExportTaskManager: 任务管理器实例

    Raises:
        HTTPException: 任务管理器未初始化
    """
    manager = getattr(request.app.state, "task_manager", None)
    if manager is None:
        raise HTTPException(status_code=500, detail="任务管理器未初始化")
    return manager


async def _sse_adapter(reporter: SSEReporter) -> AsyncGenerator[dict[str, str], None]:
    """
    为单个 HTTP 订阅者构建 SSE 事件流

    SSEReporter.events() 产出预格式化的 SSE 字符串 ``"data: {json}\\n\\n"``，
    EventSourceResponse 需要字典 ``{"data": "..."}`` 格式，此适配器完成转换；
    客户端断开时注销订阅者队列。

    Args:
        reporter: SSE 进度报告器

    Yields:
        dict[str, str]: EventSourceResponse 所需的事件字典
    """
    queue = reporter.subscribe()
    try:
        async for frame in reporter.events(queue):
            # 剥离 SSE 帧头尾，还原 JSON 文本交给 EventSourceResponse 重新组帧
            yield {"data": frame[len("data: "):-2]}
    finally:
        reporter.unsubscribe(queue)


@router.post("/api/export")
async def create_export(request: ExportRequest, req: Request) -> dict[str, str]:
    """
    提交导出任务

    验证请求体后创建后台导出任务，立即返回 task_id 供 SSE 订阅。

    Args:
        request: 导出请求体（urls, level, concurrency）
        req: FastAPI 请求对象（用于获取 task_manager）

    Returns:
        dict[str, str]: 含 task_id 的响应体
    """
    if not request.urls:
        raise HTTPException(status_code=422, detail="urls 不能为空")
    manager = _get_task_manager(req)
    task_id = manager.create_task(
        urls=request.urls,
        level=request.level,
        concurrency=request.concurrency,
    )
    # 后台启动：强引用由 manager 保存，防止任务被 GC
    manager.start_task(task_id)
    return {"task_id": task_id}


@router.get("/api/export/{task_id}")
async def get_export_status(task_id: str, req: Request) -> TaskStatusView:
    """
    查询任务结构化状态

    供前端在 SSE 之外获取最终结果（含各 URL 的下载路径）。

    Args:
        task_id: 任务 ID
        req: FastAPI 请求对象

    Returns:
        TaskStatusView: 任务状态与结构化结果列表

    Raises:
        HTTPException: 任务不存在
    """
    manager = _get_task_manager(req)
    task = manager.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    results: list[ExportItemView] = []
    # 批次尚未完成时无报告，返回空结果列表
    if task.report is not None:
        export_root = _DOWNLOAD_ROOT  # 导出根目录
        # results 与 urls 严格等长同序（asyncio.gather 保序，成功与失败分支均 append），
        # 因此这里的位置序号可直接当作 SSE 使用的 task_index
        for index, item in enumerate(task.report.results, start=1):
            download_path = ""
            # 成功且有文件路径时换算相对下载路径
            if item.success and item.file_path:
                try:
                    download_path = Path(item.file_path).resolve().relative_to(export_root).as_posix()
                except ValueError:
                    download_path = ""
            results.append(ExportItemView(
                task_index=index,
                url=item.url,
                success=item.success,
                filename=item.filename or "",
                download_path=download_path,
                error=item.error_message or "",
            ))
    return TaskStatusView(
        task_id=task.task_id,
        status=task.status,
        created_at=task.created_at,
        results=results,
    )


@router.get("/api/export/{task_id}/stream")
async def stream_export(task_id: str, req: Request) -> EventSourceResponse:
    """
    SSE 进度推送端点

    客户端通过此端点订阅导出任务的实时进度；
    新订阅者先收到历史事件回放，再收实时事件，最后流终止。

    Args:
        task_id: 任务 ID
        req: FastAPI 请求对象

    Returns:
        EventSourceResponse: SSE 事件流

    Raises:
        HTTPException: 任务不存在
    """
    manager = _get_task_manager(req)
    reporter = manager.get_reporter(task_id)
    if reporter is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return EventSourceResponse(_sse_adapter(reporter))


@router.get("/download/{file_path:path}")
async def download_file(file_path: str) -> FileResponse:
    """
    文件下载端点

    仅允许下载 data/export/ 目录下的文件，防止目录遍历攻击。

    Args:
        file_path: 相对于 data/export/ 的文件路径

    Returns:
        FileResponse: 文件下载响应

    Raises:
        HTTPException: 越界访问（403）或文件不存在（404）
    """
    requested = (_DOWNLOAD_ROOT / file_path).resolve()
    # 解析后仍须位于导出根目录内
    if not requested.is_relative_to(_DOWNLOAD_ROOT):
        raise HTTPException(status_code=403, detail="禁止访问")
    if not requested.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path=str(requested), filename=requested.name)


def _unique_zip_entry_name(filename: str, used: set[str]) -> str:
    """
    计算 zip 条目名并对同名冲突做去重

    Args:
        filename: 文件 basename
        used: 已被占用的条目名集合（调用后包含新分配的条目名）

    Returns:
        str: 未被占用的条目名（重名时形如 ``"标题 (2).docx"``）
    """
    stem, suffix = os.path.splitext(filename)  # 主干与扩展名，用于插入去重后缀
    entry = filename  # 候选条目名
    index = 2  # 重名时的递增序号
    while entry in used:
        entry = f"{stem} ({index}){suffix}"
        index += 1
    used.add(entry)
    return entry


def _write_zip(zip_path: Path, entries: list[tuple[Path, str]]) -> None:
    """
    把文件列表写入 zip 包

    同步实现，由线程池调度，避免大文件批量压缩阻塞事件循环上的 SSE 推送。

    Args:
        zip_path: 目标 zip 路径
        entries: (源文件绝对路径, zip 内条目名) 列表
    """
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, entry in entries:
            archive.write(filename=str(path), arcname=entry)


def _remove_temp_zip(zip_path: Path) -> None:
    """
    删除打包用的临时 zip 文件

    Args:
        zip_path: 临时 zip 路径
    """
    # missing_ok 兜底重复清理，避免需要空的异常捕获
    zip_path.unlink(missing_ok=True)


@router.get("/api/download-zip")
async def download_zip(paths: list[str] = Query(default=[])) -> FileResponse:
    """
    批量下载打包端点

    把 data/export/ 下的多个文件打包成单个 zip 一次返回，供移动端一次取走。
    使用 GET + 重复 paths 查询参数，让 iOS Safari 以导航方式触发下载
    （blob + fetch 方案在 Safari 上不可靠）。

    Args:
        paths: 相对于 data/export/ 的文件路径列表（重复的 paths 查询参数）

    Returns:
        FileResponse: application/zip 下载响应，临时文件在响应发送后由后台任务删除

    Raises:
        HTTPException: paths 为空或超过上限（422）、越界访问（403）、
            文件不存在（404）、打包写入失败（500）
    """
    # 数量保护：空请求、含空白项、超大请求都在读磁盘前拒绝
    # 空白项按 422 处理（请求格式错误），而不是落到后面的 404（资源不存在）
    if not paths or any(not item.strip() for item in paths):
        raise HTTPException(status_code=422, detail="paths 不能为空")
    if len(paths) > _ZIP_MAX_FILES:
        raise HTTPException(status_code=422, detail=f"paths 数量不能超过 {_ZIP_MAX_FILES}")

    resolved: list[Path] = []  # 通过校验的绝对路径
    for raw in paths:
        requested = (_DOWNLOAD_ROOT / raw).resolve()
        # 第一遍只做穿越校验：任一越界即整体拒绝，不被其他无效路径掩盖
        if not requested.is_relative_to(_DOWNLOAD_ROOT):
            raise HTTPException(status_code=403, detail="禁止访问")
        resolved.append(requested)
    for requested in resolved:
        # 第二遍校验存在性：任一文件缺失即整体拒绝，不跳过坏路径
        if not requested.is_file():
            raise HTTPException(status_code=404, detail="文件不存在")

    used: set[str] = set()  # 已占用的条目名
    # 条目名取 basename，解压后平铺无层级，手机上更好找
    entries: list[tuple[Path, str]] = [
        (path, _unique_zip_entry_name(path.name, used)) for path in resolved
    ]

    # 临时 zip 落在系统临时目录，不进入导出目录，避免污染用户产物
    descriptor, zip_name = tempfile.mkstemp(prefix=_ZIP_TMP_PREFIX, suffix=".zip")
    os.close(descriptor)  # 句柄即刻关闭，后续由 zipfile 按路径写入
    zip_path = Path(zip_name)  # 临时 zip 路径
    try:
        # 压缩是 CPU/IO 密集操作，放线程池执行，避免阻塞事件循环上的 SSE 推送
        await run_in_threadpool(_write_zip, zip_path, entries)
    except OSError as e:
        # 打包失败同样清理临时文件，异常统一转为 500 不残留
        _remove_temp_zip(zip_path)
        raise HTTPException(status_code=500, detail="打包失败") from e

    return FileResponse(
        path=str(zip_path),
        filename=f"豆包导出-{len(entries)}篇.zip",
        media_type="application/zip",
        # FileResponse 不会删除磁盘上的临时文件，必须由后台任务收尾
        background=BackgroundTask(_remove_temp_zip, zip_path),
    )


@router.get("/")
async def index(request: Request) -> Response:
    """
    渲染 index.html 主页面

    Args:
        request: FastAPI 请求对象

    Returns:
        TemplateResponse: 渲染后的 HTML 页面
    """
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "index.html")
