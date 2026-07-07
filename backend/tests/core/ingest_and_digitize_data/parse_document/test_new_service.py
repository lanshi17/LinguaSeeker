"""Tests for refactored ParseDocumentService."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.core.ingest_and_digitize_data.parse_document.contracts import (
    DocumentMetadata,
    PageContent,
    ParseResult,
    ParseAndSaveResult,
)
from src.core.ingest_and_digitize_data.parse_document.service import ParseDocumentService


@pytest.fixture
def mock_orchestrator():
    """Create mock orchestrator."""
    orchestrator = AsyncMock()
    orchestrator.name = "orchestrator"
    return orchestrator


@pytest.fixture
def sample_result():
    """Create sample parse result."""
    return ParseResult(
        metadata=DocumentMetadata(total_pages=1),
        pages=[PageContent(page_number=1, markdown="test content")],
        parser_used="mineru-remote",
    )


@pytest.mark.asyncio
async def test_service_parse(mock_orchestrator, sample_result):
    """Test service parse method."""
    mock_orchestrator.parse.return_value = sample_result

    service = ParseDocumentService(orchestrator=mock_orchestrator)
    result = await service.parse("test.pdf")

    mock_orchestrator.parse.assert_called_once_with("test.pdf")
    assert result.parser_used == "mineru-remote"


@pytest.mark.asyncio
async def test_service_save(sample_result, tmp_path):
    """Test service save method."""
    service = ParseDocumentService(orchestrator=AsyncMock())

    with patch("src.core.ingest_and_digitize_data.parse_document.service.files_io"):
        saved = await service.save(sample_result, str(tmp_path))

        assert saved.md_path == tmp_path / "output.md"
        assert saved.metadata_path == tmp_path / "metadata.json"
        assert saved.output_dir == tmp_path
        assert isinstance(saved.created_at, datetime)
        assert saved.md_path.read_text(encoding="utf-8") == "test content"
        assert saved.metadata_path.exists()


@pytest.mark.asyncio
async def test_service_dedup():
    """Test service dedup method."""
    service = ParseDocumentService(orchestrator=AsyncMock())

    with patch("src.core.ingest_and_digitize_data.parse_document.service.files_io") as mock_files:
        mock_files.check_duplicate.return_value = {"hash": "abc123", "is_duplicate": False}

        results = await service.dedup(["test.pdf"], ["known_hash"])

        assert len(results) == 1
        assert results[0].file_path == "test.pdf"
        assert results[0].hash == "abc123"
        assert results[0].is_duplicate is False


@pytest.mark.asyncio
async def test_service_parse_and_save(mock_orchestrator, sample_result, tmp_path):
    """Test service parse_and_save method."""
    mock_orchestrator.parse.return_value = sample_result

    service = ParseDocumentService(orchestrator=mock_orchestrator)

    with patch("src.core.ingest_and_digitize_data.parse_document.service.files_io"):
        result = await service.parse_and_save("test.pdf", str(tmp_path))

        assert isinstance(result, ParseAndSaveResult)
        assert result.parser_used == "mineru-remote"
        assert result.saved_files is not None
        assert result.saved_files.md_path == tmp_path / "output.md"
