"""Tests for MinerU parser."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.core.ingest_and_digitize_data.parse_document.contracts import ParseResult
from src.core.ingest_and_digitize_data.parse_document.exceptions import (
    MinerUAPIError,
    MinerUTimeoutError,
)
from src.core.ingest_and_digitize_data.parse_document.mineru_parser import MinerUParser


class TestMinerUValidateResponse:
    def test_valid_response(self):
        data = {"total_pages": 1, "pages": [{"page_number": 1}]}
        MinerUParser._validate_response(data)  # should not raise

    def test_missing_total_pages(self):
        with pytest.raises(MinerUAPIError, match="missing 'total_pages'"):
            MinerUParser._validate_response({"pages": []})

    def test_empty_pages(self):
        with pytest.raises(MinerUAPIError, match="empty 'pages'"):
            MinerUParser._validate_response({"total_pages": 1, "pages": []})


class TestMinerUParser:
    @pytest.fixture
    def parser(self):
        return MinerUParser(
            api_token="test-token",
            poll_interval=0.1,
            max_poll_attempts=5,
        )

    def test_name(self, parser):
        assert parser.name == "mineru"

    @pytest.mark.asyncio
    async def test_parse_success(self, parser):
        mock_create_response = {
            "task_id": "abc-123",
            "state": "pending",
        }
        mock_result_response = {
            "state": "done",
            "total_pages": 2,
            "title": "Test Paper",
            "pages": [
                {"page_number": 1, "markdown": "# Page 1", "figures": [], "tables": []},
                {"page_number": 2, "markdown": "Page 2", "figures": [], "tables": []},
            ],
            "full_markdown": "# Page 1\n\nPage 2",
        }

        with patch("rust_io.net.mineru_create_task", new_callable=AsyncMock, return_value=mock_create_response), \
             patch("rust_io.net.mineru_get_result", new_callable=AsyncMock, return_value=mock_result_response):
            result = await parser.parse("https://example.com/test.pdf")

        assert isinstance(result, ParseResult)
        assert result.metadata.total_pages == 2
        assert result.parser_used == "mineru"

    @pytest.mark.asyncio
    async def test_parse_create_task_fails(self, parser):
        with patch("rust_io.net.mineru_create_task", new_callable=AsyncMock, side_effect=Exception("API Error")):
            with pytest.raises(MinerUAPIError):
                await parser.parse("https://example.com/test.pdf")

    @pytest.mark.asyncio
    async def test_parse_task_timeout(self, parser):
        mock_create_response = {"task_id": "abc-123", "state": "pending"}
        mock_pending_response = {"state": "running"}

        with patch("rust_io.net.mineru_create_task", new_callable=AsyncMock, return_value=mock_create_response), \
             patch("rust_io.net.mineru_get_result", new_callable=AsyncMock, return_value=mock_pending_response):
            with pytest.raises(MinerUTimeoutError):
                await parser.parse("https://example.com/test.pdf")

    @pytest.mark.asyncio
    async def test_parse_task_failed(self, parser):
        mock_create_response = {"task_id": "abc-123", "state": "pending"}
        mock_failed_response = {"state": "failed", "error": "Parse error"}

        with patch("rust_io.net.mineru_create_task", new_callable=AsyncMock, return_value=mock_create_response), \
             patch("rust_io.net.mineru_get_result", new_callable=AsyncMock, return_value=mock_failed_response):
            with pytest.raises(MinerUAPIError):
                await parser.parse("https://example.com/test.pdf")
