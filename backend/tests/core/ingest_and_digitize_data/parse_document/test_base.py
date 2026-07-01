"""Tests for parse_document base class."""

from __future__ import annotations

import pytest

from src.core.ingest_and_digitize_data.parse_document.base import ParserStrategy
from src.core.ingest_and_digitize_data.parse_document.contracts import (
    DocumentMetadata,
    PageContent,
    ParseResult,
)


class TestParserStrategy:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            ParserStrategy()

    def test_concrete_implementation(self):
        class DummyParser(ParserStrategy):
            @property
            def name(self) -> str:
                return "dummy"

            async def parse(self, pdf_path: str) -> ParseResult:
                return ParseResult(
                    metadata=DocumentMetadata(total_pages=1),
                    pages=[PageContent(page_number=1, markdown="test")],
                    full_markdown="test",
                )

        parser = DummyParser()
        assert parser.name == "dummy"
