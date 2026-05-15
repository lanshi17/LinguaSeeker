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
    def mock_orchestrator(self):
        orchestrator = AsyncMock()
        orchestrator.name = "orchestrator"
        return orchestrator

    @pytest.fixture
    def service(self, mock_orchestrator):
        return ParseDocumentService(orchestrator=mock_orchestrator)

    @pytest.mark.asyncio
    async def test_parse(self, service, mock_orchestrator):
        mock_result = ParseResult(
            metadata=DocumentMetadata(total_pages=1, title="Test"),
            pages=[PageContent(page_number=1, markdown="# Test")],
            parser_used="mineru-remote",
        )
        mock_orchestrator.parse.return_value = mock_result

        result = await service.parse("https://example.com/test.pdf")

        assert result.parser_used == "mineru-remote"

    @pytest.mark.asyncio
    async def test_parse_and_save(self, service, mock_orchestrator, tmp_path):
        output_dir = str(tmp_path / "output")

        mock_result = ParseResult(
            metadata=DocumentMetadata(total_pages=1, title="Test"),
            pages=[PageContent(page_number=1, markdown="# Test")],
            parser_used="mineru-remote",
        )
        mock_orchestrator.parse.return_value = mock_result

        with patch("src.core.ingest_and_digitize_data.parse_document.service.files_io"):
            result = await service.parse_and_save("https://example.com/test.pdf", output_dir)

        assert result.parser_used == "mineru-remote"
        assert result.saved_files is not None
        assert result.saved_files.md_path.name == "output.md"

    @pytest.mark.asyncio
    async def test_parse_and_save_preserves_images(self, service, mock_orchestrator, tmp_path):
        output_dir = str(tmp_path / "output")

        mock_result = ParseResult(
            metadata=DocumentMetadata(total_pages=1, title="Test"),
            pages=[PageContent(page_number=1, markdown="# Test")],
            parser_used="mineru-remote",
            images={"images/fig1.jpg": b"\xff\xd8\xff\xe0"},
        )
        mock_orchestrator.parse.return_value = mock_result

        with patch("src.core.ingest_and_digitize_data.parse_document.service.files_io"):
            result = await service.parse_and_save("https://example.com/test.pdf", output_dir)

        assert result.images == {"images/fig1.jpg": b"\xff\xd8\xff\xe0"}

    @pytest.mark.asyncio
    async def test_save_persists_images(self, service, tmp_path):
        result = ParseResult(
            metadata=DocumentMetadata(total_pages=1),
            pages=[PageContent(page_number=1, markdown="Content")],
            images={"images/fig1.jpg": b"\xff\xd8\xff\xe0"},
        )

        with patch("src.core.ingest_and_digitize_data.parse_document.service.files_io"):
            saved = await service.save(result, str(tmp_path))

        assert saved.images_dir is not None
        assert (saved.images_dir / "fig1.jpg").exists()
        assert (saved.images_dir / "fig1.jpg").read_bytes() == b"\xff\xd8\xff\xe0"

    @pytest.mark.asyncio
    async def test_save_no_images(self, service, tmp_path):
        result = ParseResult(
            metadata=DocumentMetadata(total_pages=1),
            pages=[PageContent(page_number=1, markdown="Content")],
        )

        with patch("src.core.ingest_and_digitize_data.parse_document.service.files_io"):
            saved = await service.save(result, str(tmp_path))

        assert saved.images_dir is None

    @pytest.mark.asyncio
    async def test_dedup(self, service):
        with patch("src.core.ingest_and_digitize_data.parse_document.service.files_io") as mock_files:
            mock_files.check_duplicate.return_value = {"hash": "abc123", "is_duplicate": True}

            results = await service.dedup(["/tmp/test.pdf"], ["abc123"])

            assert len(results) == 1
            assert results[0].is_duplicate is True

    @pytest.mark.asyncio
    async def test_parse_local_files_delegates_to_remote_batch_parser(self, service, mock_orchestrator, tmp_path):
        file_path = tmp_path / "paper.pdf"
        file_path.write_bytes(b"%PDF-1.4\n")
        expected = MagicMock()
        mock_orchestrator.parse_local_files = AsyncMock(return_value=expected)

        result = await service.parse_local_files([str(file_path)], data_ids=["paper-1"])

        assert result is expected
        mock_orchestrator.parse_local_files.assert_awaited_once_with([str(file_path)], data_ids=["paper-1"])

    @pytest.mark.asyncio
    async def test_parse_local_files_requires_orchestrator_support(self, service, mock_orchestrator, tmp_path):
        file_path = tmp_path / "paper.pdf"
        file_path.write_bytes(b"%PDF-1.4\n")
        if hasattr(mock_orchestrator, "parse_local_files"):
            del mock_orchestrator.parse_local_files

        with pytest.raises(AttributeError, match="parse_local_files"):
            await service.parse_local_files([str(file_path)])
