"""Tests for the Phase 3 DB-ready candidate gate."""

from __future__ import annotations

from src.core.standardize_entities_and_align_knowledge.db_ready_gate import (
    DbReadyCandidate,
    DbReadyDecision,
    DbReadyGatePolicy,
    DbReadyRejectReason,
    evaluate_db_ready_candidate,
    evaluate_db_ready_candidates,
)


def _candidate(**overrides: object) -> DbReadyCandidate:
    data = {
        "candidate_id": "candidate-1",
        "source_document_id": "source-1",
        "processing_run_id": "run-1",
        "field_id": "A.variant_hgvs_p",
        "group_id": "MECP2|p.R168X",
        "status": "found",
        "track": "original",
        "value_text": "p.R168X",
        "source_span": {"source_quote": "The MECP2 p.R168X variant was identified."},
        "gene_id": "HGNC:6990",
        "variant_id": "ClinVarVariation:11891",
        "disease_id": "MONDO:0010726",
        "normalized_entity_ids": ("gene-entity", "variant-entity"),
    }
    data.update(overrides)
    return DbReadyCandidate(**data)


def test_accepts_source_grounded_variant_candidate_with_bindings() -> None:
    result = evaluate_db_ready_candidate(_candidate())

    assert result.decision == DbReadyDecision.ACCEPTED
    assert result.reasons == ()


def test_accepts_phase2_text_snippet_as_source_support() -> None:
    result = evaluate_db_ready_candidate(_candidate(source_span={"text_snippet": "MECP2 p.R168X was found."}))

    assert result.decision == DbReadyDecision.ACCEPTED


def test_rejects_variant_scoped_field_without_variant_binding() -> None:
    result = evaluate_db_ready_candidate(_candidate(variant_id=None))

    assert result.decision == DbReadyDecision.REJECTED
    assert DbReadyRejectReason.MISSING_VARIANT_BINDING in result.reasons


def test_rejects_candidate_without_source_support_unless_expert_override() -> None:
    rejected = evaluate_db_ready_candidate(_candidate(source_span=None))
    overridden = evaluate_db_ready_candidate(_candidate(source_span=None, expert_override=True))

    assert DbReadyRejectReason.MISSING_SOURCE_SUPPORT in rejected.reasons
    assert overridden.decision == DbReadyDecision.ACCEPTED


def test_rejects_review_rejected_candidate_even_when_other_fields_are_valid() -> None:
    result = evaluate_db_ready_candidate(_candidate(review_status="rejected"))

    assert result.decision == DbReadyDecision.REJECTED
    assert DbReadyRejectReason.REVIEW_REJECTED in result.reasons


def test_custom_policy_can_require_gene_binding_for_additional_fields() -> None:
    policy = DbReadyGatePolicy(gene_required_field_ids=("B.clinical_phenotypes",))
    result = evaluate_db_ready_candidate(
        _candidate(field_id="B.clinical_phenotypes", gene_id=None, variant_id=None),
        policy,
    )

    assert result.decision == DbReadyDecision.REJECTED
    assert DbReadyRejectReason.MISSING_GENE_BINDING in result.reasons
    assert DbReadyRejectReason.MISSING_VARIANT_BINDING not in result.reasons


def test_batch_report_counts_rejection_reasons() -> None:
    report = evaluate_db_ready_candidates(
        (
            _candidate(),
            _candidate(candidate_id="candidate-2", variant_id=None),
            _candidate(candidate_id="candidate-3", status="not_found", source_span=None),
        ),
    )

    counts = {entry.reason: entry.count for entry in report.rejection_counts}
    assert report.accepted_count == 1
    assert report.rejected_count == 2
    assert counts[DbReadyRejectReason.MISSING_VARIANT_BINDING] == 1
    assert counts[DbReadyRejectReason.MISSING_SOURCE_SUPPORT] == 1
    assert counts[DbReadyRejectReason.UNSUPPORTED_STATUS] == 1
