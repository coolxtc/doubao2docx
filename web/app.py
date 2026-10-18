"""FastAPI 应用工厂"""

import glob
import logging
import os
import shutil
import tempfile
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web.task_manager import _EXPORT_DIR, create_task_manager

logger = logging.getLogger("doubao.web")

# Web 包根目录
_WEB_DIR = Path(__file__).resolve().parent

# 静态资源目录
_STATIC_DIR = _WEB_DIR / "static"

# Jinja2 模板目录
_TEMPLATES_DIR = _WEB_DIR / "templates"

# 默认 Chromium 启动参数（容器内 root 运行与 /dev/shm 不足场景必需）
_DEFAULT_CHROMIUM_ARGS = "--no-sandbox,--disable-dev-shm-usage,--disable-gpu"

# 批量打包临时 zip 的匹配模式，前缀与 web/api.py 的 _ZIP_TMP_PREFIX 一致
_ZIP_TMP_GLOB = "doubao-export-zip-*.zip"

# Chromium 无头浏览器目录匹配（健康检查只确认二进制就位，不启动进程）
_BROWSER_DIR_GLOB = "chromium_headless_shell-*"


def _configure_logging() -> None:
    """
    让应用级 info 日志在容器里可见

    未挂载 handler 时 Python 仅通过 lastResort 输出 WARNING 及以上，
    导致 docker logs 里看不到启动过程与 Chromium 参数等关键信息。
    """
    app_logger = logging.getLogger("doubao")  # 应用日志根，覆盖 doubao.web.* 全部子模块
    # 重复构建应用时不叠加 handler，避免日志成倍输出
    if not app_logger.handlers:
        handler = logging.StreamHandler()  # 输出到 stderr 供容器日志采集
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        app_logger.addHandler(handler)
        app_logger.setLevel(logging.INFO)


def _configure_chromium_args() -> None:
    """
    配置 Chromium 启动参数

    读取 CHROMIUM_ARGS 环境变量（逗号分隔），未设置时使用容器默认值。
    BrowserManager 通过 src/scraper/browser.py 的 _parse_chromium_args() 消费该变量。
    """
    os.environ.setdefault("CHROMIUM_ARGS", _DEFAULT_CHROMIUM_ARGS)
    logger.info(f"Chromium 启动参数: {os.environ['CHROMIUM_ARGS']}")


def _cleanup_stale_temp_zips() -> None:
    """
    回收上次运行残留的打包临时 zip

    starlette 的 FileResponse 仅在响应正常走完时才执行后台清理任务，
    客户端中途断连会让临时 zip 留在容器可写层里长期累积，故启动时统一清扫。
    """
    pattern = str(Path(tempfile.gettempdir()) / _ZIP_TMP_GLOB)  # 临时 zip 匹配路径
    for stale_path in glob.glob(pattern):
        stale = Path(stale_path)  # 残留的临时 zip
        stale.unlink(missing_ok=True)
        logger.info(f"已清理残留的打包临时文件: {stale.name}")


router = APIRouter()


def _browser_binary_ready() -> bool:
    """
    检查 Chromium 无头浏览器二进制是否就位

    只查目录存在、不启动进程：浏览器由 fetch_and_export_batch 按批次自行启停，
    健康检查若为此拉起浏览器会让服务常驻数百 MB 内存。

    Returns:
        bool: 找到可用浏览器目录则返回 True
    """
    root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(
        Path.home() / ".cache" / "ms-playwright"
    )  # 浏览器安装根目录
    return bool(glob.glob(str(Path(root) / _BROWSER_DIR_GLOB)))


def _output_dir_writable() -> bool:
    """
    检查导出目录可写

    Returns:
        bool: 能创建并删除探针文件则返回 True
    """
    probe = _EXPORT_DIR / ".write_probe"  # 写入探针文件
    try:
        probe.touch()
        probe.unlink(missing_ok=True)
    except OSError as e:
        logger.warning(f"导出目录不可写: {_EXPORT_DIR} ({e})")
        return False
    return True


@router.get("/health")
async def health_check() -> dict[str, str]:
    """
    健康检查端点

    不启动浏览器，只核对决定导出成败的前置条件，避免为探活而常驻浏览器。

    Returns:
        dict[str, str]: status（ok/degraded）与 browser_binary、output_dir、
            pandoc 三项各自的状态
    """
    browser: str = "present" if _browser_binary_ready() else "missing"  # 浏览器二进制
    output: str = "writable" if _output_dir_writable() else "unwritable"  # 导出目录
    # pandoc 缺失只会让公式退化为 Unicode，不影响导出成功，故不参与降级判定
    pandoc: str = "available" if shutil.which("pandoc") else "missing"  # 公式转换器
    checks = {"browser_binary": browser, "output_dir": output, "pandoc": pandoc}
    ok = browser == "present" and output == "writable"  # 关键前置是否齐备
    if not ok:
        logger.warning(f"健康检查降级: {checks}")
    return {"status": "ok" if ok else "degraded", **checks}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理

    启动阶段：配置 Chromium 参数 → 回收残留临时包 → 准备导出目录。
    浏览器不在此阶段创建——导出由 fetch_and_export_batch 按批次自行启停，
    在此常驻一个实例只会白占数百 MB 内存且没有任何请求会复用它。

    不注册 SIGTERM 处理器：uvicorn 自身捕获信号后驱动本生命周期退出，
    覆盖它会让容器收不到退出指令、最终被 SIGKILL。

    Args:
        app: FastAPI 应用实例

    Yields:
        None: 交还应用运行阶段控制权
    """
    logger.info("Web 应用启动")
    _configure_chromium_args()
    _cleanup_stale_temp_zips()

    # 挂载卷首次部署时目录为空，DocNamer 读写 link_index.json 会直接报错
    _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    (_EXPORT_DIR / "export").mkdir(parents=True, exist_ok=True)

    yield
    logger.info("Web 应用已关闭")


def create_app() -> FastAPI:
    """
    创建 FastAPI 应用实例

    Returns:
        FastAPI: 配置完成的 FastAPI 应用
    """
    app = FastAPI(
        title="豆包聊天记录导出",
        description="豆包聊天记录导出 Web 服务",
        version="0.1.0",
        lifespan=lifespan,
    )
    # 尽早挂载 handler，否则本函数与生命周期内的 info 日志会被静默丢弃
    _configure_logging()
    logger.info("开始构建 FastAPI 应用")

    # 前端资源可能尚未就位，先建目录避免挂载报错
    _STATIC_DIR.mkdir(parents=True, exist_ok=True)
    _TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
    app.state.templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

    manager = create_task_manager()
    app.state.task_manager = manager
    logger.info(f"ExportTaskManager 初始化成功 (max_concurrent={manager.max_concurrent})")

    app.include_router(router)

    # 延迟导入避免 web.api 与 web.app 的循环依赖
    from web import api
    app.include_router(api.router)
    logger.info("API 路由注册成功")

    return app
