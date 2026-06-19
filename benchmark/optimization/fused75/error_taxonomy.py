"""Build error taxonomy reports for fused-75 adjudicated evaluation."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from benchmark.optimization.fused75.evaluate_adjudicated import AdjudicatedEntryResult, AdjudicatedFieldResult

_CATEGORIES = (
    "candidate_absent",
    "wrong_boundary",
    "wrong_relationship",
    "unsupported_prediction",
    "normalization_error",
    "not_source_visible_label",
)


@dataclass(frozen=True)
class ErrorTaxonomyReport:
    """Error taxonomy counts and example entry IDs."""

    counts: dict[str, int]
    examples: dict[str, tuple[str, ...]]


def build_error_taxonomy(results: tuple[AdjudicatedEntryResult, ...]) -> ErrorTaxonomyReport:
    """Classify adjudicated field-level failures into coarse error classes."""
    counts = {category: 0 for category in _CATEGORIES}
    examples: dict[str, list[str]] = {category: [] for category in _CATEGORIES}

    for result in results:
        paired = _paired_same_field_errors(result.field_results)
        consumed: set[int] = set()
        for field_id, indices in paired.items():
            category = _paired_category(field_id, result.field_results)
            _add(category, result.entry_id, counts, examples)
            consumed.update(indices)

        for index, field in enumerate(result.field_results):
            if index in consumed or field.outcome == "tp":
                continue
            category = _single_category(field)
            _add(category, result.entry_id, counts, examples)

    return ErrorTaxonomyReport(
        counts=counts,
        examples={category: tuple(values) for category, values in examples.items()},
    )


def _paired_same_field_errors(fields: tuple[AdjudicatedFieldResult, ...]) -> dict[str, tuple[int, ...]]:
    by_field: dict[str, list[int]] = defaultdict(list)
    for index, field in enumerate(fields):
        by_field[field.field_id].append(index)
    paired: dict[str, tuple[int, ...]] = {}
    for field_id, indices in by_field.items():
        outcomes = {fields[index].outcome for index in indices}
        if {"fn", "fp"}.issubset(outcomes):
            paired[field_id] = tuple(indices)
    return paired


def _paired_category(field_id: str, fields: tuple[AdjudicatedFieldResult, ...]) -> str:
    if "variant" in field_id:
        return "normalization_error"
    if "relationship" in field_id:
        return "wrong_relationship"
    return "wrong_boundary"


def _single_category(field: AdjudicatedFieldResult) -> str:
    if field.outcome == "fn":
        return "candidate_absent"
    if field.outcome == "fp":
        return "unsupported_prediction"
    return "not_source_visible_label"


def _add(category: str, entry_id: str, counts: dict[str, int], examples: dict[str, list[str]]) -> None:
    counts[category] += 1
    if entry_id not in examples[category]:
        examples[category].append(entry_id)
