"""Tests for parse_document contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.core.ingest_and_digitize_data.parse_document.contracts import (
    DocumentMetadata,
    FigurePosition,
    MinerUBatchExtractProgress,
    MinerUBatchFileResult,
    MinerUBatchStatus,
    MinerULocalBatchOptions,
    MinerULocalBatchUploadResult,
    PageContent,
    ParseResult,
    TableStructure,
)


class TestDocumentMetadata:
    def test_valid_metadata(self):
        meta = DocumentMetadata(
            total_pages=10,
            title="Test Paper",
            authors=["Author A", "Author B"],
            abstract_text="This is a test abstract.",
        )
        assert meta.total_pages == 10
        assert meta.title == "Test Paper"
        assert len(meta.authors) == 2

    def test_metadata_defaults(self):
        meta = DocumentMetadata(total_pages=5)
        assert meta.title is None
        assert meta.authors == []
        assert meta.abstract_text is None

    def test_invalid_pages(self):
        with pytest.raises(ValidationError):
            DocumentMetadata(total_pages=0)


class TestFigurePosition:
    def test_valid_figure(self):
        fig = FigurePosition(page=1, index=2, caption="Figure 1: Test")
        assert fig.page == 1
        assert fig.index == 2

    def test_figure_defaults(self):
        fig = FigurePosition(page=1, index=1)
        assert fig.caption is None

    def test_figure_with_img_path(self):
        fig = FigurePosition(page=1, index=1, caption="Fig 1", img_path="images/fig1.jpg")
        assert fig.img_path == "images/fig1.jpg"

    def test_figure_img_path_default_none(self):
        fig = FigurePosition(page=1, index=1)
        assert fig.img_path is None


class TestTableStructure:
    def test_valid_table(self):
        table = TableStructure(
            page=2,
            index=1,
            headers=["Name", "Value"],
            rows=[["A", "1"], ["B", "2"]],
        )
        assert len(table.headers) == 2
        assert len(table.rows) == 2


class TestPageContent:
    def test_valid_page(self):
        page = PageContent(
            page_number=1,
            markdown="# Title\n\nContent here.",
            figures=[FigurePosition(page=1, index=1, caption="Fig 1")],
            tables=[],
        )
        assert page.page_number == 1
        assert "Title" in page.markdown


class TestParseResult:
    def test_full_result(self):
        result = ParseResult(
            metadata=DocumentMetadata(total_pages=2, title="Test"),
            pages=[
                PageContent(page_number=1, markdown="Page 1"),
                PageContent(page_number=2, markdown="Page 2"),
            ],
            full_markdown="# Test\n\nPage 1\n\nPage 2",
            parser_used="mineru-remote",
        )
        assert result.metadata.total_pages == 2
        assert len(result.pages) == 2
        assert result.parser_used == "mineru-remote"

    def test_result_defaults(self):
        result = ParseResult(
            metadata=DocumentMetadata(total_pages=1),
            pages=[PageContent(page_number=1, markdown="Content")],
            full_markdown="Content",
        )
        assert result.parser_used == "unknown"

    def test_full_markdown_auto_derived(self):
        result = ParseResult(
            metadata=DocumentMetadata(total_pages=2),
            pages=[
                PageContent(page_number=1, markdown="Page 1"),
                PageContent(page_number=2, markdown="Page 2"),
            ],
        )
        assert result.full_markdown == "Page 1\n\nPage 2"

    def test_explicit_full_markdown_preserved(self):
        result = ParseResult(
            metadata=DocumentMetadata(total_pages=1),
            pages=[PageContent(page_number=1, markdown="Content")],
            full_markdown="Custom markdown",
        )
        assert result.full_markdown == "Custom markdown"

    def test_result_with_images(self):
        result = ParseResult(
            metadata=DocumentMetadata(total_pages=1),
            pages=[PageContent(page_number=1, markdown="Content")],
            images={"images/fig1.jpg": b"\xff\xd8\xff\xe0", "images/fig2.png": b"\x89PNG"},
        )
        assert len(result.images) == 2
        assert b"\xff\xd8" in result.images["images/fig1.jpg"]

    def test_result_images_default_empty(self):
        result = ParseResult(
            metadata=DocumentMetadata(total_pages=1),
            pages=[PageContent(page_number=1, markdown="Content")],
        )
        assert result.images == {}


def test_local_batch_options_rejects_callback_without_seed() -> None:
    with pytest.raises(ValidationError, match="seed is required"):
        MinerULocalBatchOptions(callback="https://example.com/callback")


def test_local_batch_options_rejects_unsupported_extra_format() -> None:
    with pytest.raises(ValidationError, match="extra_formats"):
        MinerULocalBatchOptions(extra_formats=["xlsx"])


def test_batch_upload_result_requires_matching_url_count() -> None:
    with pytest.raises(ValueError, match="upload URL count"):
        MinerULocalBatchUploadResult(batch_id="batch-1", file_paths=["a.pdf", "b.pdf"], file_urls=["https://u1"])


def test_batch_file_result_done_property() -> None:
    item = MinerUBatchFileResult(file_name="demo.pdf", state="done", full_zip_url="https://example.com/result.zip")
    assert item.is_done is True
    assert item.is_terminal is True


def test_batch_file_result_running_progress() -> None:
    item = MinerUBatchFileResult(
        file_name="demo.pdf",
        state="running",
        extract_progress=MinerUBatchExtractProgress(
            extracted_pages=1,
            total_pages=2,
            start_time="2026-05-15 10:00:00",
        ),
    )
    assert item.is_done is False
    assert item.is_terminal is False


def test_batch_file_result_failed_property() -> None:
    item = MinerUBatchFileResult(file_name="demo.pdf", state="failed", err_msg="parse error")
    assert item.is_done is False
    assert item.is_terminal is True


def test_batch_status_terminal_semantics() -> None:
    mixed = MinerUBatchStatus(
        batch_id="batch-1",
        extract_result=[
            MinerUBatchFileResult(file_name="a.pdf", state="done"),
            MinerUBatchFileResult(file_name="b.pdf", state="running"),
        ],
    )
    failed = MinerUBatchStatus(
        batch_id="batch-2",
        extract_result=[MinerUBatchFileResult(file_name="a.pdf", state="failed", err_msg="parse error")],
    )
    empty = MinerUBatchStatus(batch_id="batch-3")

    assert mixed.is_terminal is False
    assert failed.is_terminal is True
    assert empty.is_terminal is False
