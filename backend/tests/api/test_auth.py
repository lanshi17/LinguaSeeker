"""Tests for API key authentication."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


def _sign_token(payload_dict: dict, secret: str) -> str:
    """Helper: create a signed session token matching the backend format."""
    from src.api.auth import _b64url_encode
    payload = _b64url_encode(json.dumps(payload_dict).encode("utf-8"))
    signature = _b64url_encode(
        hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    )
    return f"{payload}.{signature}"


@pytest.fixture
def _mock_config_with_api_key():
    """Provide config with API_KEY set."""
    with patch("src.core.config.get_config") as mock_cfg:
        from src.core.config import Settings
        mock_cfg.return_value = Settings(api_key="test-secret-key")
        yield mock_cfg


@pytest.mark.asyncio
async def test_write_route_rejected_without_api_key(_mock_config_with_api_key):
    """Write routes should return 401 when API_KEY is set but not provided."""
    with (
        patch("src.utils.health.check_all_connections", new_callable=AsyncMock,
              return_value=MagicMock(failed_services=MagicMock(return_value=[]))),
    ):
        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                "/api/v1/evidence/00000000-0000-0000-0000-000000000000",
                json={"fields": {"gene": "BRCA1"}},
            )
            assert resp.status_code == 401


@pytest.mark.asyncio
async def test_write_route_accepted_with_valid_api_key(_mock_config_with_api_key):
    """Write routes should accept requests with valid X-API-Key header."""
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()

    with (
        patch("src.utils.health.check_all_connections", new_callable=AsyncMock,
              return_value=MagicMock(failed_services=MagicMock(return_value=[]))),
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
        mock_service.patch_evidence = AsyncMock(return_value=PatchResult(
            canonical_evidence_id="00000000-0000-0000-0000-000000000000",
            old_status=ReviewStatus.PROVISIONAL,
            new_status=ReviewStatus.CORRECTED,
            deltas=1,
            field_deltas=[],
        ))
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


@pytest.mark.asyncio
async def test_read_routes_open_when_no_api_key_configured():
    """When API_KEY is empty, all routes are accessible without auth."""
    with (
        patch("src.core.config.get_config") as mock_cfg,
        patch("src.utils.health.check_all_connections", new_callable=AsyncMock,
              return_value=MagicMock(failed_services=MagicMock(return_value=[]))),
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

