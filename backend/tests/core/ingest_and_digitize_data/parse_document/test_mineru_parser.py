"""Tests for MinerU parser."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
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
        assert parser.name == "mineru-remote"

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
        assert result.parser_used == "mineru-remote"

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

    def test_parse_extracted_content_with_content_list(self, parser):
        """Verify parser handles MinerU zip format with content_list.json."""
        with tempfile.TemporaryDirectory() as tmp:
            content_dir = Path(tmp) / "extract"
            content_dir.mkdir()

            # full.md
            (content_dir / "full.md").write_text("# Title\n\nBody text", encoding="utf-8")

            # content_list.json
            content_list = [
                {"type": "text", "text": "Title", "text_level": 1, "page_idx": 0},
                {"type": "text", "text": "Body text", "page_idx": 0},
                {
                    "type": "image",
                    "img_path": "images/fig.jpg",
                    "image_caption": ["Figure 1"],
                    "image_footnote": [],
                    "bbox": [0, 0, 0, 0],
                    "page_idx": 0,
                },
                {
                    "type": "table",
                    "img_path": "images/table.jpg",
                    "table_caption": ["Table 1"],
                    "table_footnote": [],
                    "table_body": "<table><tr><td>A</td></tr><tr><td>1</td></tr></table>",
                    "bbox": [0, 0, 0, 0],
                    "page_idx": 0,
                },
            ]
            (content_dir / "test-uuid_content_list.json").write_text(
                json.dumps(content_list, ensure_ascii=False), encoding="utf-8"
            )

            result = parser._parse_extracted_content(content_dir)

        assert result["state"] == "done"
        assert result["total_pages"] == 1
        assert "Title" in result["full_markdown"]
        assert "![Figure 1]" in result["full_markdown"]
        assert "| A |" in result["full_markdown"]  # markdown table

    def test_parse_extracted_content_collects_images(self, parser):
        """Verify parser collects image files from zip."""
        with tempfile.TemporaryDirectory() as tmp:
            content_dir = Path(tmp) / "extract"
            content_dir.mkdir()

            # Create images directory with a fake image
            images_dir = content_dir / "images"
            images_dir.mkdir()
            fake_jpg = b"\xff\xd8\xff\xe0\x00fake_jpg_data"
            (images_dir / "fig1.jpg").write_bytes(fake_jpg)

            # full.md
            (content_dir / "full.md").write_text("# Title", encoding="utf-8")

            # content_list.json with image block
            content_list = [
                {"type": "text", "text": "Title", "text_level": 1, "page_idx": 0},
                {
                    "type": "image",
                    "img_path": "images/fig1.jpg",
                    "image_caption": ["Figure 1"],
                    "page_idx": 0,
                },
            ]
            (content_dir / "test_content_list.json").write_text(
                json.dumps(content_list, ensure_ascii=False), encoding="utf-8"
            )

            result = parser._parse_extracted_content(content_dir)

        assert result["state"] == "done"
        assert len(result["images"]) == 1
        assert "images/fig1.jpg" in result["images"]
        assert result["images"]["images/fig1.jpg"] == fake_jpg

    def test_parse_extracted_content_figure_has_img_path(self, parser):
        """Verify figure data includes img_path."""
        with tempfile.TemporaryDirectory() as tmp:
            content_dir = Path(tmp) / "extract"
            content_dir.mkdir()
            (content_dir / "full.md").write_text("text", encoding="utf-8")

            content_list = [
                {
                    "type": "image",
                    "img_path": "images/fig1.jpg",
                    "image_caption": ["Figure 1"],
                    "page_idx": 0,
                },
            ]
            (content_dir / "test_content_list.json").write_text(
                json.dumps(content_list), encoding="utf-8"
            )

            result = parser._parse_extracted_content(content_dir)

        page = result["pages"][0]
        assert page["figures"][0]["img_path"] == "images/fig1.jpg"

    def test_build_result_propagates_img_path_to_figure_position(self, parser):
        """Integration: raw dict with img_path -> ParseResult.pages[0].figures[0].img_path."""
        raw = {
            "state": "done",
            "total_pages": 1,
            "title": None,
            "authors": [],
            "abstract": None,
            "pages": [
                {
                    "page_number": 1,
                    "markdown": "text",
                    "figures": [{"index": 1, "caption": "Fig 1", "img_path": "images/fig1.jpg"}],
                    "tables": [],
                },
            ],
            "full_markdown": "text",
            "images": {"images/fig1.jpg": b"\xff\xd8\xff\xe0"},
        }
        result = parser._build_result(raw)

        assert isinstance(result, ParseResult)
        assert result.pages[0].figures[0].img_path == "images/fig1.jpg"
        assert result.images == {"images/fig1.jpg": b"\xff\xd8\xff\xe0"}
