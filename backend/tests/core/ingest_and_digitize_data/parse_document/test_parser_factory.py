"""Tests for parser factory."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.core.ingest_and_digitize_data.parse_document.contracts import (
    DocumentMetadata,
    PageContent,
    ParseResult,
)
from src.core.ingest_and_digitize_data.parse_document.exceptions import (
    MinerUAPIError,
    PaddleOCRError,
    ParserExhaustedError,
)
from src.core.ingest_and_digitize_data.parse_document.parser_factory import ParserFactory


class TestParserFactory:
    @pytest.fixture
    def factory(self):
        return ParserFactory(
            model_server_url="http://localhost:8001",
            paddle_model_path="/models/paddleocr",
        )

    def test_factory_creates_parsers(self, factory):
        assert len(factory.parsers) == 2

    @pytest.mark.asyncio
    async def test_mineru_success(self, factory):
        mock_result = ParseResult(
            metadata=DocumentMetadata(total_pages=1),
            pages=[PageContent(page_number=1, markdown="test")],
            parser_used="mineru",
        )

        with patch.object(factory.parsers[0], "parse", new_callable=AsyncMock, return_value=mock_result):
            result = await factory.parse("/tmp/test.pdf")

        assert result.parser_used == "mineru"

    @pytest.mark.asyncio
    async def test_mineru_fails_paddle_succeeds(self, factory):
        mock_result = ParseResult(
            metadata=DocumentMetadata(total_pages=1),
            pages=[PageContent(page_number=1, markdown="test")],
            parser_used="paddleocr",
        )

        with patch.object(factory.parsers[0], "parse", new_callable=AsyncMock, side_effect=MinerUAPIError("500")), \
             patch.object(factory.parsers[1], "parse", new_callable=AsyncMock, return_value=mock_result):
            result = await factory.parse("/tmp/test.pdf")

        assert result.parser_used == "paddleocr"

    @pytest.mark.asyncio
    async def test_both_fail_raises(self, factory):
        with patch.object(factory.parsers[0], "parse", new_callable=AsyncMock, side_effect=MinerUAPIError("500")), \
             patch.object(factory.parsers[1], "parse", new_callable=AsyncMock, side_effect=PaddleOCRError("crash")):
            with pytest.raises(ParserExhaustedError):
                await factory.parse("/tmp/test.pdf")
