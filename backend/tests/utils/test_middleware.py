"""Tests for request monitoring middleware."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from src.utils.middleware import add_request_monitoring


async def _ok(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


async def _error(request: Request) -> JSONResponse:
    return JSONResponse({"error": "boom"}, status_code=500)


@pytest_asyncio.fixture
async def client():
    app = Starlette(routes=[Route("/test", _ok), Route("/error", _error)])
    add_request_monitoring(app)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_successful_request_logs_timing(client: AsyncClient):
    """Middleware should log method, path, status, and timing."""
    from loguru import logger as loguru_logger

    messages: list[str] = []
    sink_id = loguru_logger.add(lambda msg: messages.append(str(msg)), level="INFO")
    try:
        resp = await client.get("/test")
        assert resp.status_code == 200
        assert any("GET /test" in msg and "200" in msg for msg in messages)
    finally:
        loguru_logger.remove(sink_id)


@pytest.mark.asyncio
async def test_error_request_returns_500(client: AsyncClient):
    resp = await client.get("/error")
    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_middleware_preserves_response_body(client: AsyncClient):
    resp = await client.get("/test")
    assert resp.json() == {"ok": True}


@pytest.mark.asyncio
async def test_middleware_adds_request_id_header(client: AsyncClient):
    resp = await client.get("/test")
    assert "x-request-id" in resp.headers


@pytest.mark.asyncio
async def test_middleware_preserves_client_request_id(client: AsyncClient):
    resp = await client.get("/test", headers={"X-Request-ID": "my-id-42"})
    assert resp.headers["x-request-id"] == "my-id-42"


@pytest.mark.asyncio
async def test_sse_streaming_not_broken_by_middleware():
    """SSE streaming endpoint should work correctly through the middleware.

    BaseHTTPMiddleware buffers the full response body, breaking SSE/chunked
    streaming. The middleware must be raw ASGI to pass through streaming.
    """
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse
    from httpx import ASGITransport, AsyncClient
    from src.utils.middleware import add_request_monitoring

    app = FastAPI()
    add_request_monitoring(app)

    @app.get("/stream")
    async def stream():
        async def generate():
            yield "data: chunk1\n\n"
            yield "data: chunk2\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        chunks = []
        async with client.stream("GET", "/stream") as resp:
            assert resp.status_code == 200
            async for line in resp.aiter_lines():
                if line.strip():
                    chunks.append(line)

    # Should receive both chunks — BaseHTTPMiddleware would buffer and
    # potentially only yield the full body at once
    assert len(chunks) >= 2
    assert "chunk1" in chunks[0]
    assert "chunk2" in chunks[1]


@pytest.mark.asyncio
async def test_request_state_request_id_accessible_in_error_handlers():
    """request.state.request_id must be accessible in error handlers after
    the raw ASGI middleware rewrite.

    The middleware sets scope["state"]["request_id"] which Starlette's
    Request.state wraps via _State attribute delegation.
    """
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from httpx import ASGITransport, AsyncClient
    from src.utils.middleware import add_request_monitoring

    app = FastAPI()
    add_request_monitoring(app)

    @app.get("/fail")
    async def fail():
        raise RuntimeError("boom")

    @app.exception_handler(RuntimeError)
    async def handler(request: Request, exc: RuntimeError):
        rid = getattr(request.state, "request_id", "MISSING")
        return JSONResponse(status_code=500, content={"request_id": rid})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/fail")
        assert resp.status_code == 500
        data = resp.json()
        assert data["request_id"] != "MISSING"
        assert len(data["request_id"]) > 0
