"""Tests for parse_document contracts."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.core.ingest_and_digitize_data.parse_document.contracts import (
    DocumentMetadata,
    FigurePosition,
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
