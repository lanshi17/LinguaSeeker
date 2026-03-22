# test mineru adapter
# batch_id=288b2e54-8df6-40f0-aa82-e695b300e384
import pytest
from src.infrastructure.adapters.mineru.mineru_adapter_impl import (
    MinerUAdapterImpl as MineruAdapter,
)
from typing import Any
from src.infrastructure.adapters.mineru.mineru_adapter_interface import (
    MinerUAdapterInterface,
)
from src.domain.impl.pdf_parser import PDFParser
import os
from icecream import ic
from datetime import datetime, timezone
from src.config import AppConfig
from loguru import logger

cfg = AppConfig().from_env()
TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "../../fixtures")
MINERU_TOKEN = (
    (cfg.mineru.api_token if cfg.mineru and cfg.mineru.api_token else "")
    or os.getenv("MINERU_API_TOKEN", "")
).strip()
HAS_MINERU_TOKEN = bool(MINERU_TOKEN)


@pytest.mark.integration
@pytest.mark.skip(reason="Requires live MinerU service credentials")
def test_mineru_adapter_parse_pdf():
    adapter = MineruAdapter()
    pdf_path = os.path.join(TEST_DATA_DIR, "test_zh.pdf")
    document_id = "test-document-id-123"
    files = [pdf_path]
    result = adapter.mineru_parse(files)
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
    document_id = "test-invalid-document-id-456"
    with pytest.raises(Exception) as exc_info:
        adapter.mineru_parse([invalid_pdf_path])
    logger.info(f"Expected exception for invalid PDF: {exc_info.value}")
