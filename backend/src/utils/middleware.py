"""Shared ASGI middleware for the main backend."""

from __future__ import annotations

import time
from uuid import uuid4

from fastapi import FastAPI
from starlette.types import ASGIApp, Receive, Scope, Send

from src.utils.logger import get_logger


class RequestMonitorMiddleware:
    """Raw ASGI middleware that logs every request with timing and request_id.

    Unlike BaseHTTPMiddleware, this does NOT buffer the response body,
    so SSE / chunked streaming and large downloads work correctly.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = None
        for key, value in scope.get("headers", []):
            if key == b"x-request-id":
                request_id = value.decode()
                break
        if request_id is None:
            request_id = str(uuid4())

        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id

        method = scope.get("method", "?")
        path = scope.get("path", "?")
        start = time.perf_counter()
        status = 500

        async def send_wrapper(message):
            nonlocal status
            if message["type"] == "http.response.start":
                # Append to the header list — ASGI headers are a list of
                # 2-tuples specifically to allow duplicate keys (e.g.
                # multiple Set-Cookie). Do NOT convert to dict.
                message["headers"] = list(message.get("headers", []))
                message["headers"].append((b"x-request-id", request_id.encode()))
                status = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            status = 500
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            get_logger().info(
                "{method} {path} -> {status} ({elapsed:.1f}ms) [rid={request_id}]",
                method=method,
                path=path,
                status=status,
                elapsed=elapsed_ms,
                request_id=request_id,
            )


def add_request_monitoring(app: FastAPI) -> None:
    """Register the request monitoring middleware on a FastAPI app."""
    app.add_middleware(RequestMonitorMiddleware)
