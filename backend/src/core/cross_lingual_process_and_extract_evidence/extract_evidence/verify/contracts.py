"""Typed contracts for evidence support verification."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RelationshipLabel(str, Enum):
    """Supported gene-disease relationship labels."""

    CAUSATIVE = "causative"
    ASSOCIATED = "associated"
    SUSCEPTIBILITY = "susceptibility"
    UNCERTAIN = "uncertain"
    DISPUTED = "disputed"
    REFUTED = "refuted"
    NO_RELATIONSHIP = "no_relationship"


@dataclass(frozen=True)
class EvidenceVerificationInput:
    """Verifier input for one evidence candidate."""

    entry_id: str
    field_id: str
    candidate_value: str
    source_snippet: str
    source_precision: str | None
    track: str
    target_gene: str
    target_disease: str
    disease_aliases: tuple[str, ...]
    moi: str


@dataclass(frozen=True)
class EvidenceVerificationResult:
    """Verifier result for one evidence candidate."""

    field_id: str
    recommended_value: str
    support_score: float
    contradiction_score: float
    target_specificity_score: float
    rationale: str
    requires_review: bool

    def __post_init__(self) -> None:
        for field_name in ("support_score", "contradiction_score", "target_specificity_score"):
            value = getattr(self, field_name)
            if value < 0.0 or value > 1.0:
                raise ValueError(f"{field_name} must be between 0.0 and 1.0")
