"""Tests for MinerU local parser."""
from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.core.ingest_and_digitize_data.parse_document.contracts import ParseResult
from src.core.ingest_and_digitize_data.parse_document.exceptions import MinerUAPIError
from src.core.ingest_and_digitize_data.parse_document.local.parser import (
    MinerULocalParser,
)


def _file_parse_response(
    md_content: str = "",
    content_list: list[dict] | None = None,
    images: dict[str, str] | None = None,
    filename: str = "test.pdf",
) -> dict:
    """Build a mock ``/file_parse`` response dict."""
    file_result: dict = {}
    if md_content is not None:
        file_result["md_content"] = md_content
    if content_list is not None:
        file_result["content_list"] = content_list
    if images is not None:
        file_result["images"] = images
    return {
        "task_id": "",
        "status": "completed",
        "backend": "vlm",
        "version": "",
        "results": {filename: file_result},
    }


class TestParseFileParseResponse:
    """Tests for MinerULocalParser._parse_file_parse_response static method."""

    def test_single_page_from_content_list(self):
        data = _file_parse_response(
            md_content="# Hello World",
            content_list=[
                {"type": "text", "text": "# Hello World", "page_idx": 0, "bbox": [0, 0, 0, 0]},
            ],
        )
        result = MinerULocalParser._parse_file_parse_response(data)

        assert isinstance(result, ParseResult)
        assert result.metadata.total_pages == 1
        assert len(result.pages) == 1
        assert result.pages[0].page_number == 1
        assert result.pages[0].markdown == "# Hello World"
        assert result.full_markdown == "# Hello World"
        assert result.parser_used == "mineru-local"

    def test_multi_page_grouped_by_page_idx(self):
        data = _file_parse_response(
            md_content="Para A\n\nPara C\n\nPara B",
            content_list=[
                {"type": "text", "text": "Para A", "page_idx": 0, "bbox": [0, 0, 0, 0]},
                {"type": "text", "text": "Para B", "page_idx": 1, "bbox": [0, 0, 0, 0]},
                {"type": "text", "text": "Para C", "page_idx": 0, "bbox": [0, 0, 0, 0]},
            ],
        )
        result = MinerULocalParser._parse_file_parse_response(data)

        assert result.metadata.total_pages == 2
        assert len(result.pages) == 2
        assert result.pages[0].page_number == 1
        assert "Para A" in result.pages[0].markdown
        assert "Para C" in result.pages[0].markdown
        assert result.pages[1].page_number == 2
        assert result.pages[1].markdown == "Para B"

    def test_empty_content_list_falls_back_to_md(self):
        data = _file_parse_response(
            md_content="Full document markdown",
            content_list=[],
        )
        result = MinerULocalParser._parse_file_parse_response(data)

        assert len(result.pages) == 1
        assert result.pages[0].page_number == 1
        assert result.pages[0].markdown == "Full document markdown"

    def test_missing_content_list_falls_back_to_md(self):
        data = _file_parse_response(md_content="No content_list key at all")
        result = MinerULocalParser._parse_file_parse_response(data)

        assert len(result.pages) == 1
        assert result.pages[0].markdown == "No content_list key at all"

    def test_all_empty_text_blocks_falls_back_to_md(self):
        data = _file_parse_response(
            md_content="Fallback markdown",
            content_list=[
                {"type": "image", "text": "", "page_idx": 0, "bbox": [0, 0, 0, 0]},
            ],
        )
        result = MinerULocalParser._parse_file_parse_response(data)

        assert len(result.pages) == 1
        assert result.pages[0].markdown == "Fallback markdown"

    def test_empty_results_raises_error(self):
        with pytest.raises(MinerUAPIError, match="empty results"):
            MinerULocalParser._parse_file_parse_response({"results": {}})

    def test_missing_results_raises_error(self):
        with pytest.raises(MinerUAPIError, match="empty results"):
            MinerULocalParser._parse_file_parse_response({})

    def test_images_decoded_from_data_uri(self):
        raw = b"\x89PNG fake bytes"
        b64 = base64.b64encode(raw).decode()
        data = _file_parse_response(
            md_content="text",
            content_list=[{"type": "text", "text": "text", "page_idx": 0}],
            images={"img_0_0.png": f"data:image/png;base64,{b64}"},
        )
        result = MinerULocalParser._parse_file_parse_response(data)

        assert "img_0_0.png" in result.images
        assert result.images["img_0_0.png"] == raw

    def test_multiple_images_decoded(self):
        raw1 = b"\x89PNG img1"
        raw2 = b"\x89PNG img2"
        data = _file_parse_response(
            md_content="text",
            content_list=[{"type": "text", "text": "text", "page_idx": 0}],
            images={
                "img_0_0.png": f"data:image/png;base64,{base64.b64encode(raw1).decode()}",
                "img_1_0.jpg": f"data:image/jpeg;base64,{base64.b64encode(raw2).decode()}",
            },
        )
        result = MinerULocalParser._parse_file_parse_response(data)

        assert len(result.images) == 2
        assert result.images["img_0_0.png"] == raw1
        assert result.images["img_1_0.jpg"] == raw2

    def test_content_blocks_populated(self):
        content_list = [
            {"type": "text", "text": "block1", "page_idx": 0, "bbox": [1, 2, 3, 4]},
            {"type": "text", "text": "block2", "page_idx": 1, "bbox": [5, 6, 7, 8]},
        ]
        data = _file_parse_response(md_content="block1\n\nblock2", content_list=content_list)
        result = MinerULocalParser._parse_file_parse_response(data)

        assert result.content_blocks == content_list

    def test_abstract_extracted_from_markdown(self):
        md = (
            "# Paper Title\n\n"
            "Abstract\n"
            "This is a long abstract text that exceeds thirty characters.\n\n"
            "Introduction\n"
            "The body of the paper."
        )
        data = _file_parse_response(
            md_content=md,
            content_list=[{"type": "text", "text": md, "page_idx": 0}],
        )
        result = MinerULocalParser._parse_file_parse_response(data)

        assert result.metadata.abstract_text is not None
        assert "long abstract text" in result.metadata.abstract_text

    def test_no_images_returns_empty_dict(self):
        data = _file_parse_response(
            md_content="text",
            content_list=[{"type": "text", "text": "text", "page_idx": 0}],
        )
        result = MinerULocalParser._parse_file_parse_response(data)

        assert result.images == {}

    def test_non_contiguous_page_indices(self):
        """Page indices don't have to be contiguous (e.g. skipped pages)."""
        data = _file_parse_response(
            md_content="Page 0\n\nPage 2",
            content_list=[
                {"type": "text", "text": "Page 0", "page_idx": 0},
                {"type": "text", "text": "Page 2", "page_idx": 2},
            ],
        )
        result = MinerULocalParser._parse_file_parse_response(data)

        assert result.metadata.total_pages == 2
        assert result.pages[0].page_number == 1
        assert result.pages[1].page_number == 3


class TestMinerULocalParserParse:
    """Tests for MinerULocalParser.parse with mocked httpx and file I/O."""

    @pytest.fixture
    def parser(self):
        return MinerULocalParser(parse_url="http://localhost:8001")

    @pytest.mark.asyncio
    async def test_parse_single_page(self, parser):
        response = _file_parse_response(
            md_content="# Hello World",
            content_list=[{"type": "text", "text": "# Hello World", "page_idx": 0}],
        )

        mock_resp = MagicMock()
        mock_resp.json.return_value = response
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pathlib.Path.read_bytes", return_value=b"%PDF fake"), patch(
            "httpx.AsyncClient", return_value=mock_client
        ):
            result = await parser.parse("/tmp/test.pdf")

        assert isinstance(result, ParseResult)
        assert result.metadata.total_pages == 1
        assert len(result.pages) == 1
        assert result.full_markdown == "# Hello World"
        assert result.parser_used == "mineru-local"

    @pytest.mark.asyncio
    async def test_parse_multi_page(self, parser):
        response = _file_parse_response(
            md_content="Page 1\n\nPage 2",
            content_list=[
                {"type": "text", "text": "Page 1", "page_idx": 0},
                {"type": "text", "text": "Page 2", "page_idx": 1},
            ],
        )

        mock_resp = MagicMock()
        mock_resp.json.return_value = response
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pathlib.Path.read_bytes", return_value=b"%PDF fake"), patch(
            "httpx.AsyncClient", return_value=mock_client
        ):
            result = await parser.parse("/tmp/test.pdf")

        assert result.metadata.total_pages == 2
        assert len(result.pages) == 2
        assert "Page 1" in result.full_markdown
        assert "Page 2" in result.full_markdown

    @pytest.mark.asyncio
    async def test_parse_http_status_error(self, parser):
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        http_error = httpx.HTTPStatusError("500", request=mock_request, response=mock_response)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=http_error)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pathlib.Path.read_bytes", return_value=b"%PDF fake"), patch(
            "httpx.AsyncClient", return_value=mock_client
        ):
            with pytest.raises(MinerUAPIError, match="MinerU service returned 500"):
                await parser.parse("/tmp/test.pdf")

    @pytest.mark.asyncio
    async def test_parse_request_error(self, parser):
        req_error = httpx.ConnectError("Connection refused")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=req_error)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pathlib.Path.read_bytes", return_value=b"%PDF fake"), patch(
            "httpx.AsyncClient", return_value=mock_client
        ):
            with pytest.raises(MinerUAPIError, match="Request to MinerU service failed"):
                await parser.parse("/tmp/test.pdf")

    @pytest.mark.asyncio
    async def test_parse_uses_multipart_upload(self, parser):
        """Verify the POST uses multipart files with correct form data."""
        response = _file_parse_response(
            md_content="content",
            content_list=[{"type": "text", "text": "content", "page_idx": 0}],
        )

        mock_resp = MagicMock()
        mock_resp.json.return_value = response
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pathlib.Path.read_bytes", return_value=b"%PDF fake"), patch(
            "httpx.AsyncClient", return_value=mock_client
        ):
            await parser.parse("/tmp/test.pdf")

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args.args[0] == "http://localhost:8001/file_parse"
        assert call_args.kwargs["files"]["file"][0] == "test.pdf"
        assert call_args.kwargs["files"]["file"][1] == b"%PDF fake"
        assert call_args.kwargs["files"]["file"][2] == "application/pdf"
        assert call_args.kwargs["data"]["return_content_list"] == "true"
        assert call_args.kwargs["data"]["return_images"] == "true"
        assert call_args.kwargs["data"]["return_md"] == "true"

    def test_name_property(self, parser):
        assert parser.name == "mineru-local"
