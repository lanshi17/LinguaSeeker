"""Centralized exception hierarchy for Lingua Seeker backend.

All domain exceptions inherit from ``ACMGException`` which carries a
human-readable ``message`` and a stable ``code`` string.  The API layer
uses these codes in structured error responses.
"""
from __future__ import annotations


class ACMGException(Exception):
    """Base exception for all Lingua Seeker domain errors."""

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

# Stable mapping from HTTP status codes to error codes (used by error handlers
# when only the HTTP status is known, e.g. StarletteHTTPException).
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

# Reverse mapping: domain error codes → HTTP status codes.
# Derived from _STATUS_TO_CODE plus domain-specific overrides (e.g. LLM_ERROR
# maps to 502 Bad Gateway since it indicates an upstream LLM failure).
_CODE_TO_STATUS: dict[str, int] = {
    # Standard HTTP codes (mirror of _STATUS_TO_CODE)
    "BAD_REQUEST": 400,
    "UNAUTHORIZED": 401,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "CONFLICT": 409,
    "VALIDATION_ERROR": 422,
    "RATE_LIMITED": 429,
    "INTERNAL_ERROR": 500,
    "BAD_GATEWAY": 502,
    "SERVICE_UNAVAILABLE": 503,
    # Domain-specific codes
    "DATABASE_ERROR": 500,
    "LLM_ERROR": 502,
    "SERVICE_ERROR": 503,
    "TRANSLATION_ERROR": 502,
    "PARSING_ERROR": 500,
    "PHASE_ERROR": 500,
}


def error_code_from_exception(exc: Exception, *, status_code: int | None = None) -> str:
    """Derive a stable error code from an exception or HTTP status.

    Used by the global ``StarletteHTTPException`` handler in ``app/main.py``
    to map HTTP status codes to our canonical error codes. For ``ACMGException``
    subclasses, returns the exception's own ``code`` attribute directly.
    """
    if isinstance(exc, ACMGException):
        return exc.code
    if status_code is not None:
        return _STATUS_TO_CODE.get(status_code, "INTERNAL_ERROR")
    return "INTERNAL_ERROR"


def status_code_from_error_code(code: str) -> int:
    """Derive an HTTP status code from a domain error code.

    Inverse of ``error_code_from_exception`` — used by the ``ACMGException``
    handler to convert domain codes back to HTTP status.
    """
    return _CODE_TO_STATUS.get(code, 500)
