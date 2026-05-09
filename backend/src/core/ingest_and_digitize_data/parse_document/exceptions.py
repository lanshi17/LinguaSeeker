"""Custom exceptions for document parsing."""
from __future__ import annotations


class ParseDocumentError(Exception):
    """Base exception for parse_document module."""


class MinerUAPIError(ParseDocumentError):
    """MinerU API returned an error."""

    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(f"MinerU API error (status={status_code}): {message}" if status_code else message)


class MinerUTimeoutError(ParseDocumentError):
    """MinerU API request timed out."""

    def __init__(self, timeout: int):
        self.timeout = timeout
        super().__init__(f"MinerU API timed out after {timeout}s")


class PaddleOCRError(ParseDocumentError):
    """PaddleOCR processing failed."""


class ParserExhaustedError(ParseDocumentError):
    """All parsers failed."""

    def __init__(self, mineru_error: Exception | None, paddle_error: Exception | None):
        self.mineru_error = mineru_error
        self.paddle_error = paddle_error
        parts = []
        if mineru_error:
            parts.append(f"MinerU: {mineru_error}")
        if paddle_error:
            parts.append(f"PaddleOCR: {paddle_error}")
        super().__init__(f"All parsers exhausted. {'; '.join(parts)}")
