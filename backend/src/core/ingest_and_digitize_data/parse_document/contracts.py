"""Data contracts for document parsing results."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

ParserName = Literal["mineru", "paddleocr", "unknown"]


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
