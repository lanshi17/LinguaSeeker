"""Pure feature extractor for learned arbitrator candidate scoring.

Extracts a typed feature vector from existing CandidateScore and internal
candidate objects. No model training or label access.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
    SourcePrecision,
    Track,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.contracts import (
    CandidateScore,
)

_SCORABLE_FIELDS = ("A.gene_symbol", "B.disease_diagnosis", "A.gene_disease_relationship")


@dataclass(frozen=True)
class CandidateFeatureVector:
    """Typed feature vector for one evidence candidate."""

    source_score: float
    has_source: float
    source_is_exact: float
    source_is_corrected: float
    span_length: float
    confidence_score: float
    status_is_found: float
    status_is_not_found: float
    agreement_score: float
    verifier_support_score: float
    target_specificity_score: float
    contradiction_penalty: float
    no_contradiction: float
    field_is_gene: float
    field_is_disease: float
    field_is_relationship: float
    track_is_original: float
    source_x_agreement: float
    verifier_x_no_contradiction: float
    target_x_verifier: float
    source_x_verifier: float

    def to_list(self) -> list[float]:
        return [
            self.source_score,
            self.has_source,
            self.source_is_exact,
            self.source_is_corrected,
            self.span_length,
            self.confidence_score,
            self.status_is_found,
            self.status_is_not_found,
            self.agreement_score,
            self.verifier_support_score,
            self.target_specificity_score,
            self.contradiction_penalty,
            self.no_contradiction,
            self.field_is_gene,
            self.field_is_disease,
            self.field_is_relationship,
            self.track_is_original,
            self.source_x_agreement,
            self.verifier_x_no_contradiction,
            self.target_x_verifier,
            self.source_x_verifier,
        ]

    @staticmethod
    def feature_names() -> tuple[str, ...]:
        return (
            "source_score",
            "has_source",
            "source_is_exact",
            "source_is_corrected",
            "span_length",
            "confidence_score",
            "status_is_found",
            "status_is_not_found",
            "agreement_score",
            "verifier_support_score",
            "target_specificity_score",
            "contradiction_penalty",
            "no_contradiction",
            "field_is_gene",
            "field_is_disease",
            "field_is_relationship",
            "track_is_original",
            "source_x_agreement",
            "verifier_x_no_contradiction",
            "target_x_verifier",
            "source_x_verifier",
        )


def extract_features(
    score: CandidateScore,
    item: EvidenceItem,
    track: Track,
) -> CandidateFeatureVector:
    """Extract a feature vector from a scored candidate."""
    source = item.source or item.raw_source
    has_source = 1.0 if source is not None else 0.0
    source_is_exact = 1.0 if source is not None and source.source_precision == SourcePrecision.EXACT else 0.0
    source_is_corrected = (
        1.0 if source is not None and source.source_precision == SourcePrecision.CORRECTED else 0.0
    )
    span_length = _span_length(source) if source is not None else 0.0

    status_is_found = 1.0 if item.status == EvidenceStatus.FOUND else 0.0
    status_is_not_found = 1.0 if item.status == EvidenceStatus.NOT_FOUND else 0.0

    no_contradiction = 1.0 - min(score.contradiction_penalty, 1.0)
    field_is_gene = 1.0 if score.field_id == "A.gene_symbol" else 0.0
    field_is_disease = 1.0 if score.field_id == "B.disease_diagnosis" else 0.0
    field_is_relationship = 1.0 if score.field_id == "A.gene_disease_relationship" else 0.0
    track_is_original = 1.0 if track == Track.ORIGINAL else 0.0

    return CandidateFeatureVector(
        source_score=score.source_score,
        has_source=has_source,
        source_is_exact=source_is_exact,
        source_is_corrected=source_is_corrected,
        span_length=span_length,
        confidence_score=score.confidence_score,
        status_is_found=status_is_found,
        status_is_not_found=status_is_not_found,
        agreement_score=score.agreement_score,
        verifier_support_score=score.verifier_support_score,
        target_specificity_score=score.target_specificity_score,
        contradiction_penalty=score.contradiction_penalty,
        no_contradiction=no_contradiction,
        field_is_gene=field_is_gene,
        field_is_disease=field_is_disease,
        field_is_relationship=field_is_relationship,
        track_is_original=track_is_original,
        source_x_agreement=score.source_score * score.agreement_score,
        verifier_x_no_contradiction=score.verifier_support_score * no_contradiction,
        target_x_verifier=score.target_specificity_score * score.verifier_support_score,
        source_x_verifier=score.source_score * score.verifier_support_score,
    )


def _span_length(source: object) -> float:
    """Compute normalized span length from source location."""
    start = getattr(source, "start_offset", -1)
    end = getattr(source, "end_offset", -1)
    if start < 0 or end < 0 or end <= start:
        return 0.0
    return min((end - start) / 500.0, 1.0)
