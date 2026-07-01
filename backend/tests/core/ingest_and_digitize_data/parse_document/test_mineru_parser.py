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
from src.core.ingest_and_digitize_data.parse_document.remote.parser import MinerURemoteParser


class TestMinerURemoteParser:
    @pytest.fixture
    def parser(self):
        return MinerURemoteParser(
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

        with (
            patch("rust_io.net.mineru_create_task", new_callable=AsyncMock, return_value=mock_create_response),
            patch("rust_io.net.mineru_get_result", new_callable=AsyncMock, return_value=mock_poll_response),
            patch.object(parser, "_download_and_parse_zip", new_callable=AsyncMock) as mock_download,
        ):
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
    async def test_parse_create_task_rejects_nonzero_code(self, parser):
        mock_create_response = {
            "code": -1,
            "data": {},
            "msg": "bad token",
        }

        with patch("rust_io.net.mineru_create_task", new_callable=AsyncMock, return_value=mock_create_response):
            with pytest.raises(MinerUAPIError, match="MinerU create task failed: bad token"):
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

        with (
            patch("rust_io.net.mineru_create_task", new_callable=AsyncMock, return_value=mock_create_response),
            patch("rust_io.net.mineru_get_result", new_callable=AsyncMock, return_value=mock_pending_response),
        ):
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

        with (
            patch("rust_io.net.mineru_create_task", new_callable=AsyncMock, return_value=mock_create_response),
            patch("rust_io.net.mineru_get_result", new_callable=AsyncMock, return_value=mock_failed_response),
        ):
            with pytest.raises(MinerUAPIError, match="Task failed"):
                await parser.parse("https://example.com/test.pdf")

    @pytest.mark.asyncio
    async def test_parse_get_result_rejects_nonzero_code(self, parser):
        mock_create_response = {
            "code": 0,
            "data": {"task_id": "abc-123"},
            "msg": "ok",
        }
        mock_poll_response = {
            "code": -1,
            "data": {},
            "msg": "bad token",
        }

        with (
            patch("rust_io.net.mineru_create_task", new_callable=AsyncMock, return_value=mock_create_response),
            patch("rust_io.net.mineru_get_result", new_callable=AsyncMock, return_value=mock_poll_response),
        ):
            with pytest.raises(MinerUAPIError, match="MinerU get result failed: bad token"):
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

        # Verify raw_blocks are preserved (4 non-discarded blocks)
        assert "raw_blocks" in result
        assert len(result["raw_blocks"]) == 4
        assert result["raw_blocks"][0]["type"] == "text"
        assert result["raw_blocks"][2]["type"] == "image"
        assert result["raw_blocks"][3]["type"] == "table"

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

    def test_parse_extracted_content_collects_nested_images(self, parser):
        """Regression: images/ in a nested subdirectory are collected."""
        with tempfile.TemporaryDirectory() as tmp:
            content_dir = Path(tmp) / "extract"
            nested_root = content_dir / "some-root"
            nested_root.mkdir(parents=True)

            # nested images directory
            images_dir = nested_root / "images"
            images_dir.mkdir()
            fake_png = b"\x89PNG\r\n\x1a\n"
            (images_dir / "fig1.png").write_bytes(fake_png)

            # full.md at nested root
            (nested_root / "full.md").write_text("# Title", encoding="utf-8")

            # content_list.json at nested root
            content_list = [
                {"type": "text", "text": "Title", "text_level": 1, "page_idx": 0},
                {
                    "type": "image",
                    "img_path": "images/fig1.png",
                    "image_caption": ["Figure 1"],
                    "page_idx": 0,
                },
            ]
            (nested_root / "test_content_list.json").write_text(
                json.dumps(content_list, ensure_ascii=False), encoding="utf-8"
            )

            result = parser._parse_extracted_content(content_dir)

        assert result["state"] == "done"
        assert len(result["images"]) == 1
        assert "images/fig1.png" in result["images"]
        assert result["images"]["images/fig1.png"] == fake_png

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
            (content_dir / "test_content_list.json").write_text(json.dumps(content_list), encoding="utf-8")

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

    def test_build_result_populates_content_blocks(self, parser):
        """Verify _build_result passes raw_blocks as content_blocks to ParseResult."""
        raw_blocks = [
            {"type": "text", "text": "Title", "text_level": 1, "page_idx": 0},
            {"type": "image", "img_path": "images/fig.jpg", "page_idx": 0},
        ]
        raw = {
            "state": "done",
            "total_pages": 1,
            "title": None,
            "authors": [],
            "abstract": None,
            "pages": [{"page_number": 1, "markdown": "text", "figures": [], "tables": []}],
            "full_markdown": "text",
            "images": {},
            "raw_blocks": raw_blocks,
        }
        result = parser._build_result(raw)

        assert isinstance(result, ParseResult)
        assert len(result.content_blocks) == 2
        assert result.content_blocks[0]["type"] == "text"
        assert result.content_blocks[1]["type"] == "image"

    def test_build_result_defaults_content_blocks_empty(self, parser):
        """Verify _build_result defaults content_blocks to empty list when raw_blocks missing."""
        raw = {
            "state": "done",
            "total_pages": 1,
            "title": None,
            "authors": [],
            "abstract": None,
            "pages": [{"page_number": 1, "markdown": "text", "figures": [], "tables": []}],
            "full_markdown": "text",
            "images": {},
        }
        result = parser._build_result(raw)

        assert isinstance(result, ParseResult)
        assert result.content_blocks == []

    def test_validate_local_batch_rejects_empty_file_list(self, parser):
        with pytest.raises(MinerUAPIError, match="at least one file"):
            parser._validate_local_batch_inputs([], None)

    def test_validate_local_batch_rejects_more_than_50_files(self, parser, tmp_path):
        paths = []
        for index in range(51):
            file_path = tmp_path / f"paper-{index}.pdf"
            file_path.write_bytes(b"%PDF-1.4\n")
            paths.append(str(file_path))

        with pytest.raises(MinerUAPIError, match="50 files"):
            parser._validate_local_batch_inputs(paths, None)

    def test_validate_local_batch_rejects_missing_file(self, parser, tmp_path):
        missing = tmp_path / "missing.pdf"

        with pytest.raises(MinerUAPIError, match="does not exist"):
            parser._validate_local_batch_inputs([str(missing)], None)

    def test_validate_local_batch_rejects_data_id_length_mismatch(self, parser, tmp_path):
        file_path = tmp_path / "paper.pdf"
        file_path.write_bytes(b"%PDF-1.4\n")

        with pytest.raises(MinerUAPIError, match="data_ids length"):
            parser._validate_local_batch_inputs([str(file_path)], ["id-1", "id-2"])

    @pytest.mark.asyncio
    async def test_upload_local_files_returns_typed_upload_result(self, parser, tmp_path):
        file_path = tmp_path / "paper.pdf"
        file_path.write_bytes(b"%PDF-1.4\n")
        upload_response = {
            "code": 0,
            "msg": "ok",
            "trace_id": "trace-1",
            "data": {"batch_id": "batch-1", "file_urls": ["https://upload.example/paper"]},
        }

        with patch(
            "rust_io.net.mineru_upload_local_files", new_callable=AsyncMock, return_value=upload_response
        ) as upload:
            result = await parser.upload_local_files([str(file_path)], data_ids=["paper-1"], model_version="vlm")

        assert result.batch_id == "batch-1"
        assert result.file_paths == [str(file_path)]
        assert result.file_urls == ["https://upload.example/paper"]
        upload.assert_awaited_once_with(
            file_paths=[str(file_path)],
            token="test-token",
            model_version="vlm",
            enable_formula=True,
            enable_table=True,
            language="ch",
            data_ids=["paper-1"],
            is_ocr=None,
            page_ranges=None,
            callback=None,
            seed=None,
            extra_formats=None,
            timeout_ms=None,
            proxy=None,
        )

    @pytest.mark.asyncio
    async def test_upload_local_files_rejects_api_error_code(self, parser, tmp_path):
        file_path = tmp_path / "paper.pdf"
        file_path.write_bytes(b"%PDF-1.4\n")
        upload_response = {"code": -60005, "msg": "file too large", "data": {}}

        with patch("rust_io.net.mineru_upload_local_files", new_callable=AsyncMock, return_value=upload_response):
            with pytest.raises(MinerUAPIError, match="file too large"):
                await parser.upload_local_files([str(file_path)])

    @pytest.mark.asyncio
    async def test_poll_batch_result_returns_terminal_status(self, parser):
        response = {
            "code": 0,
            "msg": "ok",
            "data": {
                "batch_id": "batch-1",
                "extract_result": [
                    {
                        "file_name": "paper.pdf",
                        "state": "done",
                        "full_zip_url": "https://example.com/result.zip",
                        "err_msg": "",
                    }
                ],
            },
        }

        with patch("rust_io.net.mineru_batch_result", new_callable=AsyncMock, return_value=response) as poll:
            result = await parser.poll_batch_result("batch-1")

        assert result.batch_id == "batch-1"
        assert result.is_terminal is True
        assert result.extract_result[0].full_zip_url == "https://example.com/result.zip"
        poll.assert_awaited_once_with(batch_id="batch-1", token="test-token", timeout_ms=None, proxy=None)

    @pytest.mark.asyncio
    async def test_poll_batch_until_terminal_times_out(self, parser):
        response = {
            "code": 0,
            "msg": "ok",
            "data": {
                "batch_id": "batch-1",
                "extract_result": [{"file_name": "paper.pdf", "state": "running", "err_msg": ""}],
            },
        }

        with patch("rust_io.net.mineru_batch_result", new_callable=AsyncMock, return_value=response):
            with pytest.raises(MinerUTimeoutError):
                await parser.poll_batch_until_terminal("batch-1")

    @pytest.mark.asyncio
    async def test_parse_local_files_returns_results_and_failed_entries(self, parser, tmp_path):
        first = tmp_path / "first.pdf"
        second = tmp_path / "second.pdf"
        first.write_bytes(b"%PDF-1.4\n")
        second.write_bytes(b"%PDF-1.4\n")

        upload_response = {
            "code": 0,
            "msg": "ok",
            "data": {"batch_id": "batch-1", "file_urls": ["https://upload/1", "https://upload/2"]},
        }
        status_response = {
            "code": 0,
            "msg": "ok",
            "data": {
                "batch_id": "batch-1",
                "extract_result": [
                    {
                        "file_name": "first.pdf",
                        "state": "done",
                        "full_zip_url": "https://example.com/first.zip",
                        "err_msg": "",
                    },
                    {"file_name": "second.pdf", "state": "failed", "err_msg": "parse failed"},
                ],
            },
        }

        raw = {
            "state": "done",
            "total_pages": 1,
            "title": "First",
            "authors": [],
            "abstract": None,
            "pages": [{"page_number": 1, "markdown": "# First", "figures": [], "tables": []}],
            "full_markdown": "# First",
            "images": {},
        }

        with (
            patch("rust_io.net.mineru_upload_local_files", new_callable=AsyncMock, return_value=upload_response),
            patch("rust_io.net.mineru_batch_result", new_callable=AsyncMock, return_value=status_response),
            patch.object(parser, "_download_and_parse_zip", new_callable=AsyncMock, return_value=raw),
        ):
            result = await parser.parse_local_files([str(first), str(second)])

        assert result.batch_id == "batch-1"
        assert list(result.results.keys()) == ["first.pdf"]
        assert result.results["first.pdf"].full_markdown == "# First"
        assert result.failed_files == ["second.pdf"]

    @pytest.mark.asyncio
    async def test_single_url_parse_still_uses_create_task_not_batch_upload(self, parser):
        """Regression: single-URL parse() must use mineru_create_task, not batch upload."""
        mock_create_response = {"code": 0, "data": {"task_id": "task-1"}, "msg": "ok"}
        mock_poll_response = {
            "code": 0,
            "data": {"state": "done", "full_zip_url": "https://example.com/result.zip"},
            "msg": "ok",
        }
        raw = {
            "state": "done",
            "total_pages": 1,
            "title": None,
            "authors": [],
            "abstract": None,
            "pages": [{"page_number": 1, "markdown": "ok", "figures": [], "tables": []}],
            "full_markdown": "ok",
            "images": {},
        }

        with (
            patch(
                "rust_io.net.mineru_create_task", new_callable=AsyncMock, return_value=mock_create_response
            ) as create_task,
            patch("rust_io.net.mineru_get_result", new_callable=AsyncMock, return_value=mock_poll_response),
            patch("rust_io.net.mineru_upload_local_files", new_callable=AsyncMock) as upload_local_files,
            patch.object(parser, "_download_and_parse_zip", new_callable=AsyncMock, return_value=raw),
        ):
            result = await parser.parse("https://example.com/paper.pdf")

        assert result.full_markdown == "ok"
        create_task.assert_awaited_once()
        upload_local_files.assert_not_called()
