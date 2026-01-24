"""API-facing exception definitions and helpers."""
from fastapi.responses import JSONResponse
from starlette import status
from typing import Optional, Dict, Any


class APIException(Exception):
    """Base exception carrying HTTP semantics."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error = error
        self.details = details or {}


class BadRequestError(APIException):
    """400 Bad Request."""

    def __init__(self, message: str, error: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status.HTTP_400_BAD_REQUEST, error, details)


class NotFoundError(APIException):
    """404 Not Found."""

    def __init__(self, message: str, error: Optional[str] = None):
        super().__init__(message, status.HTTP_404_NOT_FOUND, error)


class InvalidHGVSError(BadRequestError):
    """Invalid HGVS expression."""

    def __init__(self, variant: str):
        super().__init__(message=f"Invalid HGVS format: {variant}", error="invalid_hgvs_format")


def create_error_response(exc: APIException) -> JSONResponse:
    """Create a uniform error response body."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.message,
            "error": exc.error,
            "details": exc.details or {},
        },
    )
