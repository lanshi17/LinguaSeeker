"""Unit tests for _batch_parse_downloads helper."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import (
    _batch_parse_downloads,
)


@pytest.mark.asyncio
async def test_batch_parse_downloads_attaches_markdown(tmp_path):
    """Successful MinerU batch attaches parsed_markdown to each download dict."""
    pdf_a = tmp_path / "a.pdf"
    pdf_b = tmp_path / "b.pdf"
    pdf_a.write_bytes(b"%PDF-1.4\n")
    pdf_b.write_bytes(b"%PDF-1.4\n")

    downloads = [
        {"file_path": str(pdf_a), "title": "A"},
        {"file_path": str(pdf_b), "title": "B"},
    ]

    fake_a = MagicMock(full_markdown="# A markdown", parser_used="mineru-remote")
    fake_b = MagicMock(full_markdown="# B markdown", parser_used="mineru-remote")
    fake_batch = MagicMock(results={"a.pdf": fake_a, "b.pdf": fake_b})

    fake_service = MagicMock()
    fake_service.parse_local_files = AsyncMock(return_value=fake_batch)

    with patch(
        "src.core.ingest_and_digitize_data.parse_document.create_parse_service",
        return_value=fake_service,
    ):
        out = await _batch_parse_downloads(downloads)

    assert out[0]["parsed_markdown"] == "# A markdown"
    assert out[0]["parser_used"] == "mineru-remote"
    assert out[1]["parsed_markdown"] == "# B markdown"
    fake_service.parse_local_files.assert_awaited_once_with([str(pdf_a), str(pdf_b)])


@pytest.mark.asyncio
async def test_batch_parse_downloads_handles_missing_results(tmp_path):
    """When MinerU returns nothing for a file, that download stays without markdown."""
    pdf_a = tmp_path / "a.pdf"
    pdf_a.write_bytes(b"%PDF-1.4\n")

    downloads = [{"file_path": str(pdf_a), "title": "A"}]

    fake_batch = MagicMock(results={})  # no result for a.pdf

    fake_service = MagicMock()
    fake_service.parse_local_files = AsyncMock(return_value=fake_batch)

    with patch(
        "src.core.ingest_and_digitize_data.parse_document.create_parse_service",
        return_value=fake_service,
    ):
        out = await _batch_parse_downloads(downloads)

    assert "parsed_markdown" not in out[0]


@pytest.mark.asyncio
async def test_batch_parse_downloads_empty_list_noop():
    """Empty input returns an empty list without invoking MinerU."""
    with patch(
        "src.core.ingest_and_digitize_data.parse_document.create_parse_service"
    ) as mock_factory:
        out = await _batch_parse_downloads([])
    assert out == []
    mock_factory.assert_not_called()


@pytest.mark.asyncio
async def test_batch_parse_downloads_swallows_minerU_failure(tmp_path):
    """A MinerU exception is logged but does NOT break the workflow."""
    pdf_a = tmp_path / "a.pdf"
    pdf_a.write_bytes(b"%PDF-1.4\n")
    downloads = [{"file_path": str(pdf_a), "title": "A"}]

    fake_service = MagicMock()
    fake_service.parse_local_files = AsyncMock(side_effect=RuntimeError("boom"))

    with patch(
        "src.core.ingest_and_digitize_data.parse_document.create_parse_service",
        return_value=fake_service,
    ):
        out = await _batch_parse_downloads(downloads)

    # Original list is returned unchanged (no parsed_markdown attached).
    assert out == downloads
    assert "parsed_markdown" not in out[0]


@pytest.mark.asyncio
async def test_batch_parse_downloads_handles_create_service_failure(tmp_path):
    """If parse_document module is unavailable, downloads pass through unchanged."""
    pdf_a = tmp_path / "a.pdf"
    pdf_a.write_bytes(b"%PDF-1.4\n")
    downloads = [{"file_path": str(pdf_a), "title": "A"}]

    with patch(
        "src.core.ingest_and_digitize_data.parse_document.create_parse_service",
        side_effect=ImportError("rust_io missing"),
    ):
        out = await _batch_parse_downloads(downloads)

    assert out == downloads
