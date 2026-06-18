"""Pure-Python ground-truth matching algorithms.

Carved out of ``benchmark.layer3.evaluate`` during the 2026-06-18 framework
refactor. Behavior must stay byte-identical across the move; tests in
``backend/tests/benchmark/layer3/test_evaluate_matching.py`` cover the
algorithm and run unmodified.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import replace
from typing import Any

from benchmark.core.contracts import EntryMetrics, FieldMatch

__all__ = [
    "normalize_comparison_text",
    "fuzzy_match_value",
    "compare_evidence",
    "mark_expected_fields_missing",
]


_PUNCT_TRANSLATION = str.maketrans({
    "‐": "-",  # ‐ hyphen
    "‑": "-",  # ‑ non-breaking hyphen
    "‒": "-",  # ‒ figure dash
    "–": "-",  # – en dash
    "—": "-",  # — em dash
    "―": "-",  # ― horizontal bar
    "−": "-",  # − minus sign
    "－": "-",  # － fullwidth hyphen-minus
    "‘": "'",  # ' left single quotation mark
    "’": "'",  # ' right single quotation mark
    "“": '"',  # " left double quotation mark
    "”": '"',  # " right double quotation mark
})
_NORMALIZE_CANDIDATE_PUNCT = str.maketrans({
    ",": " ",
    ";": " ",
    ":": " ",
    "，": " ",
    "；": " ",
    "：": " ",
})


def normalize_comparison_text(value: str) -> str:
    """Normalize harmless typography differences for benchmark matching."""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.translate(_PUNCT_TRANSLATION)
    normalized = normalized.translate(_NORMALIZE_CANDIDATE_PUNCT)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def fuzzy_match_value(expected: str, extracted: str) -> bool:
    """Fuzzy value matching with word-overlap for disease names."""
    if not expected or not extracted:
        return False
    exp_norm = normalize_comparison_text(expected)
    ext_norm = normalize_comparison_text(extracted)
    exp_lower = exp_norm.lower()
    ext_lower = ext_norm.lower()

    # Exact (after normalization)
    if exp_lower == ext_lower:
        return True

    # One contains the other
    if exp_lower in ext_lower or ext_lower in exp_lower:
        return True

    # Word overlap ≥ 60% of the expected word set
    exp_words = {w for w in re.split(r"\W+", exp_lower) if w}
    ext_words = {w for w in re.split(r"\W+", ext_lower) if w}
    if exp_words and ext_words:
        overlap = exp_words & ext_words
        if not overlap:
            return False
        if len(overlap) / len(exp_words) >= 0.6:
            return True
    return False


# Fields that benefit from ontology ancestry matching
_DISEASE_FIELDS = {"B.disease_diagnosis", "B.disease_phenotype"}


def compare_evidence(
    expected_fields: list[dict],
    extracted_items: list[dict],
    mondo: Any | None = None,
    expected_standardization: dict[str, str] | None = None,
) -> list[FieldMatch]:
    """Compare expected evidence fields against extracted items.

    When ``mondo`` is provided and a disease field fails fuzzy matching,
    falls back to MONDO ancestry checking: the extracted disease label
    is looked up in MONDO and checked against the expected MONDO ID's
    ancestor chain.
    """
    matches: list[FieldMatch] = []
    expected_mondo_id = (expected_standardization or {}).get("disease", "")

    for expected in expected_fields:
        field_id = expected["field_id"]
        expected_value = str(expected.get("value", ""))

        # Find matching extracted items
        candidates = [
            item for item in extracted_items
            if item.get("field_id") == field_id and item.get("status") == "found"
        ]

        if not candidates:
            matches.append(FieldMatch(
                field_id=field_id,
                expected_value=expected_value,
                matched=False,
                match_type="missing",
            ))
            continue

        # Check each candidate for value match
        best_match: FieldMatch | None = None
        for cand in candidates:
            extracted_value = str(cand.get("value", ""))
            confidence = cand.get("confidence", 0.0)
            source_span = cand.get("source_span") if isinstance(cand.get("source_span"), dict) else None

            expected_norm = normalize_comparison_text(expected_value).lower()
            extracted_norm = normalize_comparison_text(extracted_value).lower()
            if expected_norm == extracted_norm:
                match_type = "exact"
            elif fuzzy_match_value(expected_value, extracted_value):
                match_type = "fuzzy"
            else:
                continue

            candidate_match = FieldMatch(
                field_id=field_id,
                expected_value=expected_value,
                matched=True,
                extracted_value=extracted_value,
                extracted_confidence=confidence,
                source_span=source_span,
                match_type=match_type,
                **_score_components(cand),
            )
            if best_match is None or (match_type == "exact" and best_match.match_type != "exact"):
                best_match = candidate_match

        # Ontology ancestry fallback for disease fields
        if not best_match and mondo and field_id in _DISEASE_FIELDS and expected_mondo_id:
            for cand in candidates:
                extracted_value = str(cand.get("value", ""))
                if mondo.is_label_descendant_of(extracted_value, expected_mondo_id):
                    best_match = FieldMatch(
                        field_id=field_id,
                        expected_value=expected_value,
                        matched=True,
                        extracted_value=extracted_value,
                        extracted_confidence=cand.get("confidence", 0.0),
                        source_span=cand.get("source_span") if isinstance(cand.get("source_span"), dict) else None,
                        match_type="ontology_ancestor",
                        **_score_components(cand),
                    )
                    break

        if best_match:
            extra_values: list[str] = []
            seen_extra_values: set[str] = set()
            for cand in candidates:
                value = str(cand.get("value", ""))
                normalized_value = normalize_comparison_text(value).lower()
                if normalized_value in seen_extra_values:
                    continue
                if value != best_match.extracted_value and not fuzzy_match_value(expected_value, value):
                    seen_extra_values.add(normalized_value)
                    extra_values.append(value)
            matches.append(replace(best_match, extra_found_values=extra_values))
        else:
            # Found field but wrong value
            matches.append(FieldMatch(
                field_id=field_id,
                expected_value=expected_value,
                matched=False,
                extracted_value=str(candidates[0].get("value", "")),
                extracted_confidence=candidates[0].get("confidence", 0.0),
                source_span=candidates[0].get("source_span") if isinstance(candidates[0].get("source_span"), dict) else None,
                match_type="wrong_value",
                **_score_components(candidates[0]),
            ))

    return matches


def _score_components(candidate: dict) -> dict[str, float | str | None]:
    """Copy optional contextual reconcile score components from a benchmark candidate."""
    return {
        "best_score": _optional_float(candidate.get("best_score")),
        "source_score": _optional_float(candidate.get("source_score")),
        "confidence_score": _optional_float(candidate.get("confidence_score")),
        "agreement_score": _optional_float(candidate.get("agreement_score")),
        "status_score": _optional_float(candidate.get("status_score")),
        "verifier_support_score": _optional_float(candidate.get("verifier_support_score")),
        "target_specificity_score": _optional_float(candidate.get("target_specificity_score")),
        "contradiction_penalty": _optional_float(candidate.get("contradiction_penalty")),
        "accepted_track": _optional_string(candidate.get("accepted_track")),
        "normalized_value": _optional_string(candidate.get("normalized_value")),
    }


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def mark_expected_fields_missing(
    metrics: EntryMetrics,
    entry: dict,
    mondo: Any | None = None,
) -> None:
    """Populate missing field matches when no usable extraction result exists."""
    metrics.field_matches = compare_evidence(
        entry.get("expected_evidence", []),
        [],
        mondo=mondo,
        expected_standardization=entry.get("expected_standardization"),
    )
