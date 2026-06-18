"""Offline ablation for cross-track reconcile strategies."""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from benchmark.core import (
    GROUND_TRUTH_DIR,
    REPORTS_DIR,
    EntryMetrics,
    FieldMatch,
    compare_evidence,
    compute_aggregate_metrics,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualEvidenceExtractionResult,
    EvidenceItem,
    SourceLocation,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.core import (
    reconcile_results,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.contracts import (
    CandidateScore,
    FieldDecision,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.contextual import (
    reconcile_with_context,
)
from src.core.standardize_entities_and_align_knowledge.context_pack.contracts import (
    TargetContextPack,
)
from src.core.standardize_entities_and_align_knowledge.context_pack.core import (
    build_context_pack_from_expected_json,
)


class ExtractedAblationItem(TypedDict):
    """Minimal evidence item shape consumed by Layer 3 compare_evidence."""

    field_id: str
    status: str
    value: object
    confidence: float
    source_span: NotRequired[dict[str, object]]
    best_score: NotRequired[float]
    source_score: NotRequired[float]
    confidence_score: NotRequired[float]
    agreement_score: NotRequired[float]
    status_score: NotRequired[float]
    verifier_support_score: NotRequired[float]
    target_specificity_score: NotRequired[float]
    contradiction_penalty: NotRequired[float]
    accepted_track: NotRequired[str]
    normalized_value: NotRequired[str]


class FieldMatchPayload(TypedDict):
    """Serialized field-match payload."""

    field_id: str
    expected: str
    matched: bool
    extracted: str | None
    source_span: dict[str, object] | None
    match_type: str
    extra_found_values: list[str]
    best_score: float | None
    source_score: float | None
    confidence_score: float | None
    agreement_score: float | None
    status_score: float | None
    verifier_support_score: float | None
    target_specificity_score: float | None
    contradiction_penalty: float | None
    accepted_track: str | None
    normalized_value: str | None


class EntryMetricsPayload(TypedDict):
    """Serialized ablation entry metrics."""

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


class StrategyReportPayload(TypedDict):
    """Serialized report for one ablation strategy."""

    strategy: str
    total_entries: int
    status_counts: dict[str, int]
    aggregates: dict[str, object]
    per_entry: list[EntryMetricsPayload]


class AblationReportPayload(TypedDict):
    """Serialized reconcile ablation report."""

    evaluation_id: str
    timestamp: str
    config: dict[str, object]
    strategies: list[StrategyReportPayload]


class AblationStrategy(str, Enum):
    """Offline strategies compared on the same dual-track artifacts."""

    DUAL_UNION = "dual_union"
    GROUNDED_HARD_RULE = "grounded_hard_rule"
    SOURCE_GROUNDED_RECONCILE = "source_grounded_reconcile"
    CONTEXT_VERIFIER_RECONCILE = "context_verifier_reconcile"


@dataclass(frozen=True)
class AblationConfig:
    """Configuration for offline reconcile ablation."""

    ground_truth_dir: Path = GROUND_TRUTH_DIR
    reports_dir: Path = REPORTS_DIR
    entry_ids: tuple[str, ...] = ()
    limit: int | None = None
    save_report: bool = True


@dataclass(frozen=True)
class AblationStrategyReport:
    """Metrics for one ablation strategy."""

    strategy: AblationStrategy
    total_entries: int
    status_counts: dict[str, int]
    aggregates: dict[str, object]
    per_entry: tuple[EntryMetrics, ...]


@dataclass(frozen=True)
class AblationReport:
    """Full offline reconcile ablation report."""

    strategies: tuple[AblationStrategyReport, ...]
    report_path: Path | None = None


def build_extracted_items(
    result: DualEvidenceExtractionResult,
    strategy: AblationStrategy,
    *,
    context_pack: TargetContextPack | None = None,
) -> tuple[ExtractedAblationItem, ...]:
    """Build comparable evidence items for one ablation strategy."""
    if strategy == AblationStrategy.DUAL_UNION:
        items = [*result.original_result.evidence_items, *result.translated_result.evidence_items]
    elif strategy == AblationStrategy.GROUNDED_HARD_RULE:
        items = _grounded_hard_rule_items(result)
    elif strategy == AblationStrategy.SOURCE_GROUNDED_RECONCILE:
        reconciled = result.reconciled_result or reconcile_results(
            result.original_result,
            result.translated_result,
        ).result
        items = reconciled.evidence_items
    elif strategy == AblationStrategy.CONTEXT_VERIFIER_RECONCILE:
        if context_pack is None:
            raise ValueError("context_pack is required for context_verifier_reconcile")
        reconciled = reconcile_with_context(
            result.original_result,
            result.translated_result,
            context_pack,
        )
        return tuple(_to_scored_extracted_item(decision) for decision in reconciled.decisions if decision.accepted is not None)
    else:
        raise ValueError(f"unsupported ablation strategy: {strategy}")
    return tuple(_to_extracted_item(item) for item in items)


def run_ablation(config: AblationConfig) -> AblationReport:
    """Run all reconcile ablation strategies over persisted Phase 2 artifacts."""
    entries = _load_entries(config)
    strategy_reports: list[AblationStrategyReport] = []
    for strategy in AblationStrategy:
        metrics = tuple(_evaluate_entry(entry, config.ground_truth_dir, strategy) for entry in entries)
        strategy_reports.append(
            AblationStrategyReport(
                strategy=strategy,
                total_entries=len(metrics),
                status_counts=dict(Counter(metric.pipeline_status for metric in metrics)),
                aggregates=compute_aggregate_metrics(list(metrics)),
                per_entry=metrics,
            )
        )

    report_path: Path | None = None
    report = AblationReport(strategies=tuple(strategy_reports))
    if config.save_report:
        config.reports_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_path = config.reports_dir / f"reconcile_ablation_{timestamp}.json"
        report = AblationReport(strategies=tuple(strategy_reports), report_path=report_path)
        report_path.write_text(
            json.dumps(_serialize_report(report, config), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return report


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for offline reconcile ablation."""
    parser = argparse.ArgumentParser(description="Run offline cross-track reconcile ablations.")
    parser.add_argument("--ground-truth-dir", type=Path, default=GROUND_TRUTH_DIR)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--entries", nargs="*", default=())
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    report = run_ablation(
        AblationConfig(
            ground_truth_dir=args.ground_truth_dir,
            reports_dir=args.reports_dir,
            entry_ids=tuple(args.entries),
            limit=args.limit,
            save_report=args.write,
        )
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


def _grounded_hard_rule_items(result: DualEvidenceExtractionResult) -> list[EvidenceItem]:
    candidates = [*result.original_result.evidence_items, *result.translated_result.evidence_items]
    selected: list[EvidenceItem] = []
    for field_id in sorted({item.field_id for item in candidates}):
        field_items = [item for item in candidates if item.field_id == field_id]
        selected.append(
            sorted(
                field_items,
                key=lambda item: (
                    -_source_rank(item.source),
                    -item.confidence,
                    _normalize_value(item.value),
                ),
            )[0]
        )
    return selected


def _source_rank(source: SourceLocation | None) -> float:
    if source is None:
        return 0.0
    if source.source_precision == "exact":
        return 3.0
    if source.source_precision == "corrected":
        return 2.0
    if source.source_precision == "ambiguous":
        return 1.0
    return 0.0


def _to_extracted_item(item: EvidenceItem) -> ExtractedAblationItem:
    extracted: ExtractedAblationItem = {
        "field_id": item.field_id,
        "status": item.status.value,
        "value": item.value,
        "confidence": item.confidence,
    }
    if item.source is not None:
        extracted["source_span"] = _source_to_payload(item.source)
    return extracted


def _to_scored_extracted_item(decision: FieldDecision) -> ExtractedAblationItem:
    """Serialize an accepted contextual decision with score components."""
    if decision.accepted is None:
        raise ValueError("Cannot serialize a contextual decision without an accepted item")
    extracted = _to_extracted_item(decision.accepted)
    if decision.accepted_score is not None:
        extracted.update(_score_to_payload(decision.accepted_score))
    return extracted


def _score_to_payload(score: CandidateScore) -> dict[str, float | str]:
    """Serialize score components used by contextual reconcile diagnostics."""
    return {
        "best_score": score.score,
        "source_score": score.source_score,
        "confidence_score": score.confidence_score,
        "agreement_score": score.agreement_score,
        "status_score": score.status_score,
        "verifier_support_score": score.verifier_support_score,
        "target_specificity_score": score.target_specificity_score,
        "contradiction_penalty": score.contradiction_penalty,
        "accepted_track": score.track.value,
        "normalized_value": score.normalized_value,
    }


def _source_to_payload(source: SourceLocation) -> dict[str, object]:
    return {
        "span_id": source.span_id,
        "page": source.page,
        "start_offset": source.start_offset,
        "end_offset": source.end_offset,
        "text_snippet": source.text_snippet,
        "source_precision": source.source_precision.value,
    }


def _evaluate_entry(
    entry: dict[str, Any],
    ground_truth_dir: Path,
    strategy: AblationStrategy,
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
    if not artifact_path.exists():
        metrics.pipeline_status = "missing_artifact"
        metrics.error_message = f"missing artifact: {artifact_path}"
        metrics.field_matches = compare_evidence(
            list(entry.get("expected_evidence", [])),
            [],
            expected_standardization=dict(entry.get("expected_standardization", {})),
        )
        return metrics

    result = DualEvidenceExtractionResult.model_validate_json(artifact_path.read_text(encoding="utf-8"))
    context_pack = (
        build_context_pack_from_expected_json(ground_truth_dir / entry_id / "expected.json")
        if strategy == AblationStrategy.CONTEXT_VERIFIER_RECONCILE
        else None
    )
    extracted_items = list(build_extracted_items(result, strategy, context_pack=context_pack))
    metrics.pipeline_status = "completed"
    metrics.evidence_count = len(extracted_items)
    found_count = sum(1 for item in extracted_items if item["status"] == "found")
    metrics.found_rate = found_count / len(extracted_items) if extracted_items else 0.0
    metrics.field_matches = compare_evidence(
        list(entry.get("expected_evidence", [])),
        extracted_items,
        expected_standardization=dict(entry.get("expected_standardization", {})),
    )
    return metrics


def _load_entries(config: AblationConfig) -> list[dict[str, Any]]:
    selection_path = config.ground_truth_dir / "selection.json"
    selection_items = json.loads(selection_path.read_text(encoding="utf-8"))
    requested_ids = set(config.entry_ids)
    entries: list[dict[str, Any]] = []
    for selection_item in selection_items:
        entry_id = str(selection_item["entry_id"])
        if requested_ids and entry_id not in requested_ids:
            continue
        expected_path = config.ground_truth_dir / entry_id / "expected.json"
        expected_item = (
            json.loads(expected_path.read_text(encoding="utf-8"))
            if expected_path.exists()
            else {}
        )
        entries.append({**selection_item, **expected_item})
        if config.limit is not None and len(entries) >= config.limit:
            break
    return entries


def _normalize_value(value: object) -> str:
    if isinstance(value, list):
        return "|".join(sorted(str(item).strip().casefold() for item in value))
    return str(value).strip().casefold()


def _serialize_report(report: AblationReport, config: AblationConfig) -> AblationReportPayload:
    return {
        "evaluation_id": f"reconcile_ablation_{time.strftime('%Y%m%d_%H%M%S')}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {
            "ground_truth_dir": str(config.ground_truth_dir),
            "entry_ids": list(config.entry_ids),
            "limit": config.limit,
            "report_path": str(report.report_path) if report.report_path is not None else None,
        },
        "strategies": [_serialize_strategy_report(strategy_report) for strategy_report in report.strategies],
    }


def _serialize_strategy_report(report: AblationStrategyReport) -> StrategyReportPayload:
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
        "best_score": match.best_score,
        "source_score": match.source_score,
        "confidence_score": match.confidence_score,
        "agreement_score": match.agreement_score,
        "status_score": match.status_score,
        "verifier_support_score": match.verifier_support_score,
        "target_specificity_score": match.target_specificity_score,
        "contradiction_penalty": match.contradiction_penalty,
        "accepted_track": match.accepted_track,
        "normalized_value": match.normalized_value,
    }


if __name__ == "__main__":
    main()
