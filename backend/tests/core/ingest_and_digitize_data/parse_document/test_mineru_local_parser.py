"""Tests for MinerU local parser."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.core.ingest_and_digitize_data.parse_document.contracts import (
    PageContent,
    ParseResult,
)
from src.core.ingest_and_digitize_data.parse_document.exceptions import MinerUAPIError
from src.core.ingest_and_digitize_data.parse_document.mineru_local_parser import (
    MinerULocalParser,
)


class TestParsePageResponse:
    """Tests for MinerULocalParser._parse_page_response static method."""

    def test_vlm_format_with_pages(self):
        data = {
            "full_markdown": "# Title\n\nBody",
            "pages": [
                {
                    "page_number": 1,
                    "markdown": "# Title\n\nBody",
                    "figures": [{"index": 1, "caption": "Fig 1"}],
                    "tables": [{"index": 1, "headers": ["A", "B"], "rows": [["1", "2"]]}],
                }
            ],
        }
        result = MinerULocalParser._parse_page_response(1, data)

        assert isinstance(result, PageContent)
        assert result.page_number == 1
        assert result.markdown == "# Title\n\nBody"
        assert len(result.figures) == 1
        assert result.figures[0].caption == "Fig 1"
        assert len(result.tables) == 1
        assert result.tables[0].headers == ["A", "B"]

    def test_vlm_format_full_markdown_only(self):
        data = {"full_markdown": "Page content here"}
        result = MinerULocalParser._parse_page_response(2, data)

        assert result.page_number == 2
        assert result.markdown == "Page content here"
        assert result.figures == []
        assert result.tables == []

    def test_openai_chat_completions_format(self):
        data = {
            "choices": [
                {"message": {"content": "Extracted text from VLM"}}
            ]
        }
        result = MinerULocalParser._parse_page_response(1, data)

        assert result.markdown == "Extracted text from VLM"
        assert result.figures == []
        assert result.tables == []

    def test_empty_response_returns_empty_page(self):
        data = {}
        result = MinerULocalParser._parse_page_response(1, data)

        assert result.page_number == 1
        assert result.markdown == ""
        assert result.figures == []
        assert result.tables == []

    def test_pages_fallback_to_full_markdown(self):
        """When pages[0] has no markdown key, falls back to full_markdown."""
        data = {
            "full_markdown": "Fallback content",
            "pages": [{"figures": [], "tables": []}],
        }
        result = MinerULocalParser._parse_page_response(1, data)

        assert result.markdown == "Fallback content"

    def test_openai_format_empty_choices(self):
        data = {"choices": []}
        result = MinerULocalParser._parse_page_response(1, data)

        assert result.markdown == ""

    def test_figures_and_tables_parsed_from_page(self):
        data = {
            "pages": [
                {
                    "markdown": "content",
                    "figures": [
                        {"index": 1, "caption": "First"},
                        {"index": 2, "caption": "Second"},
                    ],
                    "tables": [
                        {"index": 1, "headers": ["X"], "rows": [["val"]]},
                    ],
                }
            ],
        }
        result = MinerULocalParser._parse_page_response(3, data)

        assert len(result.figures) == 2
        assert result.figures[0].page == 3
        assert result.figures[1].caption == "Second"
        assert len(result.tables) == 1
        assert result.tables[0].page == 3


class TestMinerULocalParserParse:
    """Tests for MinerULocalParser.parse with mocked httpx and PDF conversion."""

    @pytest.fixture
    def parser(self):
        return MinerULocalParser(model_server_url="http://localhost:8001")

    @pytest.mark.asyncio
    async def test_parse_single_page(self, parser):
        mock_image = MagicMock()
        vlm_response = {
            "full_markdown": "# Hello World",
            "pages": [{"page_number": 1, "markdown": "# Hello World", "figures": [], "tables": []}],
        }

        with patch(
            "src.core.ingest_and_digitize_data.parse_document.mineru_local_parser._pdf_to_images",
            return_value=[mock_image],
        ), patch(
            "src.core.ingest_and_digitize_data.parse_document.mineru_local_parser._image_to_base64",
            return_value="base64data",
        ):
            mock_resp = MagicMock()
            mock_resp.json.return_value = vlm_response
            mock_resp.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)

            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await parser.parse("/tmp/test.pdf")

        assert isinstance(result, ParseResult)
        assert result.metadata.total_pages == 1
        assert len(result.pages) == 1
        assert result.full_markdown == "# Hello World"
        assert result.parser_used == "mineru"

    @pytest.mark.asyncio
    async def test_parse_multi_page_aggregation(self, parser):
        mock_image = MagicMock()
        page1_resp = {
            "full_markdown": "Page 1 content",
            "pages": [{"page_number": 1, "markdown": "Page 1 content"}],
        }
        page2_resp = {
            "full_markdown": "Page 2 content",
            "pages": [{"page_number": 2, "markdown": "Page 2 content"}],
        }

        with patch(
            "src.core.ingest_and_digitize_data.parse_document.mineru_local_parser._pdf_to_images",
            return_value=[mock_image, mock_image],
        ), patch(
            "src.core.ingest_and_digitize_data.parse_document.mineru_local_parser._image_to_base64",
            return_value="base64data",
        ):
            mock_resp1 = MagicMock()
            mock_resp1.json.return_value = page1_resp
            mock_resp1.raise_for_status = MagicMock()

            mock_resp2 = MagicMock()
            mock_resp2.json.return_value = page2_resp
            mock_resp2.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=[mock_resp1, mock_resp2])
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)

            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await parser.parse("/tmp/test.pdf")

        assert result.metadata.total_pages == 2
        assert len(result.pages) == 2
        assert "Page 1 content" in result.full_markdown
        assert "Page 2 content" in result.full_markdown

    @pytest.mark.asyncio
    async def test_parse_http_status_error(self, parser):
        mock_image = MagicMock()

        with patch(
            "src.core.ingest_and_digitize_data.parse_document.mineru_local_parser._pdf_to_images",
            return_value=[mock_image],
        ), patch(
            "src.core.ingest_and_digitize_data.parse_document.mineru_local_parser._image_to_base64",
            return_value="base64data",
        ):
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
                with pytest.raises(MinerUAPIError, match="Model-server returned 500"):
                    await parser.parse("/tmp/test.pdf")

    @pytest.mark.asyncio
    async def test_parse_request_error(self, parser):
        mock_image = MagicMock()

        with patch(
            "src.core.ingest_and_digitize_data.parse_document.mineru_local_parser._pdf_to_images",
            return_value=[mock_image],
        ), patch(
            "src.core.ingest_and_digitize_data.parse_document.mineru_local_parser._image_to_base64",
            return_value="base64data",
        ):
            req_error = httpx.ConnectError("Connection refused")

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=req_error)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)

            with patch("httpx.AsyncClient", return_value=mock_client):
                with pytest.raises(MinerUAPIError, match="Request to model-server failed"):
                    await parser.parse("/tmp/test.pdf")

    def test_name_property(self, parser):
        assert parser.name == "mineru"
