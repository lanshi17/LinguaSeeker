"""Typed contracts for Phase 4 evidence review and feedback."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import ClassVar, Literal, TypedDict
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class SourceSpanDict(TypedDict, total=False):
    """Structured source span stored in JSONB.

    This is a partial contract — the extraction pipeline may write
    additional keys (e.g. block_type, confidence, source_url).
    total=False allows extra keys at runtime; this TypedDict documents
    the known queryable fields used by the API layer.
    """

    text_snippet: str
    start_offset: int
    end_offset: int
    page: int | None


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
    source_span: SourceSpanDict
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
    processing_run_id: UUID | None
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

    @field_validator("role", mode="before")
    @classmethod
    def validate_role(cls, v: object) -> object:
        """Validate ORM string roles before Literal coercion."""
        if not isinstance(v, str) or v not in {"user", "assistant"}:
            raise ValueError("role must be 'user' or 'assistant'")
        return v


class PatchResultResponse(BaseModel):
    """API response for PATCH /evidence."""

    canonical_evidence_id: UUID
    old_status: ReviewStatus
    new_status: ReviewStatus
    deltas: int
    field_deltas: list[DeltaEntry]


class EvidencePatchRequest(BaseModel):
    """Request body for PATCH /api/v1/evidence/{id}."""

    fields: dict[str, str | list[str] | None] = Field(default_factory=dict)
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

    @model_validator(mode="after")
    def require_fields_or_status(self) -> EvidencePatchRequest:
        """Reject completely empty patches (no fields and no status change)."""
        if not self.fields and self.new_status is None:
            raise ValueError("Provide at least one of 'fields' or 'new_status'")
        return self




class EvidenceSearchResult(BaseModel):
    """A single evidence search result row (pivoted from field-level extractions)."""

    group_id: str
    source_document_id: UUID
    title: str | None = None
    pmid: str | None = None
    doi: str | None = None
    original_document_text: str | None = None
    translated_document_text: str | None = None
    gene: str | None = None
    variant: str | None = None
    disease: str | None = None
    classification: str | None = None
    field_count: int = 0
    avg_confidence: float | None = None
    review_status: str = "provisional"
    canonical_evidence_id: UUID | None = None
    created_at: datetime | None = None


class EvidenceSearchResponse(BaseModel):
    """Response for GET /api/v1/evidence/search."""

    items: list[EvidenceSearchResult]
    total: int
    page: int = 1
    page_size: int = 50


class EvidenceFieldDistribution(BaseModel):
    """Distribution counts for one grouped evidence row."""

    by_category: dict[str, int] = Field(default_factory=dict)
    by_field: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_track: dict[str, int] = Field(default_factory=dict)


class EvidenceGroupItem(BaseModel):
    """One field-level evidence item in a grouped evidence detail view."""

    canonical_evidence_id: UUID
    field_id: str
    field_name: str | None = None
    category: str | None = None
    value: str | None = None
    review_status: str
    confidence: float | None = None
    track: str | None = None
    page: int | None = None


class EvidenceChainHighlight(BaseModel):
    """Highlightable source text for an evidence item on one track."""

    text: str
    highlight_start: int
    highlight_end: int
    page: int | None = None
    source_span: SourceSpanDict = Field(default_factory=dict)


class EvidenceTrackTrace(BaseModel):
    """Original/translated trace pair for one evidence item."""

    canonical_evidence_id: UUID
    field_id: str
    field_name: str | None = None
    original_value: str | None = None
    translated_value: str | None = None
    original: EvidenceChainHighlight | None = None
    translated: EvidenceChainHighlight | None = None
    alignment_confidence: float | None = None


class EvidenceGroupDetailResponse(BaseModel):
    """Detail payload for one grouped evidence row."""

    group_id: str
    source_document_id: UUID
    title: str | None = None
    pmid: str | None = None
    doi: str | None = None
    gene: str | None = None
    variant: str | None = None
    disease: str | None = None
    classification: str | None = None
    item_count: int
    avg_confidence: float | None = None
    distribution: EvidenceFieldDistribution
    items: list[EvidenceGroupItem]
    traces: list[EvidenceTrackTrace]


class LiteratureProfileSummary(BaseModel):
    """Summary row for literature search results."""

    literature_profile_id: UUID
    source_document_id: UUID
    pmid: str | None = None
    doi: str | None = None
    title: str | None = None
    journal: str | None = None
    publication_year: int | None = None
    review_status: str = "provisional"
    overall_confidence: float | None = None
    total_evidence_fields: int = 0
    found_count: int = 0
    evidence_group_count: int = 0
    gene: str | None = None
    variant: str | None = None
    disease: str | None = None
    classification: str | None = None
    created_at: datetime | None = None


class LiteratureSearchResponse(BaseModel):
    """Response for GET /api/v1/literature/search."""

    items: list[LiteratureProfileSummary]
    total: int
    page: int = 1
    page_size: int = 50


class EvidenceFieldItem(BaseModel):
    """One evidence field within a group."""

    canonical_evidence_id: UUID
    field_id: str
    field_name: str | None = None
    category: str | None = None
    value: str | None = None
    confidence: float | None = None
    status: str | None = None
    track: str | None = None


class EvidenceGroupSummaryDict(TypedDict, total=False):
    """Summary fields extracted from an evidence group."""

    gene: str | None
    variant: str | None
    disease: str | None
    classification: str | None


class EvidenceGroupSummary(BaseModel):
    """Summary of an evidence group within a literature profile."""

    group_id: str
    summary: EvidenceGroupSummaryDict = Field(default_factory=dict)
    avg_confidence: float | None = None
    field_count: int = 0
    review_status: str = "provisional"
    fields: list[EvidenceFieldItem] = Field(default_factory=list)


class LiteratureProfileDetailResponse(BaseModel):
    """Response for GET /api/v1/literature/{id}/detail."""

    literature_profile_id: UUID
    source_document_id: UUID
    pmid: str | None = None
    doi: str | None = None
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    journal: str | None = None
    publication_year: int | None = None
    evidence_groups: list[EvidenceGroupSummary] = Field(default_factory=list)
    review_status: str = "provisional"
    review_notes: str | None = None
    overall_confidence: float | None = None
    total_evidence_fields: int = 0
    found_count: int = 0
    not_found_count: int = 0
