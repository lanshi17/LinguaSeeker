"""Custom exceptions for document parsing."""
from __future__ import annotations


class ParseDocumentError(Exception):
    """Base exception for parse_document module."""


class MinerUAPIError(ParseDocumentError):
    """MinerU API returned an error."""

    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(f"MinerU API error (status={status_code}): {message}" if status_code else message)

    def __repr__(self) -> str:
        return f"MinerUAPIError(message={self.args[0]!r}, status_code={self.status_code!r})"


class MinerUTimeoutError(ParseDocumentError):
    """MinerU API polling timed out (total allowed time, not per-request)."""

    def __init__(self, total_timeout: float):
        self.total_timeout = total_timeout
        super().__init__(f"MinerU API timed out after {total_timeout}s")

    def __repr__(self) -> str:
        return f"MinerUTimeoutError(total_timeout={self.total_timeout!r})"


class PaddleOCRError(ParseDocumentError):
    """PaddleOCR processing failed."""


class ParserExhaustedError(ParseDocumentError):
    """All parsers failed."""

    def __init__(self, errors: dict[str, Exception]):
        self.errors = errors
        parts = [f"{name}: {err}" for name, err in errors.items()]
        super().__init__(f"All parsers exhausted. {'; '.join(parts)}")

    def __repr__(self) -> str:
        return f"ParserExhaustedError(errors={self.errors!r})"
