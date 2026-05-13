"""Tests for parse_document exceptions."""
from __future__ import annotations

from src.core.ingest_and_digitize_data.parse_document.exceptions import (
    MinerUAPIError,
    MinerUTimeoutError,
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
        err = MinerUTimeoutError(total_timeout=300)
        assert err.total_timeout == 300
        assert "300" in str(err)


class TestParserExhaustedError:
    def test_both_failed(self):
        err = ParserExhaustedError(
            errors={
                "mineru-remote": MinerUAPIError("500"),
                "mineru_retry": MinerUTimeoutError(total_timeout=300),
            },
        )
        assert "mineru-remote" in str(err)
        assert "mineru_retry" in str(err)

    def test_repr(self):
        err = ParserExhaustedError(errors={"mineru-remote": MinerUAPIError("500")})
        assert "ParserExhaustedError" in repr(err)
