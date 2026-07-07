"""Typed contracts for DB-ready evidence candidate gating."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypedDict


class DbReadySourceSpan(TypedDict, total=False):
    """Recoverable source support carried by an evidence candidate."""

    text: str
    raw_text: str
    quote: str
    source_quote: str
    text_snippet: str
    source_text: str
    matched_text: str
    page: int
    page_number: int
    block_index: int
    start_offset: int
    end_offset: int
    source_precision: str
    original_source_span: object


class DbReadyDecision(str, Enum):
    """DB-ready gate decision for one candidate."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"


class DbReadyRejectReason(str, Enum):
    """Machine-readable reason a candidate is not DB-ready."""

    MISSING_SOURCE_DOCUMENT_ID = "missing_source_document_id"
    MISSING_PROCESSING_RUN_ID = "missing_processing_run_id"
    MISSING_FIELD_ID = "missing_field_id"
    MISSING_GROUP_ID = "missing_group_id"
    UNSUPPORTED_STATUS = "unsupported_status"
    REVIEW_REJECTED = "review_rejected"
    MISSING_SOURCE_SUPPORT = "missing_source_support"
    MISSING_ENTITY_BINDING = "missing_entity_binding"
    MISSING_GENE_BINDING = "missing_gene_binding"
    MISSING_VARIANT_BINDING = "missing_variant_binding"
    MISSING_DISEASE_BINDING = "missing_disease_binding"


DEFAULT_GENE_REQUIRED_FIELD_IDS = (
    "A.gene_symbol",
    "A.gene_disease_relationship",
)

DEFAULT_VARIANT_REQUIRED_FIELD_IDS = (
    "A.variant_hgvs",
    "A.variant_hgvs_c",
    "A.variant_hgvs_g",
    "A.variant_hgvs_p",
    "A.variant_rs_id",
    "A.variant_type",
    "C.de_novo_status",
)

DEFAULT_DISEASE_REQUIRED_FIELD_IDS = (
    "A.gene_disease_relationship",
    "B.disease_diagnosis",
)


@dataclass(frozen=True)
class DbReadyGatePolicy:
    """Configurable rules for judging DB-ready candidate export readiness."""

    accepted_statuses: tuple[str, ...] = ("found",)
    rejected_review_statuses: tuple[str, ...] = ("rejected",)
    gene_required_field_ids: tuple[str, ...] = DEFAULT_GENE_REQUIRED_FIELD_IDS
    variant_required_field_ids: tuple[str, ...] = DEFAULT_VARIANT_REQUIRED_FIELD_IDS
    disease_required_field_ids: tuple[str, ...] = DEFAULT_DISEASE_REQUIRED_FIELD_IDS
    require_group_id: bool = True
    require_source_support: bool = True
    require_any_entity_binding: bool = False


DEFAULT_DB_READY_GATE_POLICY = DbReadyGatePolicy()


@dataclass(frozen=True)
class DbReadyCandidate:
    """One candidate evidence row to evaluate before DB-ready export."""

    candidate_id: str
    source_document_id: str
    processing_run_id: str
    field_id: str
    group_id: str
    status: str
    track: str
    value_text: str | None = None
    source_span: DbReadySourceSpan | None = None
    gene_id: str | None = None
    variant_id: str | None = None
    disease_id: str | None = None
    normalized_entity_ids: tuple[str, ...] = ()
    review_status: str | None = None
    expert_override: bool = False


@dataclass(frozen=True)
class DbReadyGateResult:
    """Gate outcome for one candidate."""

    candidate: DbReadyCandidate
    decision: DbReadyDecision
    reasons: tuple[DbReadyRejectReason, ...] = ()


@dataclass(frozen=True)
class DbReadyRejectReasonCount:
    """Aggregate count for one rejection reason."""

    reason: DbReadyRejectReason
    count: int


@dataclass(frozen=True)
class DbReadyGateReport:
    """Aggregate gate report for a batch of candidates."""

    results: tuple[DbReadyGateResult, ...]
    accepted_count: int
    rejected_count: int
    rejection_counts: tuple[DbReadyRejectReasonCount, ...] = ()
