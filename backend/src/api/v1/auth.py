"""Session-cookie auth endpoints for the Vite SPA frontend."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.api.auth import (
    SESSION_COOKIE,
    SESSION_DURATION_SEC,
    _decode_session,
    _get_signing_key,
    sign_session_token,
)
from src.api.v1.contracts import AuthMeResponse, AuthResponse, LoginRequest, LogoutResponse, RegisterRequest
from src.api.wiring import get_session_factory
from src.core.auth.passwords import hash_password, verify_password
from src.core.config import get_config
from src.dao.postgresql.models import User

router = APIRouter()


def _public_account_response(*, authenticated: bool = False, email: str | None = None) -> AuthMeResponse:
    """Return the public account API response."""
    return AuthMeResponse(
        authenticated=authenticated,
        account_type="public",
        user_id=None,
        email=email,
        display_name="Public account",
    )


def _user_account_response(user: User) -> AuthMeResponse:
    """Return a user account API response."""
    return AuthMeResponse(
        authenticated=True,
        account_type="user",
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
    )


def _set_session_cookie(response: Response, token: str) -> None:
    """Attach the signed session cookie to a response."""
    cfg = get_config()
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        secure=cfg.is_production,
        max_age=SESSION_DURATION_SEC,
        path="/",
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, response: Response) -> AuthResponse:
    """Validate credentials and set a signed session cookie.

    Email + password uses persisted ``users`` rows. Password-only login keeps
    the legacy API-key session behavior for existing deployments and tests.
    """
    cfg = get_config()

    if not body.password:
        raise HTTPException(status_code=400, detail="Password is required")

    signing_key = _get_signing_key()
    if body.email is None:
        secret = cfg.api_key
        if not secret:
            raise HTTPException(status_code=500, detail="Authentication not configured")
        if not hmac.compare_digest(body.password, secret):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = sign_session_token(signing_key)
        _set_session_cookie(response, token)
        return AuthResponse(success=True, account=_public_account_response(authenticated=True))

    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.email == body.email))
        user = result.scalar_one_or_none()
        if user is None or user.status != "active" or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = sign_session_token(signing_key, user_id=user.user_id, email=user.email)
        _set_session_cookie(response, token)
        return AuthResponse(success=True, account=_user_account_response(user))


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, response: Response) -> AuthResponse:
    """Create a local email account and set a signed session cookie."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        existing_result = await session.execute(select(User.user_id).where(User.email == body.email))
        if existing_result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="Email is already registered")

        user = User(
            email=body.email,
            password_hash=hash_password(body.password),
            display_name=body.display_name,
            status="active",
        )
        session.add(user)
        try:
            await session.flush()
            token = sign_session_token(_get_signing_key(), user_id=user.user_id, email=user.email)
            _set_session_cookie(response, token)
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(status_code=409, detail="Email is already registered") from exc

        return AuthResponse(success=True, account=_user_account_response(user))


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
    """Return the current session account, defaulting to public."""
    signing_key = _get_signing_key()
    token = request.cookies.get(SESSION_COOKIE)

    claims = _decode_session(token, signing_key) if token else None
    if claims is None:
        return _public_account_response(authenticated=False)

    if claims.user_id is None:
        return _public_account_response(authenticated=True, email=claims.email)

    try:
        session_factory = get_session_factory()
    except RuntimeError:
        return _public_account_response(authenticated=False)

    async with session_factory() as session:
        result = await session.execute(select(User).where(User.user_id == claims.user_id))
        user = result.scalar_one_or_none()
        if user is None or user.status != "active":
            return _public_account_response(authenticated=False)

        return _user_account_response(user)
