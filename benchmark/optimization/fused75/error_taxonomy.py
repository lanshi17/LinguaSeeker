"""Build error taxonomy reports for fused-75 adjudicated evaluation."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from benchmark.optimization.fused75.adjudication_contracts import Fused75EntryAdjudication
from benchmark.optimization.fused75.evaluate_adjudicated import AdjudicatedEntryResult, AdjudicatedFieldResult
from benchmark.optimization.fused75.run_variant import (
    PipelineRunSplit,
    _load_adjudications,
    _load_items,
    _load_json,
    _resolve_extraction_path,
    _score_field_filter,
)
from benchmark.optimization.fused75.evaluate_adjudicated import evaluate_adjudicated_entry
from benchmark.optimization.fused75.run_contracts import PipelineVariantConfig

_CATEGORIES = (
    "candidate_absent",
    "wrong_boundary",
    "wrong_relationship",
    "unsupported_prediction",
    "normalization_error",
    "not_source_visible_label",
)

_ROOT_CAUSES = (
    "target_span_not_selected",
    "span_selected_field_missing",
    "field_boundary_mismatch",
    "normalization_gap",
    "source_quote_invalid",
    "unsupported_prediction",
)


@dataclass(frozen=True)
class ErrorTaxonomyReport:
    """Error taxonomy counts and example entry IDs."""

    counts: dict[str, int]
    examples: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class DetailedErrorItem:
    """One field-level adjudicated error with source-visible audit context."""

    category: str
    entry_id: str
    expected_value: str
    extracted_value: str | None
    field_id: str
    outcome: str
    source_location: str | None = None
    source_quote: str | None = None


@dataclass(frozen=True)
class DetailedErrorTaxonomyReport:
    """Detailed error taxonomy report."""

    counts: dict[str, int]
    errors: tuple[DetailedErrorItem, ...]


@dataclass(frozen=True)
class FnRootCauseItem:
    """One field-level error with a dev-only root-cause hypothesis."""

    category: str
    entry_id: str
    expected_value: str
    extracted_value: str | None
    field_id: str
    outcome: str
    root_cause: str
    source_location: str | None = None
    source_quote: str | None = None


@dataclass(frozen=True)
class FnRootCauseTaxonomyReport:
    """Root-cause taxonomy for dev false negatives and unsupported predictions."""

    counts: dict[str, int]
    items: tuple[FnRootCauseItem, ...]


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


def build_detailed_error_taxonomy(
    results: tuple[AdjudicatedEntryResult, ...],
    *,
    adjudications: tuple[Fused75EntryAdjudication, ...] = (),
) -> DetailedErrorTaxonomyReport:
    """Build stable field-level error records from adjudicated evaluation results."""
    counts = {category: 0 for category in _CATEGORIES}
    errors: list[DetailedErrorItem] = []
    label_context = _label_context(adjudications)

    for result in results:
        paired = _paired_same_field_errors(result.field_results)
        paired_categories = {
            index: _paired_category(field_id, result.field_results)
            for field_id, indices in paired.items()
            for index in indices
        }
        counted_pair_indices = {indices[0] for indices in paired.values()}
        for index, field in enumerate(result.field_results):
            if field.outcome == "tp":
                continue
            category = paired_categories.get(index, _single_category(field))
            if index not in paired_categories or index in counted_pair_indices:
                counts[category] += 1
            source_quote, source_location = label_context.get((result.entry_id, field.field_id), (None, None))
            errors.append(
                DetailedErrorItem(
                    category=category,
                    entry_id=result.entry_id,
                    expected_value=field.expected_value,
                    extracted_value=field.extracted_value,
                    field_id=field.field_id,
                    outcome=field.outcome,
                    source_location=source_location,
                    source_quote=source_quote,
                )
            )

    return DetailedErrorTaxonomyReport(counts=counts, errors=tuple(errors))


def write_detailed_error_taxonomy_report(report: DetailedErrorTaxonomyReport, output_path: Path) -> None:
    """Write a stable detailed taxonomy JSON report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "counts": {category: report.counts[category] for category in sorted(report.counts)},
        "errors": [asdict(error) for error in report.errors],
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_fn_root_cause_taxonomy(
    report: DetailedErrorTaxonomyReport,
    *,
    artifact_payloads: dict[str, object],
    source_texts: dict[str, str] | None = None,
) -> FnRootCauseTaxonomyReport:
    """Classify field-level failures by likely dev-only root cause."""
    source_texts = source_texts or {}
    counts = {root_cause: 0 for root_cause in _ROOT_CAUSES}
    items: list[FnRootCauseItem] = []

    for error in report.errors:
        if error.outcome == "tp":
            continue
        if error.outcome == "fp" and error.category != "unsupported_prediction":
            continue
        root_cause = _root_cause_for_error(
            error,
            artifact_payload=artifact_payloads.get(error.entry_id),
            source_text=source_texts.get(error.entry_id, ""),
        )
        counts[root_cause] += 1
        items.append(
            FnRootCauseItem(
                category=error.category,
                entry_id=error.entry_id,
                expected_value=error.expected_value,
                extracted_value=error.extracted_value,
                field_id=error.field_id,
                outcome=error.outcome,
                root_cause=root_cause,
                source_location=error.source_location,
                source_quote=error.source_quote,
            )
        )

    return FnRootCauseTaxonomyReport(counts=counts, items=tuple(items))


def write_fn_root_cause_taxonomy_report(report: FnRootCauseTaxonomyReport, output_path: Path) -> None:
    """Write a stable root-cause taxonomy JSON report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "counts": {root_cause: report.counts[root_cause] for root_cause in sorted(report.counts)},
        "items": [asdict(item) for item in report.items],
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_detailed_error_taxonomy(
    *,
    split: PipelineRunSplit,
    config_path: Path,
    adjudication_root: Path,
    fused_ground_truth_root: Path,
    output_path: Path,
    root_cause_output_path: Path | None = None,
    extraction_root: Path = Path("benchmark/optimization/fused75/extractions"),
) -> DetailedErrorTaxonomyReport:
    """Evaluate existing artifacts and write a detailed taxonomy report."""
    config = PipelineVariantConfig.model_validate_json(config_path.read_text(encoding="utf-8"))
    if config.dataset_split != split:
        raise ValueError(f"config dataset_split={config.dataset_split} does not match requested split={split}")
    adjudications = _load_adjudications(split=split, adjudication_root=adjudication_root)
    score_field_filter = _score_field_filter(config)
    results: list[AdjudicatedEntryResult] = []
    artifact_payloads: dict[str, object] = {}
    for adjudication in adjudications:
        extraction_path = _resolve_extraction_path(
            entry_id=adjudication.entry_id,
            extraction_root=extraction_root,
            fused_ground_truth_root=fused_ground_truth_root,
        )
        if extraction_path is None:
            continue
        artifact_payloads[adjudication.entry_id] = _load_json(extraction_path)
        extracted_items = _load_items(extraction_path)
        if score_field_filter == "adjudicated_labels":
            allowed_field_ids = {label.field_id for label in adjudication.labels}
            extracted_items = tuple(item for item in extracted_items if item.field_id in allowed_field_ids)
        results.append(evaluate_adjudicated_entry(adjudication, extracted_items=extracted_items))

    report = build_detailed_error_taxonomy(tuple(results), adjudications=adjudications)
    write_detailed_error_taxonomy_report(report, output_path)
    if root_cause_output_path is not None:
        root_cause_report = build_fn_root_cause_taxonomy(
            report,
            artifact_payloads=artifact_payloads,
            source_texts=_load_source_texts(adjudications),
        )
        write_fn_root_cause_taxonomy_report(root_cause_report, root_cause_output_path)
    return report


def _root_cause_for_error(error: DetailedErrorItem, *, artifact_payload: object, source_text: str) -> str:
    if error.category == "normalization_error":
        return "normalization_gap"
    if error.category in {"wrong_boundary", "wrong_relationship"}:
        return "field_boundary_mismatch"
    if error.outcome == "fp":
        if error.extracted_value and _extracted_item_source_is_invalid(
            artifact_payload,
            field_id=error.field_id,
            value=error.extracted_value,
            source_text=source_text,
        ):
            return "source_quote_invalid"
        return "unsupported_prediction"
    if error.source_quote and _quote_supported_in_artifact(error.source_quote, artifact_payload):
        return "span_selected_field_missing"
    return "target_span_not_selected"


def _quote_supported_in_artifact(source_quote: str, artifact_payload: object) -> bool:
    quote = _normalize_text(source_quote)
    if not quote:
        return False
    for text in _collect_text_snippets(artifact_payload):
        normalized = _normalize_text(text)
        if quote in normalized or normalized in quote:
            return True
    return False


def _extracted_item_source_is_invalid(
    artifact_payload: object,
    *,
    field_id: str,
    value: str,
    source_text: str,
) -> bool:
    if not source_text:
        return False
    source_normalized = _normalize_text(source_text)
    for item in _iter_item_payloads(artifact_payload):
        if str(item.get("field_id", "")) != field_id or str(item.get("value", "")) != value:
            continue
        snippets = tuple(_collect_text_snippets(item.get("source"))) + tuple(_collect_text_snippets(item.get("raw_source")))
        if not snippets:
            return True
        return not any(_normalize_text(snippet) in source_normalized for snippet in snippets)
    return False


def _iter_item_payloads(payload: object) -> tuple[dict[str, object], ...]:
    if not isinstance(payload, dict):
        return ()
    item_groups: list[object] = []
    if isinstance(payload.get("items"), list):
        item_groups.append(payload["items"])
    reconciled = payload.get("reconciled_result")
    if isinstance(reconciled, dict) and isinstance(reconciled.get("evidence_items"), list):
        item_groups.append(reconciled["evidence_items"])
    for track_key in ("original_result", "translated_result"):
        track = payload.get(track_key)
        if isinstance(track, dict) and isinstance(track.get("evidence_items"), list):
            item_groups.append(track["evidence_items"])

    items: list[dict[str, object]] = []
    for group in item_groups:
        if not isinstance(group, list):
            continue
        for item in group:
            if isinstance(item, dict):
                items.append(item)
    return tuple(items)


def _collect_text_snippets(payload: object) -> tuple[str, ...]:
    snippets: list[str] = []
    if isinstance(payload, dict):
        text_snippet = payload.get("text_snippet")
        if isinstance(text_snippet, str):
            snippets.append(text_snippet)
        for value in payload.values():
            snippets.extend(_collect_text_snippets(value))
    elif isinstance(payload, list):
        for value in payload:
            snippets.extend(_collect_text_snippets(value))
    return tuple(snippets)


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _load_source_texts(adjudications: tuple[Fused75EntryAdjudication, ...]) -> dict[str, str]:
    source_texts: dict[str, str] = {}
    for adjudication in adjudications:
        path = adjudication.source_path
        candidates = (path, Path("..") / path)
        for candidate in candidates:
            if candidate.exists():
                source_texts[adjudication.entry_id] = candidate.read_text(encoding="utf-8")
                break
    return source_texts


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


def _label_context(adjudications: tuple[Fused75EntryAdjudication, ...]) -> dict[tuple[str, str], tuple[str | None, str | None]]:
    context: dict[tuple[str, str], tuple[str | None, str | None]] = {}
    for adjudication in adjudications:
        for label in adjudication.labels:
            context[(adjudication.entry_id, label.field_id)] = (label.source_quote, label.source_location)
    return context


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("dev", "test", "auto_pool"), required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--adjudication-root", type=Path, required=True)
    parser.add_argument("--fused-ground-truth-root", type=Path, required=True)
    parser.add_argument("--extraction-root", type=Path, default=Path("benchmark/optimization/fused75/extractions"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root-cause-output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """CLI entry point."""
    args = _parse_args(argv)
    run_detailed_error_taxonomy(
        split=args.split,
        config_path=args.config,
        adjudication_root=args.adjudication_root,
        extraction_root=args.extraction_root,
        fused_ground_truth_root=args.fused_ground_truth_root,
        output_path=args.output,
        root_cause_output_path=args.root_cause_output,
    )


if __name__ == "__main__":
    main()
