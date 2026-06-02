"""Tests for request body size limit middleware."""
from __future__ import annotations

from starlette.applications import Starlette
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
    """Chunked requests without Content-Length should be rejected by receive wrapper.

    Simulates a chunked transfer by sending two http.request messages
    without a Content-Length header in the ASGI scope.  The handler
    must read the body for the receive wrapper to be invoked.
    """
    import asyncio

    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def handler(request: Request):
        body = await request.body()
        return JSONResponse({"ok": True, "size": len(body)})

    starlette_app = Starlette(routes=[Route("/test", handler, methods=["POST"])])
    middleware = BodySizeLimitMiddleware(starlette_app, max_bytes=64)

    # Simulate a chunked request: two chunks totaling 128 bytes, no Content-Length
    chunk1 = b"x" * 50
    chunk2 = b"y" * 78  # Total: 128 > 64

    messages = [
        {"type": "http.request", "body": chunk1, "more_body": True},
        {"type": "http.request", "body": chunk2, "more_body": False},
    ]
    call_count = 0

    async def mock_receive() -> dict:
        nonlocal call_count
        msg = messages[min(call_count, len(messages) - 1)]
        call_count += 1
        return msg

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/test",
        "query_string": b"",
        "headers": [],  # No Content-Length header
    }
    response_started = []

    async def mock_send(message: dict) -> None:
        response_started.append(message)

    async def run():
        await middleware(scope, mock_receive, mock_send)

    asyncio.run(run())

    # Middleware should have sent a 413 response (not the app's 200)
    assert len(response_started) >= 1
    assert response_started[0]["type"] == "http.response.start"
    assert response_started[0]["status"] == 413


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
