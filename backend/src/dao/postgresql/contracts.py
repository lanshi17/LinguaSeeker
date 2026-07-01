"""Typed DAO infrastructure contracts."""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class LiteratureProfileRow:
    """Typed return from LiteratureProfileRepository.get_by_document."""

    literature_profile_id: str
    source_document_id: str
    pmid: str | None
    doi: str | None
    title: str | None
    authors: list
    journal: str | None
    publication_year: int | None
    evidence_groups: list
    review_status: str
    review_notes: str | None
    overall_confidence: float | None
    total_evidence_fields: int
    found_count: int
    not_found_count: int
    created_at: str | None
    updated_at: str | None


@dataclass(frozen=True)
class LiteratureProfileSearchItem:
    """Typed return item from LiteratureProfileRepository.search."""

    literature_profile_id: str
    source_document_id: str
    pmid: str | None
    doi: str | None
    title: str | None
    journal: str | None
    publication_year: int | None
    review_status: str
    overall_confidence: float | None
    total_evidence_fields: int
    found_count: int
    evidence_group_count: int
    gene: str | None
    variant: str | None
    disease: str | None
    classification: str | None
    created_at: str | None
