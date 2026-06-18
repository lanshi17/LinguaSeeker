"""Cross-lingual evidence alignment metrics for Layer 3 benchmarks."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any, Mapping, TypedDict, cast

from benchmark.core import GROUND_TRUTH_DIR, REPORTS_DIR
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualEvidenceExtractionResult,
    EvidenceAlignmentLabel,
    EvidenceAlignmentRecord,
    EvidenceSupportLabel,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.alignment import (
    build_alignment_records,
)


class AlignmentMetricPayload(TypedDict):
    """Serializable metric block for alignment evaluation."""

    alignment_accuracy: float
    support_label_accuracy: float
    drift_detection_f1: float
    conflict_detection_f1: float


class AlignmentCountsPayload(TypedDict):
    """Serializable count block for alignment evaluation."""

    total: int
    alignment_correct: int
    support_total: int
    support_correct: int
    drift_gold_positive: int
    drift_tp: int
    drift_fp: int
    drift_fn: int
    conflict_gold_positive: int
    conflict_tp: int
    conflict_fp: int
    conflict_fn: int


class AlignmentReportPayload(TypedDict):
    """Serializable alignment report."""

    evaluation_id: str
    timestamp: str
    config: Mapping[str, object]
    overall: Mapping[str, object]
    by_field: Mapping[str, object]
    counts: AlignmentCountsPayload
    label_counts: Mapping[str, Mapping[str, int]]
    warnings: list[str]


@dataclass(frozen=True)
class AlignmentMetricConfig:
    """Configuration for alignment metrics."""

    ground_truth_root: Path = GROUND_TRUTH_DIR
    reports_dir: Path = REPORTS_DIR
    entry_ids: tuple[str, ...] = ()
    limit: int | None = None


@dataclass(frozen=True)
class AlignmentCounts:
    """Counts used to derive alignment metrics."""

    total: int = 0
    alignment_correct: int = 0
    support_total: int = 0
    support_correct: int = 0
    drift_gold_positive: int = 0
    drift_tp: int = 0
    drift_fp: int = 0
    drift_fn: int = 0
    conflict_gold_positive: int = 0
    conflict_tp: int = 0
    conflict_fp: int = 0
    conflict_fn: int = 0


@dataclass(frozen=True)
class AlignmentMetrics:
    """Derived alignment metrics."""

    alignment_accuracy: float
    support_label_accuracy: float
    drift_detection_f1: float
    conflict_detection_f1: float


@dataclass(frozen=True)
class AlignmentMetricReport:
    """Complete alignment metric report."""

    config: AlignmentMetricConfig
    overall: AlignmentMetrics
    by_field: Mapping[str, AlignmentMetrics]
    counts: AlignmentCounts
    label_counts: Mapping[str, Mapping[str, int]]
    warnings: tuple[str, ...]


def build_alignment_metric_report(config: AlignmentMetricConfig) -> AlignmentMetricReport:
    """Build alignment metrics from annotation files and Phase 2 artifacts."""
    entries = _entry_ids(config)
    counts = AlignmentCounts()
    counts_by_field: dict[str, AlignmentCounts] = {}
    predicted_label_counts: Counter[str] = Counter()
    gold_label_counts: Counter[str] = Counter()
    warnings: list[str] = []

    for entry_id in entries:
        gold_records = _load_gold_records(config.ground_truth_root, entry_id)
        if not gold_records:
            warnings.append(f"{entry_id}: missing alignment_annotations.json")
            continue
        predicted_records = _load_predicted_records(config.ground_truth_root, entry_id)
        predicted_by_field = {record.field_id: record for record in predicted_records}
        for gold in gold_records:
            predicted = predicted_by_field.get(gold.field_id)
            field_counts = _compare_record(gold, predicted)
            counts = _add_counts(counts, field_counts)
            counts_by_field[gold.field_id] = _add_counts(
                counts_by_field.get(gold.field_id, AlignmentCounts()),
                field_counts,
            )
            gold_label_counts[gold.alignment_label.value] += 1
            predicted_alignment = _predicted_alignment_label(gold, predicted)
            if predicted_alignment is not None:
                predicted_label_counts[predicted_alignment.value] += 1

    return AlignmentMetricReport(
        config=config,
        overall=_metrics_from_counts(counts),
        by_field={field_id: _metrics_from_counts(field_counts) for field_id, field_counts in sorted(counts_by_field.items())},
        counts=counts,
        label_counts={
            "gold": dict(sorted(gold_label_counts.items())),
            "predicted": dict(sorted(predicted_label_counts.items())),
        },
        warnings=tuple(warnings),
    )


def write_alignment_metric_report(report: AlignmentMetricReport, reports_dir: Path | None = None) -> Path:
    """Persist an alignment metric report as JSON."""
    output_dir = reports_dir or report.config.reports_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"alignment_metrics_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(alignment_report_to_payload(report), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def alignment_report_to_payload(report: AlignmentMetricReport) -> AlignmentReportPayload:
    """Convert a report to a JSON-serializable payload."""
    return {
        "evaluation_id": f"alignment_metrics_{time.strftime('%Y%m%d_%H%M%S')}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {
            "ground_truth_root": str(report.config.ground_truth_root),
            "entry_ids": list(report.config.entry_ids),
            "limit": report.config.limit,
        },
        "overall": {"alignment": _metric_payload(report.overall)},
        "by_field": {
            field_id: {"alignment": _metric_payload(metrics)}
            for field_id, metrics in report.by_field.items()
        },
        "counts": _counts_payload(report.counts),
        "label_counts": report.label_counts,
        "warnings": list(report.warnings),
    }


def format_alignment_metric_report(report: AlignmentMetricReport) -> str:
    """Format alignment metrics for terminal review."""
    overall = report.overall
    return (
        f"AlignmentAccuracy={overall.alignment_accuracy} "
        f"SupportAccuracy={overall.support_label_accuracy} "
        f"DriftF1={overall.drift_detection_f1} "
        f"ConflictF1={overall.conflict_detection_f1} "
        f"N={report.counts.total}"
    )


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for alignment metrics."""
    parser = argparse.ArgumentParser(description="Compute cross-lingual evidence alignment metrics.")
    parser.add_argument("--ground-truth-root", type=Path, default=GROUND_TRUTH_DIR)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--entries", nargs="*", default=())
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    report = build_alignment_metric_report(
        AlignmentMetricConfig(
            ground_truth_root=args.ground_truth_root,
            reports_dir=args.reports_dir,
            entry_ids=tuple(args.entries),
            limit=args.limit,
        )
    )
    print(format_alignment_metric_report(report))
    if args.write:
        print(f"REPORT: {write_alignment_metric_report(report, reports_dir=args.reports_dir)}")


def _entry_ids(config: AlignmentMetricConfig) -> tuple[str, ...]:
    requested = set(config.entry_ids)
    selection_path = config.ground_truth_root / "selection.json"
    if selection_path.exists():
        raw_selection = json.loads(selection_path.read_text(encoding="utf-8"))
        if not isinstance(raw_selection, list):
            raise ValueError(f"Expected list in {selection_path}")
        entry_ids = [
            str(item.get("entry_id", ""))
            for item in raw_selection
            if isinstance(item, Mapping) and item.get("entry_id")
        ]
    else:
        entry_ids = [path.name for path in sorted(config.ground_truth_root.iterdir()) if path.is_dir()]
    filtered = [entry_id for entry_id in entry_ids if not requested or entry_id in requested]
    if config.limit is not None:
        filtered = filtered[: config.limit]
    return tuple(filtered)


def _load_gold_records(root: Path, entry_id: str) -> tuple[EvidenceAlignmentRecord, ...]:
    annotation_path = root / entry_id / "alignment_annotations.json"
    if not annotation_path.exists():
        return ()
    payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    raw_records = payload.get("records", payload) if isinstance(payload, Mapping) else payload
    if not isinstance(raw_records, list):
        raise ValueError(f"Expected alignment record list in {annotation_path}")
    return tuple(EvidenceAlignmentRecord.model_validate(record) for record in raw_records if isinstance(record, Mapping))


def _load_predicted_records(root: Path, entry_id: str) -> tuple[EvidenceAlignmentRecord, ...]:
    artifact_path = root / entry_id / "preprocessed" / "phase_2" / "extraction_result.json"
    if not artifact_path.exists():
        return ()
    payload = _load_json_object(artifact_path)
    raw_records = payload.get("alignment_records", [])
    if isinstance(raw_records, list) and raw_records:
        return tuple(EvidenceAlignmentRecord.model_validate(record) for record in raw_records if isinstance(record, Mapping))
    if "original_result" not in payload or "translated_result" not in payload:
        return ()
    result = DualEvidenceExtractionResult.model_validate(payload)
    return build_alignment_records(result.original_result, result.translated_result, entry_id=entry_id)


def _compare_record(
    gold: EvidenceAlignmentRecord,
    predicted: EvidenceAlignmentRecord | None,
) -> AlignmentCounts:
    predicted_alignment = _predicted_alignment_label(gold, predicted)
    predicted_support = _predicted_support_label(gold, predicted)
    return AlignmentCounts(
        total=1,
        alignment_correct=int(predicted_alignment == gold.alignment_label),
        support_total=1,
        support_correct=int(predicted_support == gold.support_label),
        drift_gold_positive=int(gold.alignment_label == EvidenceAlignmentLabel.DRIFTED),
        drift_tp=int(gold.alignment_label == EvidenceAlignmentLabel.DRIFTED and predicted_alignment == EvidenceAlignmentLabel.DRIFTED),
        drift_fp=int(gold.alignment_label != EvidenceAlignmentLabel.DRIFTED and predicted_alignment == EvidenceAlignmentLabel.DRIFTED),
        drift_fn=int(gold.alignment_label == EvidenceAlignmentLabel.DRIFTED and predicted_alignment != EvidenceAlignmentLabel.DRIFTED),
        conflict_gold_positive=int(gold.alignment_label == EvidenceAlignmentLabel.CONFLICT),
        conflict_tp=int(gold.alignment_label == EvidenceAlignmentLabel.CONFLICT and predicted_alignment == EvidenceAlignmentLabel.CONFLICT),
        conflict_fp=int(gold.alignment_label != EvidenceAlignmentLabel.CONFLICT and predicted_alignment == EvidenceAlignmentLabel.CONFLICT),
        conflict_fn=int(gold.alignment_label == EvidenceAlignmentLabel.CONFLICT and predicted_alignment != EvidenceAlignmentLabel.CONFLICT),
    )


def _predicted_alignment_label(
    gold: EvidenceAlignmentRecord,
    predicted: EvidenceAlignmentRecord | None,
) -> EvidenceAlignmentLabel | None:
    if predicted is not None:
        return predicted.alignment_label
    if gold.alignment_label == EvidenceAlignmentLabel.MISSING:
        return EvidenceAlignmentLabel.MISSING
    return None


def _predicted_support_label(
    gold: EvidenceAlignmentRecord,
    predicted: EvidenceAlignmentRecord | None,
) -> EvidenceSupportLabel | None:
    if predicted is not None:
        return predicted.support_label
    if gold.alignment_label == EvidenceAlignmentLabel.MISSING:
        return EvidenceSupportLabel.INSUFFICIENT
    return None


def _metrics_from_counts(counts: AlignmentCounts) -> AlignmentMetrics:
    return AlignmentMetrics(
        alignment_accuracy=_rate(counts.alignment_correct, counts.total),
        support_label_accuracy=_rate(counts.support_correct, counts.support_total),
        drift_detection_f1=_binary_f1(counts.drift_tp, counts.drift_fp, counts.drift_fn),
        conflict_detection_f1=_binary_f1(counts.conflict_tp, counts.conflict_fp, counts.conflict_fn),
    )


def _add_counts(left: AlignmentCounts, right: AlignmentCounts) -> AlignmentCounts:
    return AlignmentCounts(
        total=left.total + right.total,
        alignment_correct=left.alignment_correct + right.alignment_correct,
        support_total=left.support_total + right.support_total,
        support_correct=left.support_correct + right.support_correct,
        drift_gold_positive=left.drift_gold_positive + right.drift_gold_positive,
        drift_tp=left.drift_tp + right.drift_tp,
        drift_fp=left.drift_fp + right.drift_fp,
        drift_fn=left.drift_fn + right.drift_fn,
        conflict_gold_positive=left.conflict_gold_positive + right.conflict_gold_positive,
        conflict_tp=left.conflict_tp + right.conflict_tp,
        conflict_fp=left.conflict_fp + right.conflict_fp,
        conflict_fn=left.conflict_fn + right.conflict_fn,
    )


def _rate(numerator: int, denominator: int) -> float:
    return _round(numerator / denominator) if denominator else 0.0


def _binary_f1(tp: int, fp: int, fn: int) -> float:
    if tp == 0:
        return 0.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return _round(2 * precision * recall / (precision + recall)) if precision + recall else 0.0


def _round(value: float) -> float:
    return round(value, 4)


def _metric_payload(metrics: AlignmentMetrics) -> AlignmentMetricPayload:
    return {
        "alignment_accuracy": metrics.alignment_accuracy,
        "support_label_accuracy": metrics.support_label_accuracy,
        "drift_detection_f1": metrics.drift_detection_f1,
        "conflict_detection_f1": metrics.conflict_detection_f1,
    }


def _counts_payload(counts: AlignmentCounts) -> AlignmentCountsPayload:
    return {
        "total": counts.total,
        "alignment_correct": counts.alignment_correct,
        "support_total": counts.support_total,
        "support_correct": counts.support_correct,
        "drift_gold_positive": counts.drift_gold_positive,
        "drift_tp": counts.drift_tp,
        "drift_fp": counts.drift_fp,
        "drift_fn": counts.drift_fn,
        "conflict_gold_positive": counts.conflict_gold_positive,
        "conflict_tp": counts.conflict_tp,
        "conflict_fp": counts.conflict_fp,
        "conflict_fn": counts.conflict_fn,
    }


def _load_json_object(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Expected JSON object in {path}")
    return cast(Mapping[str, Any], payload)


if __name__ == "__main__":
    main()
