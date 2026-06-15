"""Tests for original/translation evidence alignment policy."""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceAlignmentLabel,
    EvidenceAlignmentRecord,
    EvidenceSupportLabel,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.alignment import (
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
