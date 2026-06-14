"""Offline oracle upper bounds for dual-track reconcile artifacts."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
import time
from typing import Any, NotRequired, TypedDict

from benchmark.layer3.evaluate import (
    GROUND_TRUTH_DIR,
    REPORTS_DIR,
    EntryMetrics,
    FieldMatch,
    compare_evidence,
    compute_aggregate_metrics,
    fuzzy_match_value,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualEvidenceExtractionResult,
    EvidenceItem,
)


RELATIONSHIP_FIELD_ID = "A.gene_disease_relationship"
DISEASE_FIELD_ID = "B.disease_diagnosis"


class OracleExtractedItem(TypedDict):
    """Minimal extracted item shape consumed by Layer 3 comparison."""

    field_id: str
    status: str
    value: object
    confidence: float
    source_span: NotRequired[dict[str, object]]


class FieldMatchPayload(TypedDict):
    """Serialized field match payload."""

    field_id: str
    expected: str
    matched: bool
    extracted: str | None
    source_span: dict[str, object] | None
    match_type: str
    extra_found_values: list[str]


class EntryMetricsPayload(TypedDict):
    """Serialized oracle entry metrics."""

    entry_id: str
    gene_symbol: str
    classification: str
    moi: str
    language: str
    pipeline_status: str
    error_message: str | None
    evidence_count: int
    found_rate: float
    field_matches: list[FieldMatchPayload]


class OracleStrategyPayload(TypedDict):
    """Serialized oracle strategy report."""

    strategy: str
    total_entries: int
    status_counts: dict[str, int]
    aggregates: dict[str, object]
    per_entry: list[EntryMetricsPayload]


class OracleUpperBoundPayload(TypedDict):
    """Serialized oracle upper-bound report."""

    evaluation_id: str
    timestamp: str
    config: dict[str, object]
    strategies: list[OracleStrategyPayload]


class OracleStrategy(str, Enum):
    """Offline-only oracle strategies used to estimate achievable gains."""

    ORACLE_BEST_DUAL_CANDIDATE = "oracle_best_dual_candidate"
    ORACLE_RELATIONSHIP_ONLY = "oracle_relationship_only"
    ORACLE_DISEASE_ONLY = "oracle_disease_only"
    ORACLE_NO_OVER_EXTRACTIONS = "oracle_no_over_extractions"


@dataclass(frozen=True)
class OracleStrategyReport:
    """Metrics for one oracle strategy."""

    strategy: OracleStrategy
    total_entries: int
    status_counts: dict[str, int]
    aggregates: dict[str, object]
    per_entry: tuple[EntryMetrics, ...]


@dataclass(frozen=True)
class OracleUpperBoundReport:
    """Full oracle upper-bound report."""

    strategies: tuple[OracleStrategyReport, ...]
    report_path: Path | None = None


def build_oracle_items(
    result: DualEvidenceExtractionResult,
    expected_fields: list[dict[str, object]],
    strategy: OracleStrategy,
) -> tuple[OracleExtractedItem, ...]:
    """Build extracted items for one oracle strategy."""
    candidates = [*result.original_result.evidence_items, *result.translated_result.evidence_items]
    if strategy == OracleStrategy.ORACLE_BEST_DUAL_CANDIDATE:
        selected = _best_candidates_for_fields(candidates, expected_fields, oracle_field_ids=None)
    elif strategy == OracleStrategy.ORACLE_RELATIONSHIP_ONLY:
        selected = _best_candidates_for_fields(candidates, expected_fields, oracle_field_ids={RELATIONSHIP_FIELD_ID})
    elif strategy == OracleStrategy.ORACLE_DISEASE_ONLY:
        selected = _best_candidates_for_fields(candidates, expected_fields, oracle_field_ids={DISEASE_FIELD_ID})
    elif strategy == OracleStrategy.ORACLE_NO_OVER_EXTRACTIONS:
        selected = _first_candidate_per_field(candidates)
    else:
        raise ValueError(f"unsupported oracle strategy: {strategy}")
    return tuple(_to_extracted_item(item) for item in selected)


def run_oracle_upper_bound(
    *,
    ground_truth_dir: Path = GROUND_TRUTH_DIR,
    reports_dir: Path = REPORTS_DIR,
    entry_ids: tuple[str, ...] = (),
    limit: int | None = None,
    save_report: bool = True,
) -> OracleUpperBoundReport:
    """Run oracle upper-bound strategies over persisted Phase 2 artifacts."""
    entries = _load_entries(ground_truth_dir, entry_ids=entry_ids, limit=limit)
    strategy_reports: list[OracleStrategyReport] = []
    for strategy in OracleStrategy:
        metrics = tuple(_evaluate_entry(entry, ground_truth_dir, strategy) for entry in entries)
        strategy_reports.append(
            OracleStrategyReport(
                strategy=strategy,
                total_entries=len(metrics),
                status_counts=dict(Counter(metric.pipeline_status for metric in metrics)),
                aggregates=compute_aggregate_metrics(list(metrics)),
                per_entry=metrics,
            )
        )
    report = OracleUpperBoundReport(strategies=tuple(strategy_reports))
    if save_report:
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"reconcile_oracle_upper_bound_{time.strftime('%Y%m%d_%H%M%S')}.json"
        report = OracleUpperBoundReport(strategies=tuple(strategy_reports), report_path=report_path)
        report_path.write_text(
            json.dumps(_serialize_report(report, ground_truth_dir, entry_ids, limit), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return report


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for oracle upper-bound analysis."""
    parser = argparse.ArgumentParser(description="Run offline reconcile oracle upper bounds.")
    parser.add_argument("--ground-truth-dir", type=Path, default=GROUND_TRUTH_DIR)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--entries", nargs="*", default=())
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    report = run_oracle_upper_bound(
        ground_truth_dir=args.ground_truth_dir,
        reports_dir=args.reports_dir,
        entry_ids=tuple(args.entries),
        limit=args.limit,
        save_report=args.write,
    )
    for strategy_report in report.strategies:
        overall = strategy_report.aggregates["overall"]
        print(
            f"{strategy_report.strategy.value}: "
            f"N={strategy_report.total_entries} "
            f"P={overall['precision']} R={overall['recall']} F1={overall['f1']} "
            f"statuses={strategy_report.status_counts}"
        )
    if report.report_path is not None:
        print(f"REPORT: {report.report_path}")


def _best_candidates_for_fields(
    candidates: list[EvidenceItem],
    expected_fields: list[dict[str, object]],
    *,
    oracle_field_ids: set[str] | None,
) -> list[EvidenceItem]:
    selected: list[EvidenceItem] = []
    for expected in expected_fields:
        field_id = str(expected.get("field_id", ""))
        field_candidates = [
            candidate
            for candidate in candidates
            if candidate.field_id == field_id and candidate.status.value == "found"
        ]
        if not field_candidates:
            continue
        if oracle_field_ids is None or field_id in oracle_field_ids:
            selected.append(_best_matching_or_first(field_candidates, str(expected.get("value", ""))))
            continue
        selected.append(field_candidates[0])
    return selected


def _best_matching_or_first(field_candidates: list[EvidenceItem], expected_value: str) -> EvidenceItem:
    for candidate in field_candidates:
        if fuzzy_match_value(expected_value, str(candidate.value)):
            return candidate
    return field_candidates[0]


def _first_candidate_per_field(candidates: list[EvidenceItem]) -> list[EvidenceItem]:
    selected: list[EvidenceItem] = []
    seen_fields: set[str] = set()
    for candidate in candidates:
        if candidate.status.value != "found":
            continue
        if candidate.field_id in seen_fields:
            continue
        seen_fields.add(candidate.field_id)
        selected.append(candidate)
    return selected


def _to_extracted_item(item: EvidenceItem) -> OracleExtractedItem:
    extracted: OracleExtractedItem = {
        "field_id": item.field_id,
        "status": item.status.value,
        "value": item.value,
        "confidence": item.confidence,
    }
    if item.source is not None:
        extracted["source_span"] = {
            "span_id": item.source.span_id,
            "page": item.source.page,
            "start_offset": item.source.start_offset,
            "end_offset": item.source.end_offset,
            "text_snippet": item.source.text_snippet,
            "source_precision": item.source.source_precision.value,
        }
    return extracted


def _evaluate_entry(
    entry: dict[str, Any],
    ground_truth_dir: Path,
    strategy: OracleStrategy,
) -> EntryMetrics:
    entry_id = str(entry["entry_id"])
    metrics = EntryMetrics(
        entry_id=entry_id,
        gene_symbol=str(entry.get("gene_symbol", "")),
        classification=str(entry.get("classification", "")),
        language="en",
        moi=str(entry.get("moi", "")),
    )
    artifact_path = ground_truth_dir / entry_id / "preprocessed" / "phase_2" / "extraction_result.json"
    expected_fields = list(entry.get("expected_evidence", []))
    if not artifact_path.exists():
        metrics.pipeline_status = "missing_artifact"
        metrics.error_message = f"missing artifact: {artifact_path}"
        metrics.field_matches = compare_evidence(
            expected_fields,
            [],
            expected_standardization=dict(entry.get("expected_standardization", {})),
        )
        return metrics
    result = DualEvidenceExtractionResult.model_validate_json(artifact_path.read_text(encoding="utf-8"))
    extracted_items = list(build_oracle_items(result, expected_fields, strategy))
    metrics.pipeline_status = "completed"
    metrics.evidence_count = len(extracted_items)
    found_count = sum(1 for item in extracted_items if item["status"] == "found")
    metrics.found_rate = found_count / len(extracted_items) if extracted_items else 0.0
    metrics.field_matches = compare_evidence(
        expected_fields,
        extracted_items,
        expected_standardization=dict(entry.get("expected_standardization", {})),
    )
    return metrics


def _load_entries(
    ground_truth_dir: Path,
    *,
    entry_ids: tuple[str, ...],
    limit: int | None,
) -> list[dict[str, Any]]:
    selection_items = json.loads((ground_truth_dir / "selection.json").read_text(encoding="utf-8"))
    requested_ids = set(entry_ids)
    entries: list[dict[str, Any]] = []
    for selection_item in selection_items:
        entry_id = str(selection_item["entry_id"])
        if requested_ids and entry_id not in requested_ids:
            continue
        expected_path = ground_truth_dir / entry_id / "expected.json"
        expected_item = json.loads(expected_path.read_text(encoding="utf-8")) if expected_path.exists() else {}
        entries.append({**selection_item, **expected_item})
        if limit is not None and len(entries) >= limit:
            break
    return entries


def _serialize_report(
    report: OracleUpperBoundReport,
    ground_truth_dir: Path,
    entry_ids: tuple[str, ...],
    limit: int | None,
) -> OracleUpperBoundPayload:
    return {
        "evaluation_id": f"reconcile_oracle_upper_bound_{time.strftime('%Y%m%d_%H%M%S')}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {
            "ground_truth_dir": str(ground_truth_dir),
            "entry_ids": list(entry_ids),
            "limit": limit,
            "report_path": str(report.report_path) if report.report_path is not None else None,
        },
        "strategies": [_serialize_strategy_report(strategy_report) for strategy_report in report.strategies],
    }


def _serialize_strategy_report(report: OracleStrategyReport) -> OracleStrategyPayload:
    return {
        "strategy": report.strategy.value,
        "total_entries": report.total_entries,
        "status_counts": report.status_counts,
        "aggregates": report.aggregates,
        "per_entry": [_serialize_entry_metrics(metrics) for metrics in report.per_entry],
    }


def _serialize_entry_metrics(metrics: EntryMetrics) -> EntryMetricsPayload:
    return {
        "entry_id": metrics.entry_id,
        "gene_symbol": metrics.gene_symbol,
        "classification": metrics.classification,
        "moi": metrics.moi,
        "language": metrics.language,
        "pipeline_status": metrics.pipeline_status,
        "error_message": metrics.error_message,
        "evidence_count": metrics.evidence_count,
        "found_rate": metrics.found_rate,
        "field_matches": [_serialize_field_match(match) for match in metrics.field_matches],
    }


def _serialize_field_match(match: FieldMatch) -> FieldMatchPayload:
    return {
        "field_id": match.field_id,
        "expected": match.expected_value,
        "matched": match.matched,
        "extracted": match.extracted_value,
        "source_span": match.source_span,
        "match_type": match.match_type,
        "extra_found_values": match.extra_found_values,
    }


if __name__ == "__main__":
    main()
