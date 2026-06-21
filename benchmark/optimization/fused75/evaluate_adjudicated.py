"""Evaluate pipeline outputs against fused-75 source-visible adjudication."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol

from benchmark.optimization.fused75.adjudication_contracts import Fused75EntryAdjudication


class ExtractedItem(Protocol):
    """Minimal pipeline item protocol consumed by the adjudicated evaluator."""

    field_id: str
    value: str


@dataclass(frozen=True)
class AdjudicatedMetric:
    """Precision/recall/F1 for source-visible adjudication."""

    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int


@dataclass(frozen=True)
class AdjudicatedFieldResult:
    """One adjudicated field comparison result."""

    field_id: str
    expected_value: str
    extracted_value: str | None
    outcome: str


@dataclass(frozen=True)
class AdjudicatedEntryResult:
    """Evaluation result for one adjudicated fused-75 entry."""

    entry_id: str
    metric: AdjudicatedMetric
    field_results: tuple[AdjudicatedFieldResult, ...]


def evaluate_adjudicated_entry(
    adjudication: Fused75EntryAdjudication,
    *,
    extracted_items: tuple[ExtractedItem, ...],
) -> AdjudicatedEntryResult:
    """Evaluate extracted items against source-visible labels only."""
    visible_labels = tuple(label for label in adjudication.labels if label.visibility == "source_visible")
    remaining_items = list(extracted_items)
    field_results: list[AdjudicatedFieldResult] = []
    tp = 0
    fn = 0

    for label in visible_labels:
        match_index = _find_matching_item(label.field_id, label.expected_value, remaining_items)
        if match_index is None:
            field_results.append(
                AdjudicatedFieldResult(
                    field_id=label.field_id,
                    expected_value=label.expected_value,
                    extracted_value=None,
                    outcome="fn",
                )
            )
            fn += 1
            continue

        item = remaining_items.pop(match_index)
        field_results.append(
            AdjudicatedFieldResult(
                field_id=label.field_id,
                expected_value=label.expected_value,
                extracted_value=str(item.value),
                outcome="tp",
            )
        )
        tp += 1

    fp = len(remaining_items)
    for item in remaining_items:
        field_results.append(
            AdjudicatedFieldResult(
                field_id=item.field_id,
                expected_value="",
                extracted_value=str(item.value),
                outcome="fp",
            )
        )

    metric = _metric(tp=tp, fp=fp, fn=fn)
    return AdjudicatedEntryResult(
        entry_id=adjudication.entry_id,
        metric=metric,
        field_results=tuple(field_results),
    )


def _find_matching_item(field_id: str, expected_value: str, items: list[ExtractedItem]) -> int | None:
    for index, item in enumerate(items):
        if item.field_id == field_id and _matches(field_id, expected_value, str(item.value)):
            return index
    return None


def _matches(field_id: str, expected_value: str, extracted_value: str) -> bool:
    expected = _field_normalize(field_id, expected_value)
    extracted = _field_normalize(field_id, extracted_value)
    return expected == extracted


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _field_normalize(field_id: str, value: str) -> str:
    normalized = _normalize(value).lower()
    if field_id == "A.variant_hgvs_p":
        return re.sub(r"^p\.\(([^)]+)\)$", r"p.\1", normalized)
    if field_id == "A.variant_type":
        return re.sub(r"\s+(mutation|variant)$", "", normalized)
    if field_id == "B.mode_of_inheritance_reported":
        return _normalize_inheritance(normalized)
    if field_id == "B.disease_diagnosis":
        return _normalize_disease(normalized)
    return normalized


def _normalize_inheritance(value: str) -> str:
    aliases = {
        "ar": "autosomal recessive",
        "autosomal recessive": "autosomal recessive",
        "ad": "autosomal dominant",
        "autosomal dominant": "autosomal dominant",
        "xl": "x-linked",
        "x linked": "x-linked",
        "x-linked": "x-linked",
    }
    return aliases.get(value, value)


def _normalize_disease(value: str) -> str:
    without_parentheticals = re.sub(r"\s*\([^)]*\)", "", value)
    without_hyphen = without_parentheticals.replace("-", " ")
    return _normalize(without_hyphen).lower()


def _metric(*, tp: int, fp: int, fn: int) -> AdjudicatedMetric:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return AdjudicatedMetric(
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        tp=tp,
        fp=fp,
        fn=fn,
    )
