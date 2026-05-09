"""Tests for parse_document exceptions."""
from __future__ import annotations

import pytest

from src.core.ingest_and_digitize_data.parse_document.exceptions import (
    MinerUAPIError,
    MinerUTimeoutError,
    PaddleOCRError,
    ParseDocumentError,
    ParserExhaustedError,
)


class TestParseDocumentError:
    def test_base_exception(self):
        err = ParseDocumentError("test error")
        assert str(err) == "test error"
        assert isinstance(err, Exception)


class TestMinerUAPIError:
    def test_with_status_code(self):
        err = MinerUAPIError("API failed", status_code=500)
        assert err.status_code == 500
        assert "API failed" in str(err)

    def test_without_status_code(self):
        err = MinerUAPIError("API failed")
        assert err.status_code is None


class TestMinerUTimeoutError:
    def test_timeout(self):
        err = MinerUTimeoutError(timeout=300)
        assert err.timeout == 300
        assert "300" in str(err)


class TestPaddleOCRError:
    def test_paddle_error(self):
        err = PaddleOCRError("Model not found")
        assert "Model not found" in str(err)


class TestParserExhaustedError:
    def test_both_failed(self):
        err = ParserExhaustedError(
            mineru_error=MinerUAPIError("500"),
            paddle_error=PaddleOCRError("crash"),
        )
        assert "mineru" in str(err).lower() or "MinerU" in str(err)
        assert "paddle" in str(err).lower() or "Paddle" in str(err)
