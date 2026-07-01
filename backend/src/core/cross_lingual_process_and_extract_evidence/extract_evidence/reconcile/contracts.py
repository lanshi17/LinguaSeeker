"""Typed contracts for source-grounded cross-track reconcile."""

from __future__ import annotations

from dataclasses import dataclass

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceAlignmentRecord,
    EvidenceExtractionResult,
    EvidenceItem,
    Track,
)


@dataclass(frozen=True)
class ReconcileParams:
    """Tunable constants for deterministic cross-track reconcile."""

    conflict_margin: float = 0.15


@dataclass(frozen=True)
class CandidateScore:
    """Score decomposition for one evidence candidate."""

    field_id: str
    track: Track
    normalized_value: str
    score: float
    source_score: float
    confidence_score: float
    agreement_score: float
    status_score: float
    verifier_support_score: float = 0.0
    target_specificity_score: float = 0.0
    contradiction_penalty: float = 0.0


@dataclass(frozen=True)
class FieldDecision:
    """Decision made for one evidence field."""

    field_id: str
    accepted: EvidenceItem | None
    accepted_score: CandidateScore | None
    rejected: tuple[EvidenceItem, ...] = ()
    requires_review: bool = False
    rationale: str = ""


@dataclass(frozen=True)
class ReconcileOutput:
    """Full reconcile output with the result and auditable decisions."""

    result: EvidenceExtractionResult
    decisions: tuple[FieldDecision, ...]
    alignment_records: tuple[EvidenceAlignmentRecord, ...] = ()
