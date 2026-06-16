"""Tests for MinerULocalParser (MinerU API server client)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.core.ingest_and_digitize_data.parse_document.contracts import (
    ParseResult,
)
from src.core.ingest_and_digitize_data.parse_document.exceptions import MinerUAPIError
from src.core.ingest_and_digitize_data.parse_document.local.parser import (
    MinerULocalParser,
)


class TestMinerULocalParserInit:
    """Tests for constructor and properties."""

    def test_default_values(self):
        parser = MinerULocalParser()
        assert parser._api_url == "http://localhost:8001"
        assert parser._timeout == 600.0
        assert parser._backend == "vlm"
        assert parser.name == "mineru-local"

    def test_custom_values(self):
        parser = MinerULocalParser(
            api_url="http://mineru:30000",
            timeout=300.0,
            backend="pipeline",
        )
        assert parser._api_url == "http://mineru:30000"
        assert parser._timeout == 300.0
        assert parser._backend == "pipeline"


class TestMinerULocalParserParse:
    """Tests for parse() with mocked httpx."""

    @pytest.fixture
    def parser(self):
        return MinerULocalParser(api_url="http://localhost:8000")

    @pytest.mark.asyncio
    async def test_parse_single_file_success(self, parser, tmp_path):
        """Successful parse returns ParseResult with markdown and metadata."""
        pdf_file = tmp_path / "paper.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        api_response = {
            "task_id": "task-123",
            "status": "completed",
            "backend": "vlm",
            "version": "3.3.1",
            "results": {
                "paper.pdf": {
                    "md_content": "# Title\n\nAbstract\n\nSome content",
                    "content_list": [
                        {"type": "text", "text": "Title", "page_idx": 0, "bbox": [0, 0, 100, 10]},
                        {"type": "text", "text": "Abstract", "page_idx": 0, "bbox": [0, 20, 100, 30]},
                    ],
                    "images": {},
                }
            },
        }

        mock_resp = MagicMock()
        mock_resp.json.return_value = api_response
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await parser.parse(str(pdf_file))

        assert isinstance(result, ParseResult)
        assert result.parser_used == "mineru-local"
        assert "# Title" in result.full_markdown
        assert result.metadata.total_pages >= 1

    @pytest.mark.asyncio
    async def test_parse_api_error_raises_mineru_error(self, parser, tmp_path):
        """HTTP error from MinerU API raises MinerUAPIError."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        http_error = httpx.HTTPStatusError("500", request=mock_request, response=mock_response)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=http_error)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(MinerUAPIError, match="MinerU API server returned 500"):
                await parser.parse(str(pdf_file))

    @pytest.mark.asyncio
    async def test_parse_connection_error_raises_mineru_error(self, parser, tmp_path):
        """Connection failure raises MinerUAPIError."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        conn_error = httpx.ConnectError("Connection refused")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=conn_error)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(MinerUAPIError, match="Failed to connect to MinerU API"):
                await parser.parse(str(pdf_file))

    @pytest.mark.asyncio
    async def test_parse_empty_results_raises_error(self, parser, tmp_path):
        """Empty results dict in response raises MinerUAPIError."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        api_response = {
            "task_id": "task-456",
            "status": "completed",
            "results": {},
        }

        mock_resp = MagicMock()
        mock_resp.json.return_value = api_response
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(MinerUAPIError, match="No results"):
                await parser.parse(str(pdf_file))

    @pytest.mark.asyncio
    async def test_parse_file_not_found(self, parser):
        """Non-existent file raises MinerUAPIError."""
        with pytest.raises(MinerUAPIError, match="does not exist"):
            await parser.parse("/nonexistent/path/test.pdf")


class TestBuildResultFromResponse:
    """Tests for _build_result_from_response static method."""

    def test_maps_markdown_and_content_list(self):
        file_result = {
            "md_content": "# Hello\n\nWorld",
            "content_list": [
                {"type": "text", "text": "Hello", "page_idx": 0},
                {"type": "table", "table_body": "<table>...</table>", "page_idx": 1},
            ],
            "images": {},
        }
        result = MinerULocalParser._build_result_from_response("test.pdf", file_result)
        assert isinstance(result, ParseResult)
        assert result.full_markdown == "# Hello\n\nWorld"
        assert result.parser_used == "mineru-local"
        assert len(result.content_blocks) == 2

    def test_extracts_images_from_base64(self):
        file_result = {
            "md_content": "content",
            "content_list": [],
            "images": {
                "fig1.jpg": "data:image/jpeg;base64,/9j/4AAQ",
            },
        }
        result = MinerULocalParser._build_result_from_response("test.pdf", file_result)
        assert "fig1.jpg" in result.images
        assert isinstance(result.images["fig1.jpg"], bytes)

    def test_extracts_abstract_from_markdown(self):
        file_result = {
            "md_content": "# Paper\n\n## Abstract\n\nThis is the abstract text that is long enough to be valid.\n\n## Introduction",
            "content_list": [],
            "images": {},
        }
        result = MinerULocalParser._build_result_from_response("test.pdf", file_result)
        assert result.metadata.abstract_text is not None
        assert "abstract text" in result.metadata.abstract_text

    def test_infers_page_count_from_content_list(self):
        file_result = {
            "md_content": "page1\n\npage2\n\npage3",
            "content_list": [
                {"type": "text", "text": "a", "page_idx": 0},
                {"type": "text", "text": "b", "page_idx": 1},
                {"type": "text", "text": "c", "page_idx": 2},
            ],
            "images": {},
        }
        result = MinerULocalParser._build_result_from_response("test.pdf", file_result)
        assert result.metadata.total_pages == 3
        assert len(result.pages) == 3
