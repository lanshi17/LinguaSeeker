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
from src.utils.text_normalize import SPACE_RE as _SPACE_RE
from src.utils.text_normalize import normalize_text as _normalize_text
from src.utils.text_normalize import normalize_value as _normalize_value
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
_NEGATION_CUES = {
    "no", "not", "none", "without", "absent", "absence",
    "denies", "denied", "negative", "non",
    "rare", "unrelated", "ruled out", "excluded",
    "failed", "did not", "doesn't", "doesn t", "don't", "don t",
}
# Field-id substrings whose values are quantitative medical evidence. A numeric
# drift in these fields changes clinical interpretation (allele count, frequency,
# segregation/family count, functional assay).
_NUMERIC_FIELD_HINTS = (
    "frequency",
    "allele",
    "count",
    "segregation",
    "family",
    "pedigree",
    "penetrance",
    "assay",
    "functional",
    "age",
    "onset",
    "variant",
)


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
    # Medically-critical drift checks run before the partial-match heuristic,
    # because a negation flip or a numeric change can co-occur with high token
    # overlap while altering the clinical claim.
    if _is_negation_loss(original_value, translated_value):
        return EvidenceAlignmentLabel.DRIFTED, EvidenceSupportLabel.CONTRADICTS, "negation_lost_or_gained"
    if _is_numeric_drift(field_id, original_value, translated_value):
        return EvidenceAlignmentLabel.DRIFTED, EvidenceSupportLabel.INSUFFICIENT, "numeric_evidence_changed"
    if _is_relationship_drift(field_id, original_value, translated_value):
        return EvidenceAlignmentLabel.DRIFTED, EvidenceSupportLabel.INSUFFICIENT, "relationship_cue_changed"
    if _is_partial_match(original_value, translated_value):
        return EvidenceAlignmentLabel.PARTIAL, EvidenceSupportLabel.SUPPORTS, "boundary_or_qualifier_difference"
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


def _is_negation_loss(original_value: str, translated_value: str) -> bool:
    """Return True when negation is present on one side but absent on the other.

    Medical evidence is especially sensitive to negation: "no pathogenic
    variant" vs "pathogenic variant" flips the clinical claim. A drift here
    is a contradiction, not a partial match.
    """
    original_negated = _is_negated(original_value)
    translated_negated = _is_negated(translated_value)
    return original_negated != translated_negated


def _is_negated(value: str) -> bool:
    """Return True if the value text carries an explicit negation cue."""
    tokens = set(_SPACE_RE.sub(" ", value).split())
    if tokens & _NEGATION_CUES:
        return True
    lowered = f" {value} "
    return any(cue in lowered for cue in ("no ", "not ", "n't ", "without ", "absence of"))


def _is_numeric_drift(field_id: str, original_value: str, translated_value: str) -> bool:
    """Return True when a numeric medical value changed across tracks.

    Catches drifts in allele count, frequency, family/segregation count,
    penetrance, assay values, etc. — fields where a numeric change alters the
    evidence strength. Returns False if both sides share the same number set.
    """
    if not _is_numeric_field(field_id):
        # Still detect numeric drift when the values themselves are dominated
        # by numbers (e.g. a frequency string on a generic field).
        if not (_is_number_dominated(original_value) and _is_number_dominated(translated_value)):
            return False
    original_numbers = _extract_numbers(original_value)
    translated_numbers = _extract_numbers(translated_value)
    if not original_numbers and not translated_numbers:
        return False
    return set(original_numbers) != set(translated_numbers)


def _is_numeric_field(field_id: str) -> bool:
    lowered = field_id.casefold()
    return any(hint in lowered for hint in _NUMERIC_FIELD_HINTS)


_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _extract_numbers(value: str) -> tuple[str, ...]:
    return tuple(_NUMBER_RE.findall(value))


def _is_number_dominated(value: str) -> bool:
    numbers = _extract_numbers(value)
    if not numbers:
        return False
    digits = sum(len(n) for n in numbers)
    return digits >= len(value.strip()) * 0.5


def _value_text(item: EvidenceItem | None) -> str:
    if item is None or item.value is None:
        return ""
    if isinstance(item.value, list):
        return "|".join(str(value) for value in item.value)
    return str(item.value)




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
