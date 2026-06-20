"""API key and session-cookie authentication dependencies."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from src.core.config import get_config

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

SESSION_COOKIE = "ce_session"
SESSION_DURATION_SEC = 8 * 3600  # 8 hours


def _b64url_encode(data: bytes) -> str:
    """Return base64url encoding without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    """Return bytes decoded from base64url (padding-tolerant)."""
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _validate_session(token: str, secret: str) -> bool:
    """Validate an HMAC-SHA256 signed session token.

    Token format: ``payload.signature`` where payload is base64url JSON
    ``{"exp": <unix_ts>}`` and signature is base64url HMAC-SHA256 of the
    payload string keyed by ``secret``.

    Args:
        token: The session cookie value.
        secret: The shared secret used to sign the token.

    Returns:
        True if the signature matches and the token has not expired.
    """
    if not token or not secret:
        return False

    parts = token.split(".")
    if len(parts) != 2:
        return False
    payload, signature = parts

    expected_sig = _b64url_encode(
        hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    )

    if not hmac.compare_digest(signature, expected_sig):
        return False

    try:
        data = json.loads(_b64url_decode(payload))
        exp = int(data["exp"])
    except (ValueError, KeyError, TypeError):
        return False

    return exp > int(time.time())


async def require_api_key(
    request: Request,
    api_key: str | None = Security(_api_key_header),
) -> str | None:
    """Validate X-API-Key header or session cookie against configured API_KEY.

    Accepts either an ``X-API-Key`` header or a valid ``ce_session`` cookie.
    Returns the validated key string, or None if no key is configured (auth
    disabled). Routes that need a reviewer_id can use this value.

    Args:
        request: The incoming request, used to read the session cookie.
        api_key: The value of the X-API-Key header, if present.

    Returns:
        The validated API key string, or None if auth is disabled.

    Raises:
        HTTPException: 401 when a key is configured but no valid credential
            is supplied.
    """
    cfg = get_config()
    if not cfg.api_key:
        return None  # Auth disabled — no key configured

    # Header-based auth (existing behavior).
    if api_key is not None:
        if hmac.compare_digest(api_key, cfg.api_key):
            return api_key
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Session-cookie auth (alternative for SPA clients).
    token = request.cookies.get(SESSION_COOKIE)
    if token and _validate_session(token, cfg.api_key):
        return cfg.api_key

    raise HTTPException(status_code=401, detail="Missing X-API-Key header")
