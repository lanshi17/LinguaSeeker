"""Dataclass contracts shared across the benchmark suite.

These are read by every analyzer and runner. Algorithm logic lives in
``benchmark.core.matching`` and ``benchmark.core.aggregate``; this module
only declares the shapes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["FieldMatch", "EntryMetrics"]


@dataclass
class FieldMatch:
    """Result of matching one expected field against extracted evidence."""

    field_id: str
    expected_value: str
    matched: bool
    extracted_value: str | None = None
    extracted_confidence: float | None = None
    source_span: dict[str, object] | None = None
    match_type: str = "none"  # exact, fuzzy, ontology_ancestor, missing, wrong_value, none
    extra_found_values: list[str] = field(default_factory=list)
    best_score: float | None = None
    source_score: float | None = None
    confidence_score: float | None = None
    agreement_score: float | None = None
    status_score: float | None = None
    verifier_support_score: float | None = None
    target_specificity_score: float | None = None
    contradiction_penalty: float | None = None
    accepted_track: str | None = None
    normalized_value: str | None = None


@dataclass
class EntryMetrics:
    """Metrics for one ground truth entry evaluation."""

    entry_id: str
    gene_symbol: str
    classification: str
    language: str
    moi: str = ""
    run_id: str | None = None
    status_url: str | None = None
    pipeline_status: str = "pending"
    error_message: str | None = None
    last_pipeline_status: str | None = None
    last_current_phase: str | None = None
    duration_s: float = 0.0
    field_matches: list[FieldMatch] = field(default_factory=list)
    article_supported_field_matches: list[FieldMatch] = field(default_factory=list)
    entity_matches: dict[str, bool] = field(default_factory=dict)
    standardization_accuracy: float = 0.0
    track_consistency: float = 0.0
    evidence_count: int = 0
    found_rate: float = 0.0
    grounding_rate: float = 0.0
    # Provenance fields (populated when running against unified dataset)
    source_dataset: str = ""
    original_entry_id: str = ""
