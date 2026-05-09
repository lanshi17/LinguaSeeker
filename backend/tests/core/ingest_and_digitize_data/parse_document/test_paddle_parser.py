"""Tests for PaddleOCR parser."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from src.core.ingest_and_digitize_data.parse_document.contracts import ParseResult
from src.core.ingest_and_digitize_data.parse_document.exceptions import PaddleOCRError
from src.core.ingest_and_digitize_data.parse_document.paddle_parser import PaddleOCRParser


class TestPaddleOCRParser:
    @pytest.fixture
    def parser(self):
        return PaddleOCRParser(model_path="/models/paddleocr-vl-1.5")

    def test_name(self, parser):
        assert parser.name == "paddleocr"

    @pytest.mark.asyncio
    async def test_parse_success(self, parser):
        mock_result = {
            "total_pages": 1,
            "pages": [
                {
                    "page_number": 1,
                    "markdown": "# Test\n\nContent",
                    "figures": [],
                    "tables": [],
                }
            ],
            "full_markdown": "# Test\n\nContent",
        }

        with patch.object(parser, "_run_paddle_ocr", return_value=mock_result):
            result = await parser.parse("/tmp/test.pdf")

        assert isinstance(result, ParseResult)
        assert result.parser_used == "paddleocr"

    @pytest.mark.asyncio
    async def test_parse_failure(self, parser):
        with patch.object(parser, "_run_paddle_ocr", side_effect=RuntimeError("Model crash")):
            with pytest.raises(PaddleOCRError):
                await parser.parse("/tmp/test.pdf")
