"""Typed contracts for Phase 4 evidence review and feedback."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ReviewStatus(str, Enum):
    """Evidence review state machine."""

    PROVISIONAL = "provisional"
    APPROVED = "approved"
    CORRECTED = "corrected"
    REJECTED = "rejected"


class TargetType(str, Enum):
    """Review feedback target types.

    P0 implements: evidence_item, entity, missed_evidence.
    Others are declared but not implemented.
    """

    EVIDENCE_ITEM = "evidence_item"
    ENTITY = "entity"
    MISSED_EVIDENCE = "missed_evidence"
    TASK = "task"
    NATIVE_EXTRACTION = "native_extraction"
    TRANSLATED_EXTRACTION = "translated_extraction"
    TRANSLATION = "translation"
    FUSION = "fusion"
    REPORT = "report"


class EvidenceCardPayload(BaseModel):
    """Predefined schema for evidence card active_payload.

    Used for delta diff operations. Field list is fixed; arbitrary
    field paths are rejected to prevent injection.
    """

    gene: str | None = None
    variant: str | None = None
    phenotype: str | None = None
    disease: str | None = None
    classification: str | None = None
    evidence_strength: str | None = None
    evidence_type: str | None = None
    functional_impact: str | None = None
    inheritance_pattern: str | None = None
    zygosity: str | None = None
    references: list[str] = Field(default_factory=list)
    summary: str | None = None

    # Fixed field list for delta diff operations
    DIFF_FIELDS: ClassVar[tuple[str, ...]] = (
        "gene",
        "variant",
        "phenotype",
        "disease",
        "classification",
        "evidence_strength",
        "evidence_type",
        "functional_impact",
        "inheritance_pattern",
        "zygosity",
        "references",
        "summary",
    )


class DeltaEntry(BaseModel):
    """Single field change in a review audit event."""

    field: str
    old_value: str | list[str] | None
    new_value: str | list[str] | None

    @field_validator("field")
    @classmethod
    def validate_field_name(cls, v: str) -> str:
        """Reject arbitrary field paths to prevent injection."""
        if v not in EvidenceCardPayload.DIFF_FIELDS:
            raise ValueError(
                f"Invalid field '{v}'. Must be one of {EvidenceCardPayload.DIFF_FIELDS}"
            )
        return v


class ReviewAuditEventResponse(BaseModel):
    """API response for a review audit event."""

    review_event_id: UUID
    canonical_evidence_id: UUID
    reviewer_id: UUID | None
    target_type: TargetType
    old_status: ReviewStatus | None
    new_status: ReviewStatus | None
    field_deltas: list[DeltaEntry]
    change_reason: str | None
    created_at: datetime


class TrackSpan(BaseModel):
    """Single-track source span with highlight context."""

    track: Literal["original", "translated"]
    source_span: dict  # Raw source_span JSONB
    block_text: str
    highlight_start: int
    highlight_end: int
    page: int | None = None


class BilingualSpan(BaseModel):
    """Cross-track bilingual traceability result."""

    canonical_evidence_id: UUID
    original_track: TrackSpan | None
    translated_track: TrackSpan | None
    alignment_confidence: float | None = None


class ChatSessionResponse(BaseModel):
    """API response for a chat session."""

    chat_session_id: UUID
    processing_run_id: UUID
    user_id: UUID | None
    created_at: datetime
    message_count: int = 0


class ChatMessageResponse(BaseModel):
    """API response for a chat message."""

    message_id: UUID
    chat_session_id: UUID
    role: Literal["user", "assistant"]
    content: str
    evidence_id: UUID | None
    entity_id: UUID | None
    created_at: datetime


class EvidencePatchRequest(BaseModel):
    """Request body for PATCH /api/v1/evidence/{id}."""

    fields: dict[str, str | list[str] | None] = Field(..., min_length=1)
    change_reason: str | None = None
    new_status: ReviewStatus | None = None

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, v: dict[str, str | list[str] | None]) -> dict:
        """Ensure all field names are in DIFF_FIELDS."""
        invalid = set(v.keys()) - set(EvidenceCardPayload.DIFF_FIELDS)
        if invalid:
            raise ValueError(
                f"Invalid fields: {invalid}. Must be subset of {EvidenceCardPayload.DIFF_FIELDS}"
            )
        return v
