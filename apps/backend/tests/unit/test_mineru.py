import os
from pathlib import Path

import pytest
from loguru import logger

from src.domain.mineru.component import MinerUComponent
from src.domain.models import MinerURequest
from src.utils import file_utils


mineru = MinerUComponent()


def _disable_proxies() -> None:
    os.environ.pop("http_proxy", None)
    os.environ.pop("https_proxy", None)
    os.environ.pop("all_proxy", None)


def _assert_assets_exist(folder_path: str) -> None:
    all_files = file_utils.get_all_files_in_directory(folder_path)
    md_files = [f for f in all_files if f.endswith(".md")]
    image_files = [
        f
        for f in all_files
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp"))
    ]
    assert len(md_files) > 0, "未找到.md文件"
    assert len(image_files) > 0, "未找到图片文件"
    logger.debug("找到的.md文件: {}", md_files)
    logger.debug("找到的图片文件: {}", image_files)


def _resolve_path(relative_path: str) -> Path:
    return Path(os.getcwd()) / relative_path


@pytest.mark.unit
def test_minerU_pipeline_on_sample_pdf() -> None:
    _disable_proxies()
    file_path = _resolve_path(
        "knowledge_docs/Richards 等 - 2015 - Standards and guidelines for the interpretation of sequence variants a joint consensus recommendati.pdf"
    )
    if not file_path.exists():
        pytest.skip("测试文件不存在，跳过 MinerU 解析测试")

    response = mineru.minerU_pipeline(MinerURequest(file_paths=[str(file_path)]))
    assert response is not None
    assert response.folder_path is not None
    _assert_assets_exist(response.folder_path)
    logger.success("minerU_pipeline 解析测试通过。")


@pytest.mark.unit
def test_minerU_pipeline_on_nonexistent_file() -> None:
    _disable_proxies()
    file_path = _resolve_path("demo_pdf/nonexistent_file.pdf")
    response = mineru.minerU_pipeline(MinerURequest(file_paths=[str(file_path)]))
    assert response is None, "预期返回 None 但实际返回了响应"
    logger.success("minerU_pipeline 处理不存在文件测试通过。")


@pytest.mark.unit
def test_minerU_pipeline_on_empty_file_list() -> None:
    _disable_proxies()
    response = mineru.minerU_pipeline(MinerURequest(file_paths=[]))
    assert response is None, "预期返回 None 但实际返回了响应"
    logger.success("minerU_pipeline 处理空文件列表测试通过。")


@pytest.mark.unit
def test_minerU_pipeline_on_unsupported_file_format() -> None:
    _disable_proxies()
    file_path = _resolve_path("demo_pdf/unsupported_file.txt")
    if not file_path.exists():
        pytest.skip("测试文件不存在，跳过不支持格式测试")

    response = mineru.minerU_pipeline(MinerURequest(file_paths=[str(file_path)]))
    assert response is None, "预期返回 None 但实际返回了响应"
    logger.success("minerU_pipeline 处理非支持格式文件测试通过。")


@pytest.mark.unit
def test_minerU_pipeline_on_batch_files() -> None:
    _disable_proxies()
    file1 = _resolve_path("demo_pdf/test_ja01.pdf")
    file2 = _resolve_path("demo_pdf/test_de01.pdf")
    if not file1.exists() or not file2.exists():
        pytest.skip("测试文件不存在，跳过批量解析测试")

    response = mineru.minerU_pipeline(MinerURequest(file_paths=[str(file1), str(file2)]))
    assert response is not None
    assert response.folder_path is not None
    _assert_assets_exist(response.folder_path)
    logger.success("minerU_pipeline 批量文件解析测试通过。")