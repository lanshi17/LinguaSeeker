"""Integration tests for parse_document module.

These tests require actual services (MinerU API or PaddleOCR model).
Mark with @pytest.mark.integration to skip in CI.
"""
from __future__ import annotations

import os

import pytest

from src.core.ingest_and_digitize_data.parse_document import (
    ParseDocumentService,
    ParseResult,
)


@pytest.fixture
def sample_pdf_url():
    """PDF URL from environment variable, skip if not set."""
    url = os.environ.get("TEST_PDF_URL", "")
    if not url:
        pytest.skip("TEST_PDF_URL not set")
    return url


@pytest.mark.integration
class TestParseDocumentIntegration:
    """Integration tests requiring actual services."""

    @pytest.fixture
    def service(self):
        from src.core.config import get_config

        cfg = get_config()
        return ParseDocumentService(
            mineru_api_token=cfg.mineru.api_token,
            paddle_model_path=cfg.paddle.model_path,
        )

    @pytest.mark.asyncio
    async def test_parse_sample_pdf(self, service, sample_pdf_url):
        """Test parsing a sample PDF file via URL."""
        result = await service.parse(sample_pdf_url)

        assert isinstance(result, ParseResult)
        assert result.metadata.total_pages > 0
        assert len(result.pages) > 0
        assert result.full_markdown
        assert result.parser_used in ("mineru", "paddleocr")

    @pytest.mark.asyncio
    async def test_parse_and_save_output(self, service, sample_pdf_url, tmp_path):
        """Test parsing and saving output files."""
        await service.parse_and_save(sample_pdf_url, str(tmp_path))

        assert (tmp_path / "output.md").exists()
        assert (tmp_path / "metadata.json").exists()
