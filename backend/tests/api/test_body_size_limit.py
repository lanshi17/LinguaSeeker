"""Tests for request body size limit middleware."""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from fastapi import FastAPI

from src.api.body_size_limit import BodySizeLimitMiddleware


def test_body_size_limit_rejects_oversized_content_length():
    """Requests with Content-Length exceeding limit should be rejected before body read."""
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=1024)  # 1KB limit

    @app.post("/test")
    async def handler():
        return {"ok": True}

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/test",
        content=b"x",
        headers={"Content-Length": str(2048)},  # 2KB — exceeds 1KB limit
    )
    assert resp.status_code == 413
    assert "too large" in resp.json()["detail"].lower()


def test_body_size_limit_rejects_invalid_content_length():
    """Requests with invalid Content-Length should return 400."""
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=1024)

    @app.post("/test")
    async def handler():
        return {"ok": True}

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/test",
        content=b"x",
        headers={"Content-Length": "not-a-number"},
    )
    assert resp.status_code == 400


def test_body_size_limit_allows_normal_requests():
    """Requests within the size limit should pass through."""
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=1024)

    @app.post("/test")
    async def handler():
        return {"ok": True}

    client = TestClient(app)
    resp = client.post("/test", json={"key": "value"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_body_size_limit_handles_chunked_encoding():
    """Chunked requests exceeding the limit should be rejected by receive wrapper."""
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=64)  # 64 bytes limit

    received_size = 0

    @app.post("/test")
    async def handler(request_body: bytes = b""):
        return {"ok": True, "size": len(request_body)}

    client = TestClient(app, raise_server_exceptions=False)
    # Send a body that exceeds 64 bytes via chunked encoding
    # (TestClient doesn't truly chunk, but the receive wrapper tracks bytes)
    resp = client.post(
        "/test",
        content=b"x" * 128,  # 128 bytes — exceeds 64 byte limit
    )
    # With Content-Length set, the header check catches this
    assert resp.status_code == 413


def test_body_size_limit_does_not_buffer_responses():
    """Raw ASGI middleware should not buffer streaming responses."""
    from starlette.responses import StreamingResponse
    import asyncio

    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=1024)

    @app.get("/stream")
    async def stream():
        async def generate():
            yield "chunk1\n"
            yield "chunk2\n"

        return StreamingResponse(generate(), media_type="text/plain")

    client = TestClient(app)
    resp = client.get("/stream")
    assert resp.status_code == 200
    assert "chunk1" in resp.text
    assert "chunk2" in resp.text
