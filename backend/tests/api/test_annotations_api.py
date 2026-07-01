"""End-to-end API tests for the document annotations CRUD routes.

These tests spin up an in-memory SQLite database, wire it into the FastAPI
app via ``get_session_factory``, and exercise the
``/api/v1/documents/{source_document_id}/annotations`` endpoints through the
ASGI transport. Auth is disabled (empty API key) to keep the focus on CRUD
behavior.

NOTE: A ``StaticPool`` is required so that every request session shares the
same in-memory SQLite database (otherwise each connection gets its own
ephemeral DB).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.dao.postgresql.models import Base, SourceDocument

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@asynccontextmanager
async def _app_client() -> AsyncGenerator[tuple[AsyncClient, uuid.UUID], None]:
    """Build an app client backed by an isolated in-memory SQLite DB.

    Yields:
        A tuple of (httpx AsyncClient, source_document_id) seeded with one
        parent ``SourceDocument`` row.
    """
    engine = create_async_engine(
        SQLITE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    # Swap JSONB -> JSON so SQLite can render column types (mirrors conftest).
    swapped: list[tuple] = []
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                swapped.append((col, col.type))
                col.type = JSON()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    for col, original_type in swapped:
        col.type = original_type

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Seed a parent source document so the FK is satisfied.
    doc_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(SourceDocument(source_document_id=doc_id, raw_metadata={}))
        await session.commit()

    with (
        patch("src.core.config.get_config") as mock_cfg,
        patch(
            "src.utils.health.check_all_connections",
            new_callable=AsyncMock,
            return_value=MagicMock(failed_services=MagicMock(return_value=[])),
        ),
        patch("src.api.deps.get_session_factory", return_value=session_factory),
    ):
        from src.core.config import Settings

        mock_cfg.return_value = Settings(api_key="")  # auth disabled

        from app.main import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, doc_id

    await engine.dispose()


def _payload(track: str = "original", **overrides) -> dict:
    """Build a minimal valid annotation creation payload."""
    base = {
        "track": track,
        "paragraph_id": "para-1-full-text",
        "start_offset": 0,
        "end_offset": 10,
        "color": "#fde68a",
        "note": "highlight",
        "author": "tester",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_create_list_update_delete_flow():
    """Full CRUD lifecycle: create -> list -> patch -> delete."""
    async with _app_client() as (client, doc_id):
        base = f"/api/v1/documents/{doc_id}/annotations"

        # Create.
        resp = await client.post(base, json=_payload(note="first"))
        assert resp.status_code == 201, resp.text
        created = resp.json()
        ann_id = created["id"]
        assert created["track"] == "original"
        assert created["paragraph_id"] == "para-1-full-text"
        assert created["start_offset"] == 0
        assert created["end_offset"] == 10
        assert created["note"] == "first"
        assert created["color"] == "#fde68a"
        assert "created_at" in created and "updated_at" in created

        # List contains it.
        resp = await client.get(base)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == ann_id

        # Patch color + note.
        resp = await client.patch(f"{base}/{ann_id}", json={"color": "#fecaca", "note": "updated note"})
        assert resp.status_code == 200, resp.text
        patched = resp.json()
        assert patched["color"] == "#fecaca"
        assert patched["note"] == "updated note"
        assert patched["id"] == ann_id

        # List reflects the update.
        resp = await client.get(base)
        assert resp.json()["items"][0]["note"] == "updated note"

        # Delete.
        resp = await client.delete(f"{base}/{ann_id}")
        assert resp.status_code == 204

        # List is now empty.
        resp = await client.get(base)
        assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_invalid_offsets_rejected():
    """end_offset <= start_offset must yield 422."""
    async with _app_client() as (client, doc_id):
        base = f"/api/v1/documents/{doc_id}/annotations"

        # end_offset == start_offset.
        resp = await client.post(base, json=_payload(start_offset=5, end_offset=5))
        assert resp.status_code == 422, resp.text

        # end_offset < start_offset.
        resp = await client.post(base, json=_payload(start_offset=8, end_offset=3))
        assert resp.status_code == 422, resp.text

        # negative start_offset.
        resp = await client.post(base, json=_payload(start_offset=-1, end_offset=3))
        assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_track_filter():
    """The track query param filters annotations by track."""
    async with _app_client() as (client, doc_id):
        base = f"/api/v1/documents/{doc_id}/annotations"

        resp = await client.post(base, json=_payload(track="original", paragraph_id="p1"))
        assert resp.status_code == 201
        resp = await client.post(base, json=_payload(track="translated", paragraph_id="p2"))
        assert resp.status_code == 201

        # No filter -> both.
        resp = await client.get(base)
        assert len(resp.json()["items"]) == 2

        # Filter original -> one.
        resp = await client.get(f"{base}?track=original")
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["track"] == "original"
        assert items[0]["paragraph_id"] == "p1"

        # Filter translated -> one.
        resp = await client.get(f"{base}?track=translated")
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["track"] == "translated"


@pytest.mark.asyncio
async def test_update_and_delete_unknown_return_404():
    """Patching/deleting a non-existent annotation (or wrong doc) yields 404."""
    async with _app_client() as (client, doc_id):
        base = f"/api/v1/documents/{doc_id}/annotations"
        missing = uuid.uuid4()

        resp = await client.patch(f"{base}/{missing}", json={"note": "x"})
        assert resp.status_code == 404

        resp = await client.delete(f"{base}/{missing}")
        assert resp.status_code == 404
