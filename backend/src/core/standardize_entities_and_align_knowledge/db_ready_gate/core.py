"""Pure DB-ready evidence candidate gate logic."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from src.core.standardize_entities_and_align_knowledge.db_ready_gate.contracts import (
    DEFAULT_DB_READY_GATE_POLICY,
    DbReadyCandidate,
    DbReadyDecision,
    DbReadyGatePolicy,
    DbReadyGateReport,
    DbReadyGateResult,
    DbReadyRejectReason,
    DbReadyRejectReasonCount,
    DbReadySourceSpan,
)


_SOURCE_TEXT_KEYS = (
    "text",
    "raw_text",
    "quote",
    "source_quote",
    "text_snippet",
    "source_text",
    "matched_text",
)

_SOURCE_LOCATION_KEY_GROUPS = (
    ("page", "block_index"),
    ("page_number", "block_index"),
    ("page", "start_offset", "end_offset"),
    ("page_number", "start_offset", "end_offset"),
)


def evaluate_db_ready_candidate(
    candidate: DbReadyCandidate,
    policy: DbReadyGatePolicy = DEFAULT_DB_READY_GATE_POLICY,
) -> DbReadyGateResult:
    """Evaluate whether one evidence candidate is DB-ready."""
    reasons: list[DbReadyRejectReason] = []

    if not candidate.source_document_id.strip():
        reasons.append(DbReadyRejectReason.MISSING_SOURCE_DOCUMENT_ID)
    if not candidate.processing_run_id.strip():
        reasons.append(DbReadyRejectReason.MISSING_PROCESSING_RUN_ID)
    if not candidate.field_id.strip():
        reasons.append(DbReadyRejectReason.MISSING_FIELD_ID)
    if policy.require_group_id and not candidate.group_id.strip():
        reasons.append(DbReadyRejectReason.MISSING_GROUP_ID)

    if _normalized(candidate.status) not in _normalized_set(policy.accepted_statuses):
        reasons.append(DbReadyRejectReason.UNSUPPORTED_STATUS)

    review_status = _normalized(candidate.review_status or "")
    if review_status and review_status in _normalized_set(policy.rejected_review_statuses):
        reasons.append(DbReadyRejectReason.REVIEW_REJECTED)

    if policy.require_source_support and not _has_source_support(candidate):
        reasons.append(DbReadyRejectReason.MISSING_SOURCE_SUPPORT)

    if policy.require_any_entity_binding and not _has_any_entity_binding(candidate):
        reasons.append(DbReadyRejectReason.MISSING_ENTITY_BINDING)

    field_id = candidate.field_id.strip()
    if _requires_gene(field_id, policy) and not _has_value(candidate.gene_id):
        reasons.append(DbReadyRejectReason.MISSING_GENE_BINDING)
    if _requires_variant(field_id, policy) and not _has_value(candidate.variant_id):
        reasons.append(DbReadyRejectReason.MISSING_VARIANT_BINDING)
    if _requires_disease(field_id, policy) and not _has_value(candidate.disease_id):
        reasons.append(DbReadyRejectReason.MISSING_DISEASE_BINDING)

    decision = DbReadyDecision.REJECTED if reasons else DbReadyDecision.ACCEPTED
    return DbReadyGateResult(candidate=candidate, decision=decision, reasons=tuple(reasons))


def evaluate_db_ready_candidates(
    candidates: Iterable[DbReadyCandidate],
    policy: DbReadyGatePolicy = DEFAULT_DB_READY_GATE_POLICY,
) -> DbReadyGateReport:
    """Evaluate a batch of candidates and return aggregate rejection counts."""
    results = tuple(evaluate_db_ready_candidate(candidate, policy) for candidate in candidates)
    accepted_count = sum(1 for result in results if result.decision == DbReadyDecision.ACCEPTED)
    reason_counter: Counter[DbReadyRejectReason] = Counter()
    for result in results:
        reason_counter.update(result.reasons)
    rejection_counts = tuple(
        DbReadyRejectReasonCount(reason=reason, count=reason_counter[reason])
        for reason in sorted(reason_counter, key=lambda item: item.value)
    )
    return DbReadyGateReport(
        results=results,
        accepted_count=accepted_count,
        rejected_count=len(results) - accepted_count,
        rejection_counts=rejection_counts,
    )


def _has_source_support(candidate: DbReadyCandidate) -> bool:
    if candidate.expert_override:
        return True
    span = candidate.source_span
    if span is None:
        return False
    return _has_source_text(span) or _has_source_location(span)


def _has_source_text(span: DbReadySourceSpan) -> bool:
    for key in _SOURCE_TEXT_KEYS:
        value = span.get(key)
        if isinstance(value, str) and value.strip():
            return True
    original = span.get("original_source_span")
    if isinstance(original, dict):
        return _has_source_text(original)
    return False


def _has_source_location(span: DbReadySourceSpan) -> bool:
    for keys in _SOURCE_LOCATION_KEY_GROUPS:
        if all(span.get(key) is not None for key in keys):
            return True
    return False


def _has_any_entity_binding(candidate: DbReadyCandidate) -> bool:
    return bool(
        candidate.normalized_entity_ids
        or _has_value(candidate.gene_id)
        or _has_value(candidate.variant_id)
        or _has_value(candidate.disease_id),
    )


def _requires_gene(field_id: str, policy: DbReadyGatePolicy) -> bool:
    return field_id in policy.gene_required_field_ids


def _requires_variant(field_id: str, policy: DbReadyGatePolicy) -> bool:
    return field_id in policy.variant_required_field_ids or field_id.startswith("A.variant_")


def _requires_disease(field_id: str, policy: DbReadyGatePolicy) -> bool:
    return field_id in policy.disease_required_field_ids


def _has_value(value: str | None) -> bool:
    return bool(value and value.strip())


def _normalized(value: str) -> str:
    return value.strip().casefold()


def _normalized_set(values: tuple[str, ...]) -> frozenset[str]:
    return frozenset(_normalized(value) for value in values)
