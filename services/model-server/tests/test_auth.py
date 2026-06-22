"""Authentication tests for model-server API key handling."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import auth


@pytest.mark.asyncio
async def test_require_api_key_accepts_x_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """X-API-Key should be accepted because backend jobs commonly use it."""
    monkeypatch.setattr(auth, "get_config", lambda: SimpleNamespace(api_key="test-key"))

    token = await auth.require_api_key(x_api_key="test-key")

    assert token == "test-key"


@pytest.mark.asyncio
async def test_require_api_key_accepts_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Authorization: Bearer <key> should be accepted."""
    monkeypatch.setattr(auth, "get_config", lambda: SimpleNamespace(api_key="test-key"))

    token = await auth.require_api_key(auth_header="Bearer test-key")

    assert token == "test-key"


@pytest.mark.asyncio
async def test_require_api_key_rejects_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configured auth should reject requests without a matching key."""
    monkeypatch.setattr(auth, "get_config", lambda: SimpleNamespace(api_key="test-key"))

    with pytest.raises(HTTPException) as exc_info:
        await auth.require_api_key()

    assert exc_info.value.status_code == 401
