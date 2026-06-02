"""Request body size limit middleware.

Rejects requests whose Content-Length exceeds a configured maximum
before the body is read into memory, preventing memory-DoS from
oversized uploads.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests with Content-Length exceeding max_bytes.

    This runs before ASGI body parsing, so large payloads are rejected
    at the TCP level without allocating memory for the full body.
    """

    def __init__(self, app, max_bytes: int = 100 * 1024 * 1024) -> None:  # noqa: ANN001
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                size = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header"},
                )
            if size > self.max_bytes:
                max_mb = self.max_bytes // (1024 * 1024)
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"Request body too large. Maximum size: {max_mb}MB"},
                )
        return await call_next(request)
