"""API key and session-cookie authentication dependencies."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from uuid import UUID

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.core.config import get_config
from src.core.auth.contracts import AuthContext, PUBLIC_AUTH_CONTEXT, SessionClaims
from src.dao.postgresql.models import User

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

SESSION_COOKIE = "ce_session"
SESSION_DURATION_SEC = 8 * 3600  # 8 hours


def _get_signing_key() -> str:
    """Return the session signing key, falling back to api_key."""
    cfg = get_config()
    return cfg.session_signing_key or cfg.api_key


def _b64url_encode(data: bytes) -> str:
    """Return base64url encoding without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    """Return bytes decoded from base64url (padding-tolerant)."""
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _decode_session(token: str, secret: str) -> SessionClaims | None:
    """Decode and validate an HMAC-SHA256 signed session token.

    Token format: ``payload.signature`` where payload is base64url JSON
    with at least ``{"exp": <unix_ts>}`` and signature is base64url
    HMAC-SHA256 of the payload string keyed by ``secret``.

    Args:
        token: The session cookie value.
        secret: The shared secret used to sign the token.

    Returns:
        Decoded claims if the signature matches and the token has not
        expired, otherwise None.
    """
    if not token or not secret:
        return None

    parts = token.split(".")
    if len(parts) != 2:
        return None
    payload, signature = parts

    expected_sig = _b64url_encode(
        hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    )

    if not hmac.compare_digest(signature, expected_sig):
        return None

    try:
        data = json.loads(_b64url_decode(payload))
        exp = int(data["exp"])
    except (ValueError, KeyError, TypeError):
        return None

    if exp <= int(time.time()):
        return None

    user_id = None
    raw_user_id = data.get("user_id")
    if raw_user_id:
        try:
            user_id = UUID(str(raw_user_id))
        except ValueError:
            return None

    email = data.get("email")
    return SessionClaims(
        expires_at=exp,
        user_id=user_id,
        email=str(email) if email else None,
    )


def _validate_session(token: str, secret: str) -> bool:
    """Validate an HMAC-SHA256 signed session token."""
    return _decode_session(token, secret) is not None


def sign_session_token(
    secret: str,
    duration_sec: int = SESSION_DURATION_SEC,
    *,
    user_id: UUID | str | None = None,
    email: str | None = None,
) -> str:
    """Create an HMAC-SHA256 signed session token.

    Args:
        secret: The signing key.
        duration_sec: Token lifetime in seconds.
        user_id: Optional authenticated user id.
        email: Optional authenticated user email.

    Returns:
        A token string in ``payload.signature`` format.
    """
    expires_at = int(time.time()) + duration_sec
    payload_data: dict[str, str | int] = {"exp": expires_at}
    if user_id is not None:
        payload_data["user_id"] = str(user_id)
    if email:
        payload_data["email"] = email
    payload = _b64url_encode(json.dumps(payload_data).encode("utf-8"))
    signature = _b64url_encode(
        hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    )
    return f"{payload}.{signature}"


async def get_current_account(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    api_key: str | None = Security(_api_key_header),
) -> AuthContext:
    """Return the current account context, defaulting to the public account."""
    cfg = get_config()

    if api_key is not None:
        if cfg.api_key and hmac.compare_digest(api_key, cfg.api_key):
            return AuthContext(
                authenticated=True,
                account_type="public",
                user_id=None,
                email=None,
                display_name="Public account",
                method="api_key",
            )
        if cfg.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")

    token = request.cookies.get(SESSION_COOKIE)
    claims = _decode_session(token, _get_signing_key()) if token else None
    if claims is None:
        return PUBLIC_AUTH_CONTEXT

    if claims.user_id is None:
        return AuthContext(
            authenticated=True,
            account_type="public",
            user_id=None,
            email=claims.email,
            display_name="Public account",
            method="session",
        )

    result = await session.execute(select(User).where(User.user_id == claims.user_id))
    user = result.scalar_one_or_none()
    if user is None or user.status != "active":
        return PUBLIC_AUTH_CONTEXT

    return AuthContext(
        authenticated=True,
        account_type="user",
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        method="session",
    )


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
    if token and _validate_session(token, _get_signing_key()):
        return cfg.api_key

    raise HTTPException(status_code=401, detail="Missing X-API-Key header")
