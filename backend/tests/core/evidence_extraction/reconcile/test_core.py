"""Tests for source-grounded cross-track evidence reconcile."""

from __future__ import annotations

from src.core.evidence_extraction.contracts import (
    EvidenceExtractionResult,
    EvidenceExtractionStatus,
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
    SourcePrecision,
    Track,
)
from src.core.evidence_extraction.reconcile.core import reconcile_results


def _source(precision: SourcePrecision) -> SourceLocation:
    return SourceLocation(
        span_id=f"{precision.value}-span",
        page=1,
        start_offset=10,
        end_offset=20,
        context_type="text",
        context_ref="Results",
        text_snippet="grounded evidence",
        source_precision=precision,
    )


def _item(
    *,
    field_id: str = "A.gene_symbol",
    value: str | None = "BRCA1",
    status: EvidenceStatus = EvidenceStatus.FOUND,
    confidence: float = 0.8,
    source: SourceLocation | None = None,
) -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category=field_id.split(".", maxsplit=1)[0],
        field_name=field_id,
        status=status,
        value=value,
        confidence=confidence,
        source=source,
    )


def _result(track: Track, items: list[EvidenceItem]) -> EvidenceExtractionResult:
    return EvidenceExtractionResult(
        status=EvidenceExtractionStatus.COMPLETED,
        document_id="doc-reconcile",
        track=track,
        evidence_items=items,
    )


def test_reconcile_prefers_grounded_candidate_over_ungrounded_higher_confidence() -> None:
    original = _result(
        Track.ORIGINAL,
        [_item(value="BRCA2", confidence=1.0, source=None)],
    )
    translated = _result(
        Track.TRANSLATED,
        [_item(value="BRCA1", confidence=0.4, source=_source(SourcePrecision.EXACT))],
    )

    output = reconcile_results(original, translated)

    assert output.result.track == Track.RECONCILED
    assert output.result.evidence_items[0].value == "BRCA1"
    assert output.decisions[0].accepted_score is not None
    assert output.decisions[0].accepted_score.track == Track.TRANSLATED
    assert output.result.discarded_evidence[0].value == "BRCA2"


def test_reconcile_scores_cross_track_agreement_for_same_normalized_value() -> None:
    original = _result(
        Track.ORIGINAL,
        [_item(value="BRCA1", confidence=0.8, source=_source(SourcePrecision.CORRECTED))],
    )
    translated = _result(
        Track.TRANSLATED,
        [_item(value=" brca1 ", confidence=0.8, source=_source(SourcePrecision.CORRECTED))],
    )

    output = reconcile_results(original, translated)

    assert output.result.evidence_items[0].value == "BRCA1"
    assert output.decisions[0].accepted_score is not None
    assert output.decisions[0].accepted_score.agreement_score == 1.0
    assert "cross-track agreement" in output.result.evidence_items[0].inference_basis


def test_reconcile_marks_small_margin_grounded_conflict_for_review() -> None:
    original = _result(
        Track.ORIGINAL,
        [_item(value="BRCA1", confidence=0.5, source=_source(SourcePrecision.EXACT))],
    )
    translated = _result(
        Track.TRANSLATED,
        [_item(value="BRCA2", confidence=0.8, source=_source(SourcePrecision.CORRECTED))],
    )

    output = reconcile_results(original, translated)

    assert output.result.evidence_items[0].value == "BRCA1"
    assert output.decisions[0].requires_review is True
    assert "manual review" in output.result.evidence_items[0].notes


def test_reconcile_selects_available_grounded_candidate_when_other_track_missing() -> None:
    original = _result(
        Track.ORIGINAL,
        [_item(value="AARS2", confidence=0.7, source=_source(SourcePrecision.AMBIGUOUS))],
    )
    translated = _result(Track.TRANSLATED, [])

    output = reconcile_results(original, translated)

    assert output.result.evidence_items[0].value == "AARS2"
    assert output.decisions[0].requires_review is False


def test_reconcile_uses_deterministic_order_for_equal_ungrounded_scores() -> None:
    original = _result(
        Track.ORIGINAL,
        [_item(value="zeta", confidence=0.5, source=None)],
    )
    translated = _result(
        Track.TRANSLATED,
        [_item(value="alpha", confidence=0.5, source=None)],
    )

    output = reconcile_results(original, translated)

    assert output.result.evidence_items[0].value == "alpha"
    assert output.decisions[0].accepted_score is not None
    assert output.decisions[0].accepted_score.normalized_value == "alpha"
