"""Tests for delta audit API routes."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_list_audit_events(async_client: AsyncClient):
    """GET /api/v1/delta-audit/ returns audit events."""
    with patch("src.api.v1.delta_audit.get_phase5_factory") as mock_factory:
        mock_service = MagicMock()
        mock_service.list_audit_events = AsyncMock(return_value=[])
        mock_factory.return_value.delta_audit = mock_service

        response = await async_client.get("/api/v1/delta-audit/")
        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.asyncio
async def test_patch_evidence_event_is_queryable_by_source_document(
    db_session: AsyncSession,
) -> None:
    """PATCH evidence through API records an audit event queryable by source document."""
    from app.main import create_app
    from src.agents.phase_5_factory import Phase5ServiceFactory
    from src.api.deps import get_db_session
    from src.core.config import Settings
    from src.dao.postgresql.models import CanonicalEvidenceItem, SourceDocument

    source_document_id = uuid4()
    canonical_evidence_id = uuid4()
    db_session.add(SourceDocument(source_document_id=source_document_id, raw_metadata={}))
    db_session.add(
        CanonicalEvidenceItem(
            canonical_evidence_id=canonical_evidence_id,
            source_document_id=source_document_id,
            field_id="B.disease_diagnosis",
            position_hash="pos-1",
            text_hash="txt-1",
            entity_scope_hash="scope-1",
            current_best_status="found",
            review_status="provisional",
            active_payload={
                "field_id": "B.disease_diagnosis",
                "value": "Fabry disease",
            },
        )
    )
    await db_session.flush()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    mock_settings = Settings(api_key="")
    factory = Phase5ServiceFactory(cfg=MagicMock())

    with (
        patch("src.core.config.get_config", return_value=mock_settings),
        patch("src.api.auth.get_config", return_value=mock_settings),
        patch("src.api.v1.evidence.get_phase5_factory", return_value=factory),
        patch("src.api.v1.delta_audit.get_phase5_factory", return_value=factory),
        patch(
            "src.core.visualize_evidence_with_expert_in_loop.feedback_service."
            "FeedbackService._refresh_literature_profile",
            new_callable=AsyncMock,
        ),
        patch(
            "src.core.visualize_evidence_with_expert_in_loop.feedback_service.FeedbackService._refresh_search_index",
            new_callable=AsyncMock,
        ),
    ):
        app = create_app()
        app.dependency_overrides[get_db_session] = override_session
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            patch_response = await client.patch(
                f"/api/v1/evidence/{canonical_evidence_id}",
                json={
                    "fields": {"disease": "Fabry disease type I"},
                    "change_reason": "curator correction",
                    "new_status": "corrected",
                },
            )
            audit_response = await client.get(
                "/api/v1/delta-audit/",
                params={"source_document_id": str(source_document_id)},
            )

    assert patch_response.status_code == 200
    assert audit_response.status_code == 200
    events = audit_response.json()
    assert len(events) == 1
    assert events[0]["canonical_evidence_id"] == str(canonical_evidence_id)
    assert events[0]["old_status"] == "provisional"
    assert events[0]["new_status"] == "corrected"
    assert events[0]["change_reason"] == "curator correction"
    assert events[0]["field_deltas"] == [
        {
            "field": "disease",
            "old_value": "Fabry disease",
            "new_value": "Fabry disease type I",
        }
    ]
