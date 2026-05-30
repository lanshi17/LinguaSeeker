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
