"""Tests for request body size limit middleware."""
from __future__ import annotations

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse
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
    # Starlette TestClient preserves the Content-Length header from headers dict
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
