"""Tests for parse_document service."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.ingest_and_digitize_data.parse_document.contracts import (
    DocumentMetadata,
    PageContent,
    ParseResult,
)
from src.core.ingest_and_digitize_data.parse_document.service import ParseDocumentService


class TestParseDocumentService:
    @pytest.fixture
    def service(self):
        return ParseDocumentService(
            mineru_api_token="test-token",
            paddle_model_path="/models/paddleocr",
        )

    @pytest.mark.asyncio
    async def test_parse(self, service):
        mock_result = ParseResult(
            metadata=DocumentMetadata(total_pages=1, title="Test"),
            pages=[PageContent(page_number=1, markdown="# Test")],
            parser_used="mineru",
        )

        with patch.object(service._factory, "parse", new_callable=AsyncMock, return_value=mock_result):
            result = await service.parse("https://example.com/test.pdf")

        assert result.parser_used == "mineru"

    @pytest.mark.asyncio
    async def test_parse_and_save(self, service, tmp_path):
        output_dir = str(tmp_path / "output")

        mock_result = ParseResult(
            metadata=DocumentMetadata(total_pages=1, title="Test"),
            pages=[PageContent(page_number=1, markdown="# Test")],
            parser_used="mineru",
        )

        with patch.object(service._factory, "parse", new_callable=AsyncMock, return_value=mock_result), \
             patch("rust_io.files.File") as mock_file_cls:
            mock_file_instance = MagicMock()
            mock_file_cls.return_value = mock_file_instance

            result = await service.parse_and_save("https://example.com/test.pdf", output_dir)

        assert result.parser_used == "mineru"
        assert mock_file_instance.write.call_count == 2  # markdown + metadata JSON

    @pytest.mark.asyncio
    async def test_check_duplicate(self, service):
        with patch("rust_io.files.check_duplicate", return_value={"hash": "abc123", "is_duplicate": True}):
            result = await service.check_duplicate("/tmp/test.pdf", ["abc123"])

        assert result["is_duplicate"] is True
