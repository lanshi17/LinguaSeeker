"""Tests for API key authentication."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient


def _sign_token(payload_dict: dict, secret: str) -> str:
    """Helper: create a signed session token matching the backend format."""
    from src.api.auth import _b64url_encode

    payload = _b64url_encode(json.dumps(payload_dict).encode("utf-8"))
    signature = _b64url_encode(hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest())
    return f"{payload}.{signature}"


@pytest.fixture
def _mock_config_with_api_key():
    """Provide config with API_KEY set."""
    with (
        patch("src.core.config.get_config") as mock_cfg,
        patch("src.api.auth.get_config") as mock_auth_cfg,
        patch("src.api.v1.auth.get_config") as mock_v1_auth_cfg,
    ):
        from src.core.config import Settings

        settings = Settings(api_key="test-secret-key", session_signing_key="")
        mock_cfg.return_value = settings
        mock_auth_cfg.return_value = settings
        mock_v1_auth_cfg.return_value = settings
        yield mock_cfg


@pytest.mark.asyncio
async def test_write_route_defaults_to_public_account_without_api_key(_mock_config_with_api_key):
    """Write routes should use public account scope when no credential is supplied."""
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()

    with (
        patch(
            "src.utils.health.check_all_connections",
            new_callable=AsyncMock,
            return_value=MagicMock(failed_services=MagicMock(return_value=[])),
        ),
        patch("src.api.v1.evidence.get_phase4_factory") as mock_factory,
        patch("src.api.deps.get_session_factory") as mock_sf,
    ):
        mock_sf.return_value = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        from src.core.visualize_evidence_with_expert_in_loop.contracts import ReviewStatus
        from src.core.visualize_evidence_with_expert_in_loop.feedback_service import PatchResult

        mock_service = MagicMock()
        mock_service.patch_evidence = AsyncMock(
            return_value=PatchResult(
                canonical_evidence_id="00000000-0000-0000-0000-000000000000",
                old_status=ReviewStatus.PROVISIONAL,
                new_status=ReviewStatus.CORRECTED,
                deltas=1,
                field_deltas=[],
            )
        )
        mock_factory.return_value.create_feedback_service.return_value = mock_service

        from app.main import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                "/api/v1/evidence/00000000-0000-0000-0000-000000000000",
                json={"fields": {"gene": "BRCA1"}},
            )
            assert resp.status_code == 200

        mock_service.patch_evidence.assert_awaited_once()
        kwargs = mock_service.patch_evidence.await_args.kwargs
        assert kwargs["owner_user_id"] is None
        assert kwargs["reviewer_id"] is None


@pytest.mark.asyncio
async def test_write_route_accepted_with_valid_api_key(_mock_config_with_api_key):
    """Write routes should accept requests with valid X-API-Key header."""
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()

    with (
        patch(
            "src.utils.health.check_all_connections",
            new_callable=AsyncMock,
            return_value=MagicMock(failed_services=MagicMock(return_value=[])),
        ),
        patch("src.api.v1.evidence.get_phase4_factory") as mock_factory,
        patch("src.api.deps.get_session_factory") as mock_sf,
    ):
        mock_sf.return_value = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        from src.core.visualize_evidence_with_expert_in_loop.feedback_service import PatchResult
        from src.core.visualize_evidence_with_expert_in_loop.contracts import ReviewStatus

        mock_service = MagicMock()
        mock_service.patch_evidence = AsyncMock(
            return_value=PatchResult(
                canonical_evidence_id="00000000-0000-0000-0000-000000000000",
                old_status=ReviewStatus.PROVISIONAL,
                new_status=ReviewStatus.CORRECTED,
                deltas=1,
                field_deltas=[],
            )
        )
        mock_factory.return_value.create_feedback_service.return_value = mock_service

        from app.main import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                "/api/v1/evidence/00000000-0000-0000-0000-000000000000",
                json={"fields": {"gene": "BRCA1"}},
                headers={"X-API-Key": "test-secret-key"},
            )
            assert resp.status_code == 200
            kwargs = mock_service.patch_evidence.await_args.kwargs
            assert kwargs["owner_user_id"] is None
            assert kwargs["reviewer_id"] is None


@pytest.mark.asyncio
async def test_me_defaults_to_public_account(_mock_config_with_api_key):
    """GET /auth/me returns public account when no session cookie is present."""
    with patch(
        "src.utils.health.check_all_connections",
        new_callable=AsyncMock,
        return_value=MagicMock(failed_services=MagicMock(return_value=[])),
    ):
        from app.main import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/auth/me")

        assert resp.status_code == 200
        assert resp.json() == {
            "authenticated": False,
            "account_type": "public",
            "user_id": None,
            "username": None,
            "display_name": "Public account",
        }


@pytest.mark.asyncio
async def test_read_routes_open_when_no_api_key_configured():
    """When API_KEY is empty, all routes are accessible without auth."""
    with (
        patch("src.core.config.get_config") as mock_cfg,
        patch(
            "src.utils.health.check_all_connections",
            new_callable=AsyncMock,
            return_value=MagicMock(failed_services=MagicMock(return_value=[])),
        ),
    ):
        from src.core.config import Settings

        mock_cfg.return_value = Settings(api_key="")  # No key configured

        from app.main import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Session signing key separation tests
# ---------------------------------------------------------------------------


def test_get_signing_key_falls_back_to_api_key():
    """When session_signing_key is empty, _get_signing_key returns api_key."""
    with patch("src.api.auth.get_config") as mock_cfg:
        from src.core.config import Settings

        mock_cfg.return_value = Settings(api_key="my-api-key", session_signing_key="")
        from src.api.auth import _get_signing_key

        assert _get_signing_key() == "my-api-key"


def test_get_signing_key_uses_dedicated_key():
    """When session_signing_key is set, _get_signing_key returns it."""
    with patch("src.api.auth.get_config") as mock_cfg:
        from src.core.config import Settings

        mock_cfg.return_value = Settings(api_key="my-api-key", session_signing_key="dedicated-signing-key")
        from src.api.auth import _get_signing_key

        assert _get_signing_key() == "dedicated-signing-key"


def test_login_request_rejects_blank_username():
    """Blank username should not be treated as legacy password-only login."""
    from pydantic import ValidationError

    from src.api.v1.contracts import LoginRequest

    with pytest.raises(ValidationError):
        LoginRequest(username="   ", password="password123")


@pytest.mark.asyncio
async def test_session_cookie_signed_with_signing_key_accepted():
    """A session cookie signed with session_signing_key should be accepted for auth."""
    signing_key = "dedicated-signing-key"
    token = _sign_token({"exp": int(time.time()) + 3600}, signing_key)

    with (
        patch("src.core.config.get_config") as mock_cfg,
        patch("src.api.auth.get_config", mock_cfg),
        patch("src.api.v1.auth.get_config", mock_cfg),
    ):
        from src.core.config import Settings

        mock_cfg.return_value = Settings(
            api_key="my-api-key",
            session_signing_key=signing_key,
        )

        from app.main import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/auth/me",
                cookies={"ce_session": token},
            )
            assert resp.status_code == 200
            assert resp.json()["authenticated"] is True


@pytest.mark.asyncio
async def test_session_cookie_signed_with_api_key_rejected_when_signing_key_set():
    """When session_signing_key is set, a cookie signed with api_key must be rejected."""
    token_signed_with_api_key = _sign_token({"exp": int(time.time()) + 3600}, "my-api-key")

    with (
        patch("src.core.config.get_config") as mock_cfg,
        patch("src.api.auth.get_config", mock_cfg),
        patch("src.api.v1.auth.get_config", mock_cfg),
    ):
        from src.core.config import Settings

        mock_cfg.return_value = Settings(
            api_key="my-api-key",
            session_signing_key="dedicated-signing-key",
        )

        from app.main import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/auth/me",
                cookies={"ce_session": token_signed_with_api_key},
            )
            assert resp.status_code == 200
            assert resp.json()["authenticated"] is False


@pytest.mark.asyncio
async def test_login_creates_cookie_with_signing_key():
    """POST /login should sign the session cookie with session_signing_key, not api_key."""
    api_key = "my-api-key"
    signing_key = "dedicated-signing-key"

    with (
        patch("src.core.config.get_config") as mock_cfg,
        patch("src.api.auth.get_config", mock_cfg),
        patch("src.api.v1.auth.get_config", mock_cfg),
    ):
        from src.core.config import Settings

        mock_cfg.return_value = Settings(
            api_key=api_key,
            session_signing_key=signing_key,
        )

        from app.main import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/auth/login",
                json={"password": api_key},
            )
            assert resp.status_code == 200

            cookie = resp.cookies.get("ce_session")
            assert cookie is not None

            from src.api.auth import _validate_session

            assert _validate_session(cookie, signing_key) is True
            assert _validate_session(cookie, api_key) is False


@pytest.mark.asyncio
async def test_login_creates_user_for_new_username(_mock_config_with_api_key):
    """POST /login should create and sign in a new username account."""
    user_id = uuid4()
    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = None

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=query_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    async def flush_with_user_id() -> None:
        created_user = mock_session.add.call_args.args[0]
        created_user.user_id = user_id

    mock_session.flush = AsyncMock(side_effect=flush_with_user_id)
    mock_session.rollback = AsyncMock()

    session_context = MagicMock()
    session_context.__aenter__ = AsyncMock(return_value=mock_session)
    session_context.__aexit__ = AsyncMock(return_value=False)
    session_factory = MagicMock(return_value=session_context)

    with (
        patch(
            "src.utils.health.check_all_connections",
            new_callable=AsyncMock,
            return_value=MagicMock(failed_services=MagicMock(return_value=[])),
        ),
        patch("src.api.v1.auth.get_session_factory", return_value=session_factory),
    ):
        from app.main import create_app
        from src.api.auth import _decode_session
        from src.core.auth.passwords import verify_password

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/auth/login",
                json={"username": "Clinician", "password": "password123"},
            )

        assert resp.status_code == 200
        assert resp.json()["account"] == {
            "authenticated": True,
            "account_type": "user",
            "user_id": str(user_id),
            "username": "clinician",
            "display_name": "clinician",
        }

        created_user = mock_session.add.call_args.args[0]
        assert created_user.username == "clinician"
        assert created_user.display_name == "clinician"
        assert verify_password("password123", created_user.password_hash)
        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_not_awaited()

        cookie = resp.cookies.get("ce_session")
        assert cookie is not None
        claims = _decode_session(cookie, "test-secret-key")
        assert claims is not None
        assert claims.user_id == user_id
        assert claims.username == "clinician"
