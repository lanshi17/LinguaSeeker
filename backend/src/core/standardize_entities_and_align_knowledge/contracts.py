"""Typed contracts for Phase 3 entity standardization."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EntityType(str, Enum):
    """Supported biomedical entity types for Phase 3 matching."""

    GENE = "gene"
    DISEASE = "disease"
    PHENOTYPE = "phenotype"
    VARIANT = "variant"


class BindingRole(str, Enum):
    """Evidence binding roles used for canonical scope calculation."""

    SUBJECT = "subject"
    TARGET = "target"
    CONTEXT = "context"
    MENTION = "mention"


class MatchStatus(str, Enum):
    """Deterministic match outcomes for standardization candidates."""

    STANDARDIZED = "standardized"
    UNMAPPED = "unmapped"
    AMBIGUOUS = "ambiguous"


class MatchMethod(str, Enum):
    """How an entity match was produced."""

    PRECISE = "precise"
    SIMILARITY = "similarity"


class CanonicalStatusRank(str, Enum):
    """Canonical evidence precedence ordered as symbolic status labels."""

    FOUND = "found"
    SOURCE_INVALID = "source_invalid"
    OCR_GAP = "ocr_gap"
    TABLE_UNGROUNDED = "table_ungrounded"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class StandardizationCandidate:
    """Typed entity mention extracted for deterministic standardization."""

    candidate_id: str
    entity_type: EntityType
    role: BindingRole
    raw_text: str
    chain_id: str
    track: str
    field_id: str = ""
    context: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TerminologyCandidate:
    """Resolved terminology alias candidate returned by repository lookups."""

    entry_id: str
    entity_type: EntityType
    source_db: str
    external_id: str
    display_name: str
    normalized_alias: str
    alias_type: str
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SimilarityCandidate:
    """Semantic retrieval candidate returned from pgvector and rerank."""

    terminology: TerminologyCandidate
    embedding_text: str
    vector_distance: float
    rerank_score: float | None = None


@dataclass(frozen=True)
class EntityMatch:
    """Resolved or unresolved standardization result for one candidate."""

    candidate: StandardizationCandidate
    status: MatchStatus
    external_id: str | None
    display_name: str
    terminology_candidates: tuple[TerminologyCandidate, ...] = ()
    rationale: str = ""
    match_method: MatchMethod = MatchMethod.PRECISE
    similarity_score: float | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StandardizationInput:
    """Service boundary input for one Phase 3 processing run."""

    document_id: str
    source_document_id: str
    processing_run_id: str
    candidates: tuple[StandardizationCandidate, ...]
    evidence_items: tuple[Any, ...]
    track_payloads: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StandardizationResult:
    """Summary result for one standardization run."""

    document_id: str
    match_count: int
    standardized_count: int
    ambiguous_count: int
    unmapped_count: int
    normalized_entity_ids: tuple[str, ...]
