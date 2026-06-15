"""Deterministic original/translation evidence alignment helpers."""
from __future__ import annotations

import re

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceAlignmentLabel,
    EvidenceAlignmentRecord,
    EvidenceExtractionResult,
    EvidenceItem,
    EvidenceStatus,
    EvidenceSupportLabel,
)


_SPACE_RE = re.compile(r"\s+")
_RELATIONSHIP_VALUES = {
    "associated",
    "association",
    "causative",
    "cause",
    "causal",
    "disputed",
    "no relationship",
    "no_relationship",
    "refuted",
    "susceptibility",
    "uncertain",
}
_CONFLICT_VALUES = {
    "benign",
    "likely benign",
    "pathogenic",
    "likely pathogenic",
    "refuted",
    "causative",
    "no relationship",
    "no_relationship",
}


def build_alignment_records(
    original: EvidenceExtractionResult,
    translated: EvidenceExtractionResult,
    *,
    entry_id: str = "",
) -> tuple[EvidenceAlignmentRecord, ...]:
    """Build field-level alignment records from dual-track extraction results."""
    original_items = _best_items_by_field(original.evidence_items)
    translated_items = _best_items_by_field(translated.evidence_items)
    records: list[EvidenceAlignmentRecord] = []
    for field_id in sorted(set(original_items) | set(translated_items)):
        original_item = original_items.get(field_id)
        translated_item = translated_items.get(field_id)
        records.append(_build_record(entry_id, field_id, original_item, translated_item))
    return tuple(records)


def is_alignment_acceptable(record: EvidenceAlignmentRecord) -> bool:
    """Return whether a record can pass the traceability/alignment gate."""
    if not record.original_span_id:
        return False
    if record.alignment_label in {EvidenceAlignmentLabel.DRIFTED, EvidenceAlignmentLabel.CONFLICT}:
        return False
    return record.support_label != EvidenceSupportLabel.CONTRADICTS


def _best_items_by_field(items: list[EvidenceItem]) -> dict[str, EvidenceItem]:
    found_items = [item for item in items if item.status == EvidenceStatus.FOUND]
    best: dict[str, EvidenceItem] = {}
    for item in found_items:
        current = best.get(item.field_id)
        if current is None or _item_rank(item) > _item_rank(current):
            best[item.field_id] = item
    return best


def _item_rank(item: EvidenceItem) -> tuple[float, int, str]:
    source_rank = 1 if item.source is not None else 0
    return item.confidence, source_rank, _normalize_value(item.value)


def _build_record(
    entry_id: str,
    field_id: str,
    original_item: EvidenceItem | None,
    translated_item: EvidenceItem | None,
) -> EvidenceAlignmentRecord:
    original_value = _value_text(original_item)
    translated_value = _value_text(translated_item)
    original_normalized = _normalize_text(original_value)
    translated_normalized = _normalize_text(translated_value)
    alignment_label, support_label, drift_reason = _alignment_decision(
        field_id,
        original_normalized,
        translated_normalized,
    )
    return EvidenceAlignmentRecord(
        entry_id=entry_id,
        field_id=field_id,
        original_value=original_value or None,
        translated_value=translated_value or None,
        normalized_value=original_normalized or translated_normalized,
        original_span_id=_span_id(original_item),
        translated_span_id=_span_id(translated_item),
        alignment_label=alignment_label,
        support_label=support_label,
        drift_reason=drift_reason,
        confidence=_combined_confidence(original_item, translated_item),
    )


def _alignment_decision(
    field_id: str,
    original_value: str,
    translated_value: str,
) -> tuple[EvidenceAlignmentLabel, EvidenceSupportLabel, str]:
    if not original_value or not translated_value:
        return EvidenceAlignmentLabel.MISSING, EvidenceSupportLabel.INSUFFICIENT, "single_track_only"
    if original_value == translated_value:
        return EvidenceAlignmentLabel.ALIGNED, EvidenceSupportLabel.SUPPORTS, ""
    if _is_partial_match(original_value, translated_value):
        return EvidenceAlignmentLabel.PARTIAL, EvidenceSupportLabel.SUPPORTS, "boundary_or_qualifier_difference"
    if _is_relationship_drift(field_id, original_value, translated_value):
        return EvidenceAlignmentLabel.DRIFTED, EvidenceSupportLabel.INSUFFICIENT, "relationship_cue_changed"
    if _is_conflict(original_value, translated_value):
        return EvidenceAlignmentLabel.CONFLICT, EvidenceSupportLabel.CONTRADICTS, "mutually_exclusive_values"
    return EvidenceAlignmentLabel.CONFLICT, EvidenceSupportLabel.CONTRADICTS, "value_mismatch"


def _is_partial_match(left: str, right: str) -> bool:
    if left in right or right in left:
        return True
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return False
    overlap = len(left_tokens & right_tokens) / min(len(left_tokens), len(right_tokens))
    return overlap >= 0.75


def _is_relationship_drift(field_id: str, original_value: str, translated_value: str) -> bool:
    if "relationship" not in field_id:
        return False
    return original_value in _RELATIONSHIP_VALUES and translated_value in _RELATIONSHIP_VALUES


def _is_conflict(original_value: str, translated_value: str) -> bool:
    return original_value in _CONFLICT_VALUES and translated_value in _CONFLICT_VALUES


def _value_text(item: EvidenceItem | None) -> str:
    if item is None or item.value is None:
        return ""
    if isinstance(item.value, list):
        return "|".join(str(value) for value in item.value)
    return str(item.value)


def _normalize_value(value: str | int | float | bool | list[str] | None) -> str:
    if isinstance(value, list):
        return "|".join(sorted(_normalize_text(str(item)) for item in value if _normalize_text(str(item))))
    if value is None:
        return ""
    return _normalize_text(str(value))


def _normalize_text(value: str) -> str:
    return _SPACE_RE.sub(" ", value.strip()).casefold()


def _span_id(item: EvidenceItem | None) -> str:
    if item is None:
        return ""
    source = item.source or item.raw_source
    return source.span_id if source is not None else ""


def _combined_confidence(original_item: EvidenceItem | None, translated_item: EvidenceItem | None) -> float:
    confidences = [item.confidence for item in (original_item, translated_item) if item is not None]
    if not confidences:
        return 0.0
    return round(sum(confidences) / len(confidences), 4)
