"""Centralized exception hierarchy for ACMG Lingua backend.

All domain exceptions inherit from ``ACMGException`` which carries a
human-readable ``message`` and a stable ``code`` string.  The API layer
uses these codes in structured error responses.
"""
from __future__ import annotations


class ACMGException(Exception):
    """Base exception for all ACMG Lingua domain errors."""

    def __init__(self, message: str, *, code: str = "INTERNAL_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


# ── Concrete exceptions ──────────────────────────────────────────────────


class NotFoundException(ACMGException):
    """Requested resource not found."""

    def __init__(self, entity: str, identifier: str) -> None:
        super().__init__(f"{entity} {identifier} not found", code="NOT_FOUND")


class ValidationException(ACMGException):
    """Input validation failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="VALIDATION_ERROR")


class DatabaseException(ACMGException):
    """Database operation failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="DATABASE_ERROR")


class LLMException(ACMGException):
    """LLM service call failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="LLM_ERROR")


class TranslationException(ACMGException):
    """Translation operation failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="TRANSLATION_ERROR")


class ParsingException(ACMGException):
    """Document parsing failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="PARSING_ERROR")


class ServiceException(ACMGException):
    """External service unavailable or failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="SERVICE_ERROR")


# ── Helpers ───────────────────────────────────────────────────────────────

# Stable mapping from HTTP status codes to error codes
_STATUS_TO_CODE: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
}


def error_code_from_exception(exc: Exception, *, status_code: int | None = None) -> str:
    """Derive a stable error code from an exception or HTTP status."""
    if isinstance(exc, ACMGException):
        return exc.code
    if status_code is not None:
        return _STATUS_TO_CODE.get(status_code, "INTERNAL_ERROR")
    return "INTERNAL_ERROR"
