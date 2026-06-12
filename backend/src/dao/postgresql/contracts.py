"""Typed DAO infrastructure contracts."""
from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, ConfigDict


class AsyncpgServerSettings(TypedDict):
    """asyncpg server settings passed through SQLAlchemy connect args."""

    search_path: str


class AsyncpgConnectArgs(TypedDict):
    """SQLAlchemy asyncpg connection arguments."""

    server_settings: AsyncpgServerSettings


class CanonicalEvidencePayload(BaseModel):
    """Field-level JSONB contract for CanonicalEvidenceItem.active_payload.

    Uses extra="allow" to preserve unknown keys from extraction providers
    (e.g. source spans, confidence scores, block metadata).
    """

    model_config = ConfigDict(extra="allow")

    value: str | list[str] | None = None
    group_id: str | None = None
    track: str | None = None
    field_id: str | None = None
    field_name: str | None = None
    source: dict[str, object] | None = None
    entity_id: str | None = None
