"""Tests for parser factory."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.core.ingest_and_digitize_data.parse_document.contracts import (
    DocumentMetadata,
    PageContent,
    ParseResult,
)
from src.core.ingest_and_digitize_data.parse_document.exceptions import MinerUAPIError
from src.core.ingest_and_digitize_data.parse_document.parser_factory import ParserFactory


class TestParserFactory:
    @pytest.fixture
    def factory(self):
        return ParserFactory(model_server_url="http://localhost:8001")

    def test_factory_creates_parser(self, factory):
        assert factory.parser.name == "mineru-local"

    @pytest.mark.asyncio
    async def test_mineru_success(self, factory):
        mock_result = ParseResult(
            metadata=DocumentMetadata(total_pages=1),
            pages=[PageContent(page_number=1, markdown="test")],
            parser_used="mineru-remote",
        )

        with patch.object(factory.parser, "parse", new_callable=AsyncMock, return_value=mock_result):
            result = await factory.parse("/tmp/test.pdf")

        assert result.parser_used == "mineru-remote"

    @pytest.mark.asyncio
    async def test_mineru_failure_raises(self, factory):
        with patch.object(factory.parser, "parse", new_callable=AsyncMock, side_effect=MinerUAPIError("500")):
            with pytest.raises(MinerUAPIError):
                await factory.parse("/tmp/test.pdf")
