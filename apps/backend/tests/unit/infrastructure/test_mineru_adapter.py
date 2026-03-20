# test mineru adapter
# batch_id=288b2e54-8df6-40f0-aa82-e695b300e384
import os

import pytest
from icecream import ic
from loguru import logger

from src.infrastructure.adapters.mineru.mineru_adapter_impl import (
    MinerUAdapterImpl as MineruAdapter,
)

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "../../fixtures")


def test_mineru_adapter_parse_pdf():
    adapter = MineruAdapter()
    pdf_path = os.path.join(TEST_DATA_DIR, "test_zh.pdf")
    result = adapter.mineru_parse([pdf_path])
    logger.info(f"MinerU parse result: {result}")
    ic(result)
    assert isinstance(result, dict)
    assert result.get("file_id") is not None
    assert result.get("file_name") == "test_zh.pdf"
    assert result.get("state") in ["processing", "completed", "failed"]
    assert result.get("full_zip_url") is not None


def test_mineru_adapter_parse_invalid_pdf():
    adapter = MineruAdapter()
    invalid_pdf_path = os.path.join(TEST_DATA_DIR, "invalid_file.pdf")
    with pytest.raises(Exception) as exc_info:
        adapter.mineru_parse([invalid_pdf_path])
    logger.info(f"Expected exception for invalid PDF: {exc_info.value}")
