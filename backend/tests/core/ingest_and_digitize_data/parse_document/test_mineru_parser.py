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
            "code": 0,
            "data": {"task_id": "abc-123"},
            "msg": "ok",
        }
        mock_poll_response = {
            "code": 0,
            "data": {
                "state": "done",
                "full_zip_url": "https://example.com/result.zip",
            },
            "msg": "ok",
        }

        with patch("rust_io.net.mineru_create_task", new_callable=AsyncMock, return_value=mock_create_response), \
             patch("rust_io.net.mineru_get_result", new_callable=AsyncMock, return_value=mock_poll_response), \
             patch.object(parser, "_download_and_parse_zip", new_callable=AsyncMock) as mock_download:
            mock_download.return_value = {
                "state": "done",
                "total_pages": 2,
                "title": "Test Paper",
                "authors": [],
                "abstract": None,
                "pages": [
                    {"page_number": 1, "markdown": "# Page 1", "figures": [], "tables": []},
                    {"page_number": 2, "markdown": "Page 2", "figures": [], "tables": []},
                ],
                "full_markdown": "# Page 1\n\nPage 2",
            }
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
    async def test_parse_no_task_id(self, parser):
        mock_create_response = {
            "code": 0,
            "data": {},
            "msg": "ok",
        }

        with patch("rust_io.net.mineru_create_task", new_callable=AsyncMock, return_value=mock_create_response):
            with pytest.raises(MinerUAPIError, match="No task_id"):
                await parser.parse("https://example.com/test.pdf")

    @pytest.mark.asyncio
    async def test_parse_task_timeout(self, parser):
        mock_create_response = {
            "code": 0,
            "data": {"task_id": "abc-123"},
            "msg": "ok",
        }
        mock_pending_response = {
            "code": 0,
            "data": {"state": "running"},
            "msg": "ok",
        }

        with patch("rust_io.net.mineru_create_task", new_callable=AsyncMock, return_value=mock_create_response), \
             patch("rust_io.net.mineru_get_result", new_callable=AsyncMock, return_value=mock_pending_response):
            with pytest.raises(MinerUTimeoutError):
                await parser.parse("https://example.com/test.pdf")

    @pytest.mark.asyncio
    async def test_parse_task_failed(self, parser):
        mock_create_response = {
            "code": 0,
            "data": {"task_id": "abc-123"},
            "msg": "ok",
        }
        mock_failed_response = {
            "code": 0,
            "data": {"state": "failed", "err_msg": "Parse error"},
            "msg": "ok",
        }

        with patch("rust_io.net.mineru_create_task", new_callable=AsyncMock, return_value=mock_create_response), \
             patch("rust_io.net.mineru_get_result", new_callable=AsyncMock, return_value=mock_failed_response):
            with pytest.raises(MinerUAPIError, match="Task failed"):
                await parser.parse("https://example.com/test.pdf")
