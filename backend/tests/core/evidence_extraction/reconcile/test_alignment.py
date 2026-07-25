"""Tests for original/translation evidence alignment policy."""

from __future__ import annotations

from src.core.evidence_extraction.contracts import (
    EvidenceAlignmentLabel,
    EvidenceAlignmentRecord,
    EvidenceExtractionResult,
    EvidenceExtractionStatus,
    EvidenceItem,
    EvidenceStatus,
    EvidenceSupportLabel,
    SourceLocation,
    Track,
)
from src.core.evidence_extraction.reconcile.alignment import (
    build_alignment_records,
    is_alignment_acceptable,
)


def _record(
    *,
    label: EvidenceAlignmentLabel,
    support: EvidenceSupportLabel,
    original_span_id: str = "original-p1",
) -> EvidenceAlignmentRecord:
    return EvidenceAlignmentRecord(
        entry_id="clingen_000",
        field_id="A.gene_symbol",
        original_value="GENE1",
        translated_value="GENE1",
        normalized_value="gene1",
        original_span_id=original_span_id,
        translated_span_id="translated-p1",
        alignment_label=label,
        support_label=support,
        confidence=0.9,
    )


def _result(track: Track, items: list[EvidenceItem]) -> EvidenceExtractionResult:
    return EvidenceExtractionResult(
        status=EvidenceExtractionStatus.COMPLETED,
        document_id="doc-1",
        track=track,
        evidence_items=items,
    )


def _found_item(field_id: str, value: str, *, confidence: float = 0.9) -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category="evidence",
        field_name=field_id,
        status=EvidenceStatus.FOUND,
        value=value,
        source=SourceLocation(span_id="original-p1", context_type="text", context_ref="c", text_snippet=value),
        confidence=confidence,
    )


def test_alignment_gate_rejects_source_invalid_evidence() -> None:
    record = _record(
        label=EvidenceAlignmentLabel.ALIGNED,
        support=EvidenceSupportLabel.SUPPORTS,
        original_span_id="",
    )

    assert is_alignment_acceptable(record) is False


def test_alignment_gate_rejects_drifted_or_conflicting_evidence() -> None:
    drifted = _record(label=EvidenceAlignmentLabel.DRIFTED, support=EvidenceSupportLabel.INSUFFICIENT)
    conflict = _record(label=EvidenceAlignmentLabel.CONFLICT, support=EvidenceSupportLabel.CONTRADICTS)

    assert is_alignment_acceptable(drifted) is False
    assert is_alignment_acceptable(conflict) is False


def test_alignment_gate_accepts_source_only_missing_translation() -> None:
    record = _record(label=EvidenceAlignmentLabel.MISSING, support=EvidenceSupportLabel.INSUFFICIENT)

    assert is_alignment_acceptable(record) is True


def test_negation_loss_is_detected_as_drifted_contradiction() -> None:
    """Translation dropping/gaining negation flips the clinical claim."""
    records = build_alignment_records(
        _result(Track.ORIGINAL, [_found_item("A.disease_diagnosis", "no pathogenic variant")]),
        _result(Track.TRANSLATED, [_found_item("A.disease_diagnosis", "pathogenic variant")]),
        entry_id="clingen_000",
    )
    record = records[0]
    assert record.alignment_label == EvidenceAlignmentLabel.DRIFTED
    assert record.support_label == EvidenceSupportLabel.CONTRADICTS
    assert record.drift_reason == "negation_lost_or_gained"


def test_negation_preserved_is_not_flagged() -> None:
    """Both sides negated (same polarity) is not a negation drift."""
    records = build_alignment_records(
        _result(Track.ORIGINAL, [_found_item("A.disease_diagnosis", "no pathogenic variant")]),
        _result(Track.TRANSLATED, [_found_item("A.disease_diagnosis", "not pathogenic variant")]),
        entry_id="clingen_000",
    )
    record = records[0]
    # Same negation polarity; values differ only in cue wording → partial/aligned, not drift.
    assert record.alignment_label != EvidenceAlignmentLabel.DRIFTED


def test_numeric_drift_on_frequency_field_is_detected() -> None:
    """Allele frequency changing across tracks is medical-evidence drift."""
    records = build_alignment_records(
        _result(Track.ORIGINAL, [_found_item("B.population_frequency", "0.001")]),
        _result(Track.TRANSLATED, [_found_item("B.population_frequency", "0.05")]),
        entry_id="clingen_000",
    )
    record = records[0]
    assert record.alignment_label == EvidenceAlignmentLabel.DRIFTED
    assert record.drift_reason == "numeric_evidence_changed"


def test_numeric_drift_on_segregation_count_is_detected() -> None:
    """Family/segregation count changing across tracks is medical-evidence drift."""
    records = build_alignment_records(
        _result(Track.ORIGINAL, [_found_item("B.segregation_count", "3 affected family members")]),
        _result(Track.TRANSLATED, [_found_item("B.segregation_count", "13 affected family members")]),
        entry_id="clingen_000",
    )
    record = records[0]
    assert record.alignment_label == EvidenceAlignmentLabel.DRIFTED
    assert record.drift_reason == "numeric_evidence_changed"


def test_numeric_value_preserved_is_not_flagged() -> None:
    """Same frequency value, different surrounding wording, is not numeric drift."""
    records = build_alignment_records(
        _result(Track.ORIGINAL, [_found_item("B.population_frequency", "frequency 0.001")]),
        _result(Track.TRANSLATED, [_found_item("B.population_frequency", "allele freq 0.001")]),
        entry_id="clingen_000",
    )
    record = records[0]
    assert record.alignment_label != EvidenceAlignmentLabel.DRIFTED


def test_non_numeric_text_mismatch_falls_back_to_conflict() -> None:
    """Non-numeric, non-negated value mismatch is still conflict, not drift."""
    records = build_alignment_records(
        _result(Track.ORIGINAL, [_found_item("A.gene_symbol", "BRCA1")]),
        _result(Track.TRANSLATED, [_found_item("A.gene_symbol", "TP53")]),
        entry_id="clingen_000",
    )
    record = records[0]
    assert record.alignment_label == EvidenceAlignmentLabel.CONFLICT
    assert record.drift_reason == "value_mismatch"
