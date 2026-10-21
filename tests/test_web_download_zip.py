"""
web/api.py 批量下载 zip 端点测试

覆盖：正常打包、目录穿越（403）、文件缺失（404）、数量保护（422）、
同名 basename 去重、临时文件后台清理。
"""

import zipfile
from pathlib import Path
from urllib.parse import unquote

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from web import api
from web.api import download_zip


def write_docx(root: Path, relative: str, payload: bytes) -> Path:
    """
    在导出根目录下写入一个假 docx 文件

    Args:
        root: 导出根目录
        relative: 相对根目录的路径（含日期子目录）
        payload: 文件内容

    Returns:
        Path: 写入后的文件绝对路径
    """
    target = root / relative  # 目标文件路径
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return target


@pytest.fixture(name="export_root")
def export_root_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    构造隔离的导出根目录并替换 api._DOWNLOAD_ROOT

    Args:
        tmp_path: pytest 临时目录
        monkeypatch: pytest 打桩工具

    Returns:
        Path: 生效的导出根目录
    """
    root = (tmp_path / "export").resolve()  # 隔离的导出根目录
    root.mkdir(parents=True)
    monkeypatch.setattr(api, "_DOWNLOAD_ROOT", root)
    return root


class TestDownloadZipSuccess:
    """正常打包路径的行为"""

    @pytest.mark.asyncio
    async def test_returns_zip_with_flat_basenames(self, export_root: Path) -> None:
        """zip 条目名为 basename 平铺，数量与请求一致且不解压即损坏"""
        write_docx(export_root, "261017/261017-1 示例会话标题一.docx", b"docx-A")
        write_docx(export_root, "261017/261017-2 另一个会话.docx", b"docx-B")
        response = await download_zip(paths=[
            "261017/261017-1 示例会话标题一.docx",
            "261017/261017-2 另一个会话.docx",
        ])
        assert response.media_type == "application/zip"
        with zipfile.ZipFile(response.path) as archive:
            assert archive.namelist() == ["261017-1 示例会话标题一.docx", "261017-2 另一个会话.docx"]
            assert archive.testzip() is None
            assert archive.read("261017-1 示例会话标题一.docx") == b"docx-A"
            # deflate 压缩算法，与约束一致
            assert all(info.compress_type == zipfile.ZIP_DEFLATED for info in archive.infolist())
        await response.background()

    @pytest.mark.asyncio
    async def test_attachment_header_rfc5987(self, export_root: Path) -> None:
        """响应头为 attachment 且中文 zip 名走 RFC 5987 编码"""
        write_docx(export_root, "261017/a.docx", b"A")
        write_docx(export_root, "261018/b.docx", b"B")
        response = await download_zip(paths=["261017/a.docx", "261018/b.docx"])
        disposition = response.headers["content-disposition"]
        assert disposition.startswith("attachment; filename*=utf-8''")
        assert unquote(disposition.split("''", 1)[1]) == "豆包导出-2篇.zip"
        await response.background()

    @pytest.mark.asyncio
    async def test_duplicate_basenames_are_deduped(self, export_root: Path) -> None:
        """不同目录下的同名 basename 追加序号而不是互相覆盖"""
        write_docx(export_root, "261017/同名.docx", b"one")
        write_docx(export_root, "261018/同名.docx", b"two")
        write_docx(export_root, "261019/同名.docx", b"three")
        response = await download_zip(paths=["261017/同名.docx", "261018/同名.docx", "261019/同名.docx"])
        with zipfile.ZipFile(response.path) as archive:
            assert archive.namelist() == ["同名.docx", "同名 (2).docx", "同名 (3).docx"]
            assert archive.read("同名 (2).docx") == b"two"
        # 去重后的数量仍等于请求数量
        assert unquote(response.headers["content-disposition"].split("''", 1)[1]) == "豆包导出-3篇.zip"
        await response.background()


class TestDownloadZipCleanup:
    """临时文件清理"""

    @pytest.mark.asyncio
    async def test_background_task_deletes_temp_zip(self, export_root: Path) -> None:
        """后台任务执行后临时 zip 从磁盘消失"""
        write_docx(export_root, "261017/a.docx", b"A")
        response = await download_zip(paths=["261017/a.docx"])
        temp_zip = Path(response.path)  # FileResponse 指向的临时 zip
        assert temp_zip.is_file()
        await response.background()
        assert not temp_zip.exists()

    @pytest.mark.asyncio
    async def test_temp_zip_not_inside_export_root(self, export_root: Path) -> None:
        """临时 zip 不落在导出目录内，避免污染用户产物"""
        write_docx(export_root, "261017/a.docx", b"A")
        response = await download_zip(paths=["261017/a.docx"])
        temp_zip = Path(response.path)  # FileResponse 指向的临时 zip
        assert not temp_zip.is_relative_to(export_root)
        await response.background()
        assert list(export_root.rglob("*.zip")) == []


class TestDownloadZipRejection:
    """校验分支"""

    @pytest.mark.asyncio
    async def test_parent_traversal_rejected(self, export_root: Path) -> None:
        """../ 形式穿越到根目录外返回 403"""
        with pytest.raises(HTTPException) as excinfo:
            await download_zip(paths=["261017/../../etc/passwd"])
        assert excinfo.value.status_code == 403

    @pytest.mark.asyncio
    async def test_symlink_escape_rejected(self, export_root: Path, tmp_path: Path) -> None:
        """导出目录内指向外部的软链接同样返回 403"""
        outside = tmp_path / "outside.docx"  # 根目录之外的真实文件
        outside.write_bytes(b"secret")
        link = export_root / "261017" / "link.docx"  # 导出目录内的软链接
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(outside)
        with pytest.raises(HTTPException) as excinfo:
            await download_zip(paths=["261017/link.docx"])
        assert excinfo.value.status_code == 403

    @pytest.mark.asyncio
    async def test_absolute_path_rejected(self, export_root: Path) -> None:
        """绝对路径查询参数返回 403"""
        with pytest.raises(HTTPException) as excinfo:
            await download_zip(paths=["/etc/hosts"])
        assert excinfo.value.status_code == 403

    @pytest.mark.asyncio
    async def test_traversal_wins_over_missing_file(self, export_root: Path) -> None:
        """穿越路径优先于缺失路径被拒绝，不做部分打包"""
        write_docx(export_root, "261017/a.docx", b"A")
        with pytest.raises(HTTPException) as excinfo:
            await download_zip(paths=["261017/a.docx", "nope.docx", "../../etc/passwd"])
        assert excinfo.value.status_code == 403

    @pytest.mark.asyncio
    async def test_missing_file_rejected(self, export_root: Path) -> None:
        """任一文件不存在时整体 404"""
        write_docx(export_root, "261017/a.docx", b"A")
        with pytest.raises(HTTPException) as excinfo:
            await download_zip(paths=["261017/a.docx", "261017/ghost.docx"])
        assert excinfo.value.status_code == 404

    @pytest.mark.asyncio
    async def test_directory_path_rejected(self, export_root: Path) -> None:
        """指向目录（非文件）时返回 404"""
        (export_root / "261017").mkdir()
        with pytest.raises(HTTPException) as excinfo:
            await download_zip(paths=["261017"])
        assert excinfo.value.status_code == 404

    @pytest.mark.asyncio
    async def test_empty_paths_rejected(self, export_root: Path) -> None:
        """空 paths 列表返回 422"""
        with pytest.raises(HTTPException) as excinfo:
            await download_zip(paths=[])
        assert excinfo.value.status_code == 422

    @pytest.mark.asyncio
    async def test_too_many_paths_rejected(self, export_root: Path) -> None:
        """超过 50 个 paths 返回 422 且不读磁盘"""
        write_docx(export_root, "261017/a.docx", b"A")
        too_many = ["261017/a.docx"] * (api._ZIP_MAX_FILES + 1)  # 超限的请求
        with pytest.raises(HTTPException) as excinfo:
            await download_zip(paths=too_many)
        assert excinfo.value.status_code == 422

    @pytest.mark.asyncio
    async def test_max_paths_allowed(self, export_root: Path) -> None:
        """恰好 50 个 paths 允许打包"""
        paths = [f"261017/f{i}.docx" for i in range(api._ZIP_MAX_FILES)]  # 达到上限的请求
        for path in paths:
            write_docx(export_root, path, b"x")
        response = await download_zip(paths=paths)
        with zipfile.ZipFile(response.path) as archive:
            assert len(archive.namelist()) == api._ZIP_MAX_FILES
        await response.background()


@pytest.fixture(name="client")
def client_fixture() -> TestClient:
    """
    仅挂载 api.router 的 TestClient（不触发 lifespan，避免启动浏览器池）

    Returns:
        TestClient: HTTP 层测试客户端
    """
    app = FastAPI()  # 独立测试应用
    app.include_router(api.router)
    return TestClient(app)


class TestDownloadZipHttpContract:
    """HTTP 层契约：重复 paths 参数与 URL 编码"""

    def test_repeated_encoded_query_params(self, client: TestClient, export_root: Path) -> None:
        """中文加空格的重复 paths 参数能被正确解码并打包"""
        write_docx(export_root, "261017/261017-1 示例会话标题一.docx", b"A")
        write_docx(export_root, "261017/261017-2 示例会话标题二.docx", b"B")
        response = client.get("/api/download-zip", params={
            "paths": ["261017/261017-1 示例会话标题一.docx", "261017/261017-2 示例会话标题二.docx"],
        })
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert response.headers["content-disposition"].startswith("attachment; filename*=utf-8''")
        assert len(response.content) > 0

    def test_missing_paths_query_is_422(self, client: TestClient, export_root: Path) -> None:
        """完全不带 paths 参数时返回 422"""
        response = client.get("/api/download-zip")
        assert response.status_code == 422

    def test_traversal_query_is_403(self, client: TestClient, export_root: Path) -> None:
        """URL 编码的穿越参数在 HTTP 层返回 403"""
        response = client.get("/api/download-zip", params={"paths": ["../../etc/passwd"]})
        assert response.status_code == 403

    def test_missing_file_query_is_404(self, client: TestClient, export_root: Path) -> None:
        """不存在的文件在 HTTP 层返回 404"""
        response = client.get("/api/download-zip", params={"paths": ["261017/ghost.docx"]})
        assert response.status_code == 404
