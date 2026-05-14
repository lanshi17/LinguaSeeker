"""Data contracts for document parsing results."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

ParserName = Literal["mineru-remote", "mineru-local", "unknown"]


class DocumentMetadata(BaseModel):
    """Document-level metadata extracted from PDF."""

    total_pages: int = Field(ge=1, description="Total number of pages")
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    abstract_text: str | None = None


class FigurePosition(BaseModel):
    """Position of a figure within the document."""

    page: int = Field(ge=1)
    index: int = Field(ge=1, description="Figure index on this page")
    caption: str | None = None
    img_path: str | None = None


class TableStructure(BaseModel):
    """Structured table data extracted from PDF.

    All cell values are stored as strings. Numeric data from scientific
    tables is coerced to strings at extraction time — this prioritizes
    consistent markdown rendering over semantic type fidelity.
    """

    page: int = Field(ge=1)
    index: int = Field(ge=1, description="Table index on this page")
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class PageContent(BaseModel):
    """Content of a single page."""

    page_number: int = Field(ge=1)
    markdown: str
    figures: list[FigurePosition] = Field(default_factory=list)
    tables: list[TableStructure] = Field(default_factory=list)


def _figures_from_page(page_number: int, figures: list[dict]) -> list[FigurePosition]:
    """Extract figure positions from raw page data."""
    return [
        FigurePosition(page=page_number, index=f.get("index", 1), caption=f.get("caption"))
        for f in figures
    ]


def _tables_from_page(page_number: int, tables: list[dict]) -> list[TableStructure]:
    """Extract table structures from raw page data."""
    return [
        TableStructure(
            page=page_number,
            index=t.get("index", 1),
            headers=t.get("headers", []),
            rows=t.get("rows", []),
        )
        for t in tables
    ]


def pages_from_raw(pages_data: list[dict]) -> list[PageContent]:
    """Convert raw page dicts to PageContent list."""
    pages: list[PageContent] = []
    for i, page_data in enumerate(pages_data, start=1):
        page_number = page_data.get("page_number", i)
        pages.append(
            PageContent(
                page_number=page_number,
                markdown=page_data.get("markdown", ""),
                figures=_figures_from_page(page_number, page_data.get("figures", [])),
                tables=_tables_from_page(page_number, page_data.get("tables", [])),
            )
        )
    return pages


class ParseResult(BaseModel):
    """Complete result of PDF parsing.

    ``full_markdown`` is automatically derived from ``pages`` if not provided.
    """

    metadata: DocumentMetadata
    pages: list[PageContent]
    full_markdown: str = ""
    parser_used: ParserName = "unknown"

    @model_validator(mode="after")
    def _derive_full_markdown(self) -> ParseResult:
        if not self.full_markdown and self.pages:
            self.full_markdown = "\n\n".join(p.markdown for p in self.pages)
        return self


@dataclass
class SavedFiles:
    """Result of saving parsed document to files."""

    md_path: Path
    metadata_path: Path
    output_dir: Path
    created_at: datetime


@dataclass
class DedupResult:
    """Result of duplicate check for a file."""

    file_path: str
    hash: str
    is_duplicate: bool


class ParseAndSaveResult(ParseResult):
    """ParseResult extended with saved file information."""

    saved_files: SavedFiles | None = None
