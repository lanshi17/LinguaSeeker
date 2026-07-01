"""Tests for new data contracts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def test_parser_name_literal():
    """Test ParserName includes remote and local variants."""
    from src.core.ingest_and_digitize_data.parse_document.contracts import ParserName

    assert "mineru-remote" in ParserName.__args__
    assert "mineru-local" in ParserName.__args__
    assert "unknown" in ParserName.__args__


def test_saved_files_creation():
    """Test SavedFiles dataclass creation."""
    from src.core.ingest_and_digitize_data.parse_document.contracts import SavedFiles

    now = datetime.now()
    saved = SavedFiles(
        md_path=Path("/tmp/output.md"),
        metadata_path=Path("/tmp/metadata.json"),
        output_dir=Path("/tmp"),
        created_at=now,
    )
    assert saved.md_path == Path("/tmp/output.md")
    assert saved.metadata_path == Path("/tmp/metadata.json")
    assert saved.output_dir == Path("/tmp")
    assert saved.created_at == now


def test_dedup_result_creation():
    """Test DedupResult dataclass creation."""
    from src.core.ingest_and_digitize_data.parse_document.contracts import DedupResult

    result = DedupResult(
        file_path="/tmp/test.pdf",
        hash="abc123",
        is_duplicate=False,
    )
    assert result.file_path == "/tmp/test.pdf"
    assert result.hash == "abc123"
    assert result.is_duplicate is False


def test_parse_and_save_result_creation():
    """Test ParseAndSaveResult inherits ParseResult and adds saved files."""
    from src.core.ingest_and_digitize_data.parse_document.contracts import (
        DocumentMetadata,
        PageContent,
        ParseAndSaveResult,
        SavedFiles,
    )

    now = datetime.now()
    saved = SavedFiles(
        md_path=Path("/tmp/output.md"),
        metadata_path=Path("/tmp/metadata.json"),
        output_dir=Path("/tmp"),
        created_at=now,
    )
    result = ParseAndSaveResult(
        metadata=DocumentMetadata(total_pages=1),
        pages=[PageContent(page_number=1, markdown="test")],
        parser_used="mineru-remote",
        saved_files=saved,
    )
    assert result.parser_used == "mineru-remote"
    assert result.images == {}
    assert result.saved_files is not None
    assert result.saved_files.md_path == Path("/tmp/output.md")
    assert result.saved_files.metadata_path == Path("/tmp/metadata.json")
    assert result.saved_files.output_dir == Path("/tmp")
    assert result.saved_files.created_at == now

    # With explicit images
    result_with_images = ParseAndSaveResult(
        metadata=DocumentMetadata(total_pages=1),
        pages=[PageContent(page_number=1, markdown="test")],
        parser_used="mineru-remote",
        images={"images/fig.jpg": b"\xff\xd8"},
        saved_files=saved,
    )
    assert result_with_images.images == {"images/fig.jpg": b"\xff\xd8"}
