"""Session-cookie auth endpoints for the Vite SPA frontend.

Provides /login (set signed cookie), /logout (clear cookie), and
/me (check current session) for SPA authentication flow.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from src.api.auth import (
    SESSION_COOKIE,
    SESSION_DURATION_SEC,
    _get_signing_key,
    _validate_session,
    sign_session_token,
)
from src.core.config import get_config

router = APIRouter()


class LoginRequest(BaseModel):
    """Login request body."""

    password: str


class LoginResponse(BaseModel):
    """Login success response."""

    success: bool


class LogoutResponse(BaseModel):
    """Logout success response."""

    success: bool


class AuthMeResponse(BaseModel):
    """Current authentication status."""

    authenticated: bool
    email: str | None = None


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, response: Response) -> LoginResponse:
    """Validate the admin password and set a signed session cookie.

    Args:
        body: Request body containing the password.
        response: The outgoing response, used to set the session cookie.

    Returns:
        LoginResponse with ``success=True`` on valid credentials.

    Raises:
        HTTPException: 400 if no password, 500 if auth not configured,
            401 on invalid credentials.
    """
    cfg = get_config()
    secret = cfg.api_key

    if not secret:
        raise HTTPException(status_code=500, detail="Authentication not configured")
    if not body.password:
        raise HTTPException(status_code=400, detail="Password is required")
    if not hmac.compare_digest(body.password, secret):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    signing_key = _get_signing_key()
    token = sign_session_token(signing_key)

    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        secure=cfg.is_production,
        max_age=SESSION_DURATION_SEC,
        path="/",
    )
    return LoginResponse(success=True)


@router.post("/logout", response_model=LogoutResponse)
async def logout(response: Response) -> LogoutResponse:
    """Delete the session cookie.

    Args:
        response: The outgoing response, used to delete the cookie.

    Returns:
        LogoutResponse with ``success=True``.
    """
    response.delete_cookie(key=SESSION_COOKIE, path="/")
    return LogoutResponse(success=True)


@router.get("/me", response_model=AuthMeResponse)
async def me(request: Request) -> AuthMeResponse:
    """Return whether the current session cookie is valid.

    Args:
        request: The incoming request, used to read the session cookie.

    Returns:
        AuthMeResponse with ``authenticated=True`` if the session cookie is
        valid and not expired, otherwise ``authenticated=False``.
    """
    cfg = get_config()
    signing_key = _get_signing_key()
    token = request.cookies.get(SESSION_COOKIE)

    if not cfg.api_key or not token or not _validate_session(token, signing_key):
        return AuthMeResponse(authenticated=False)

    return AuthMeResponse(authenticated=True)
