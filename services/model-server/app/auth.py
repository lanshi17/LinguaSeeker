"""API key authentication for model server endpoints."""

from __future__ import annotations

import hmac

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import get_config

_api_key_header = APIKeyHeader(name="Authorization", auto_error=False)
_x_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(
    auth_header: str | None = Security(_api_key_header),
    x_api_key: str | None = Security(_x_api_key_header),
) -> str | None:
    """Validate Bearer token or X-API-Key against configured API key.

    Returns the validated key string, or None if no key is configured
    (auth disabled).  Accepts both ``Authorization: Bearer <key>`` and
    ``X-API-Key: <key>`` formats for compatibility with OpenAI clients.
    """
    cfg = get_config()
    if not cfg.api_key:
        return None  # Auth disabled — no key configured

    # Try Bearer token first (OpenAI-compatible)
    if isinstance(auth_header, str) and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if hmac.compare_digest(token, cfg.api_key):
            return token

    if isinstance(x_api_key, str) and hmac.compare_digest(x_api_key, cfg.api_key):
        return x_api_key

    raise HTTPException(status_code=401, detail="Invalid or missing API key")
