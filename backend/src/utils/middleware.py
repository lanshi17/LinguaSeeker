"""Shared ASGI middleware for the main backend."""
from __future__ import annotations

import time
from uuid import uuid4

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.utils.logger import get_logger


class RequestMonitorMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status code, and duration.

    Generates or extracts a ``request_id`` (from ``X-Request-ID`` header),
    stores it on ``request.state``, adds it to the response header, and
    includes it in every log line for distributed tracing.

    Logs timing even when the route handler raises an unhandled exception.

    Known limitation: ``BaseHTTPMiddleware`` buffers the full response body
    in memory, which breaks SSE / chunked streaming and large downloads.
    If streaming endpoints are added, rewrite this as raw ASGI middleware::

        class RequestMonitorMiddleware:
            async def __call__(self, scope, receive, send): ...
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        request_id = request.headers.get("x-request-id") or str(uuid4())
        request.state.request_id = request_id

        start = time.perf_counter()
        status = 500
        try:
            response: Response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            status = 500
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            get_logger().info(
                "{method} {path} -> {status} ({elapsed:.1f}ms) [rid={request_id}]",
                method=request.method,
                path=request.url.path,
                status=status,
                elapsed=elapsed_ms,
                request_id=request_id,
            )


def add_request_monitoring(app: FastAPI) -> None:
    """Register the request monitoring middleware on a FastAPI app."""
    app.add_middleware(RequestMonitorMiddleware)
