"""Runtime multilingual evidence augmentation metrics for Benchmark B phase 2 samples."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any, Mapping, TypedDict, cast

from benchmark.analysis.dataset_curation.evidence_augmentation_metrics import (
    EvidenceAugmentationCaseReport,
    EvidenceAugmentationMetrics,
    EvidenceAugmentationMatrix,
    _aggregate_metrics,
    _build_matrix,
    _metrics_from_matrix,
)
from benchmark.core import REPORTS_DIR


class BenchmarkBPhase2RuntimeCasePayload(TypedDict):
    """Serializable runtime sample case payload."""

    queue_id: str
    entry_id: str
    article_language: str
    target_gene: str
    target_disease: str
    processing_run_id: str | None
    source_document_id: str | None
    pipeline_status: str | None
    phase2_status: str | None
    source_pdf_path: str
    artifact_path: str
    artifact_exists: bool
    original_count: int
    translated_count: int
    reconciled_count: int
    matrix: Mapping[str, object]
    metrics: Mapping[str, object]


class BenchmarkBPhase2RuntimeReportPayload(TypedDict):
    """Serializable runtime report."""

    evaluation_id: str
    timestamp: str
    config: Mapping[str, object]
    runtime_summary: Mapping[str, object]
    overall: Mapping[str, object]
    per_case: list[BenchmarkBPhase2RuntimeCasePayload]
    warnings: list[str]


@dataclass(frozen=True)
class BenchmarkBPhase2RuntimeConfig:
    """Configuration for runtime sample augmentation metrics."""

    sample_report_paths: tuple[Path, ...]
    reports_dir: Path = REPORTS_DIR


@dataclass(frozen=True)
class BenchmarkBPhase2RuntimeCaseReport:
    """Runtime augmentation metrics for one sample row."""

    queue_id: str
    entry_id: str
    article_language: str
    target_gene: str
    target_disease: str
    processing_run_id: str | None
    source_document_id: str | None
    pipeline_status: str | None
    phase2_status: str | None
    source_pdf_path: Path
    artifact_path: Path
    artifact_exists: bool
    original_count: int
    translated_count: int
    reconciled_count: int
    matrix: EvidenceAugmentationMatrix
    metrics: EvidenceAugmentationMetrics


@dataclass(frozen=True)
class BenchmarkBPhase2RuntimeSummary:
    """Runtime attempt summary across sample runner rows."""

    attempted_samples: int
    phase2_completed: int
    timeout_count: int
    failed_count: int
    completed_queue_ids: tuple[str, ...]
    incomplete_queue_ids: tuple[str, ...]


@dataclass(frozen=True)
class BenchmarkBPhase2RuntimeReport:
    """Runtime augmentation report for multiple sample runs."""

    config: BenchmarkBPhase2RuntimeConfig
    per_case: tuple[BenchmarkBPhase2RuntimeCaseReport, ...]
    runtime_summary: BenchmarkBPhase2RuntimeSummary
    warnings: tuple[str, ...]

    @property
    def overall(self) -> EvidenceAugmentationMetrics:
        """Aggregate metrics across runtime cases."""
        synthetic = tuple(
            EvidenceAugmentationCaseReport(
                entry_id=case.entry_id,
                target_gene=case.target_gene,
                target_disease=case.target_disease,
                matrix=case.matrix,
                metrics=case.metrics,
            )
            for case in self.per_case
        )
        return _aggregate_metrics(synthetic)


def build_benchmark_b_phase2_runtime_report(config: BenchmarkBPhase2RuntimeConfig) -> BenchmarkBPhase2RuntimeReport:
    """Build augmentation metrics from runtime sample runner reports."""
    cases_by_queue_id: dict[str, BenchmarkBPhase2RuntimeCaseReport] = {}
    candidate_scores: dict[str, int] = {}
    attempted_statuses: dict[str, str] = {}
    warnings: list[str] = []
    seen_artifacts: set[Path] = set()
    for sample_report_path in config.sample_report_paths:
        payload = _load_json_object(sample_report_path)
        for row in _rows(payload):
            status = str(row.get("status") or "")
            queue_id = str(row.get("queue_id") or "")
            if queue_id and status != "planned":
                attempted_statuses[queue_id] = _preferred_attempt_status(attempted_statuses.get(queue_id), status)
            artifact_path_text = str(row.get("artifact_path") or "").strip()
            artifact_path = Path(artifact_path_text)
            artifact_exists = bool(artifact_path_text and artifact_path.is_file())
            is_explicit_completed = status == "phase2_completed"
            is_late_completed = status == "timeout" and artifact_exists
            if not (is_explicit_completed or is_late_completed):
                continue
            if not artifact_exists:
                warnings.append(f"{row.get('queue_id', '')}: missing artifact {artifact_path}")
                continue
            candidate_score = 2 if is_explicit_completed else 1
            previous_score = candidate_scores.get(queue_id, -1)
            if candidate_score < previous_score:
                continue
            if artifact_path in seen_artifacts and candidate_score <= previous_score:
                continue
            artifact_payload = _load_json_object(artifact_path)
            original_result = artifact_payload.get("original_result")
            translated_result = artifact_payload.get("translated_result")
            reconciled_result = artifact_payload.get("reconciled_result")
            if isinstance(reconciled_result, Mapping):
                source_payload: Mapping[str, Any] = reconciled_result
            elif isinstance(artifact_payload.get("evidence_items"), list):
                source_payload = artifact_payload
            else:
                source_payload = {
                    "original_result": original_result if isinstance(original_result, Mapping) else None,
                    "translated_result": translated_result if isinstance(translated_result, Mapping) else None,
                }
            matrix = _build_matrix(_accepted_items(source_payload))
            original_count = _count_found(original_result)
            translated_count = _count_found(translated_result)
            reconciled_count = _count_found(reconciled_result)
            case_report = BenchmarkBPhase2RuntimeCaseReport(
                queue_id=queue_id,
                entry_id=str(row.get("entry_id", "")),
                article_language=str(row.get("article_language", "")),
                target_gene=str(row.get("target_gene", "")),
                target_disease=str(row.get("target_disease", "")),
                processing_run_id=_optional_str(row.get("processing_run_id")),
                source_document_id=_optional_str(row.get("source_document_id")),
                pipeline_status=_optional_str(row.get("pipeline_status")),
                phase2_status="completed" if is_late_completed else _optional_str(row.get("phase2_status")),
                source_pdf_path=Path(str(row.get("source_pdf_path", ""))),
                artifact_path=artifact_path,
                artifact_exists=artifact_exists,
                original_count=original_count,
                translated_count=translated_count,
                reconciled_count=reconciled_count,
                matrix=matrix,
                metrics=_metrics_from_matrix(matrix),
            )
            previous_case = cases_by_queue_id.get(queue_id)
            if previous_case is not None:
                seen_artifacts.discard(previous_case.artifact_path)
            cases_by_queue_id[queue_id] = case_report
            candidate_scores[queue_id] = candidate_score
            seen_artifacts.add(artifact_path)
    completed_queue_ids = tuple(
        sorted(queue_id for queue_id, case in cases_by_queue_id.items() if case.phase2_status == "completed")
    )
    completed_set = set(completed_queue_ids)
    incomplete_queue_ids = tuple(sorted(queue_id for queue_id in attempted_statuses if queue_id not in completed_set))
    timeout_count = sum(1 for queue_id in incomplete_queue_ids if attempted_statuses.get(queue_id) == "timeout")
    return BenchmarkBPhase2RuntimeReport(
        config=config,
        per_case=tuple(cases_by_queue_id.values()),
        runtime_summary=BenchmarkBPhase2RuntimeSummary(
            attempted_samples=len(attempted_statuses),
            phase2_completed=len(completed_queue_ids),
            timeout_count=timeout_count,
            failed_count=len(incomplete_queue_ids),
            completed_queue_ids=completed_queue_ids,
            incomplete_queue_ids=incomplete_queue_ids,
        ),
        warnings=tuple(warnings),
    )


def benchmark_b_phase2_runtime_report_to_payload(
    report: BenchmarkBPhase2RuntimeReport,
) -> BenchmarkBPhase2RuntimeReportPayload:
    """Convert a runtime report to JSON-serializable payload."""
    return {
        "evaluation_id": f"benchmark_b_phase2_runtime_{time.strftime('%Y%m%d_%H%M%S')}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {
            "sample_report_paths": [str(path) for path in report.config.sample_report_paths],
            "reports_dir": str(report.config.reports_dir),
        },
        "runtime_summary": _runtime_summary_payload(report.runtime_summary),
        "overall": _metrics_payload(report.overall),
        "per_case": [_case_payload(case) for case in report.per_case],
        "warnings": list(report.warnings),
    }


def write_benchmark_b_phase2_runtime_report(
    report: BenchmarkBPhase2RuntimeReport,
    reports_dir: Path | None = None,
) -> Path:
    """Persist a runtime augmentation report as JSON."""
    output_dir = reports_dir or report.config.reports_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"benchmark_b_phase2_runtime_metrics_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(
        json.dumps(benchmark_b_phase2_runtime_report_to_payload(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def format_benchmark_b_phase2_runtime_report(report: BenchmarkBPhase2RuntimeReport) -> str:
    """Format runtime sample metrics for terminal review."""
    overall = report.overall
    summary = report.runtime_summary
    return (
        f"AttemptedSamples={summary.attempted_samples} "
        f"RuntimeSamples={len(report.per_case)} "
        f"Phase2Completed={summary.phase2_completed} "
        f"Timeouts={summary.timeout_count} "
        f"EvidenceCoverageGain={overall.evidence_coverage_gain} "
        f"NonEnglishYield={overall.non_english_evidence_yield} "
        f"TraceableAugmentationRate={overall.traceable_augmentation_rate} "
        f"ReviewerBurden={overall.reviewer_burden}"
    )


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-report", action="append", type=Path, required=True)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    report = build_benchmark_b_phase2_runtime_report(
        BenchmarkBPhase2RuntimeConfig(sample_report_paths=tuple(args.sample_report), reports_dir=args.reports_dir)
    )
    print(format_benchmark_b_phase2_runtime_report(report))
    if args.write:
        print(f"REPORT: {write_benchmark_b_phase2_runtime_report(report, reports_dir=args.reports_dir)}")


def _rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return []
    return [cast(Mapping[str, Any], row) for row in rows if isinstance(row, Mapping)]


def _accepted_items(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    evidence_items = payload.get("evidence_items")
    if isinstance(evidence_items, list):
        return _found_items(evidence_items)
    reconciled = payload.get("reconciled_result")
    if isinstance(reconciled, Mapping):
        return _found_items(reconciled.get("evidence_items"))
    items: list[Mapping[str, Any]] = []
    for key in ("original_result", "translated_result"):
        track_payload = payload.get(key)
        if isinstance(track_payload, Mapping):
            items.extend(_found_items(track_payload.get("evidence_items")))
    return items


def _found_items(raw_items: object) -> list[Mapping[str, Any]]:
    if not isinstance(raw_items, list):
        return []
    return [cast(Mapping[str, Any], item) for item in raw_items if isinstance(item, Mapping) and item.get("status") == "found"]


def _count_found(payload: object) -> int:
    if not isinstance(payload, Mapping):
        return 0
    items = payload.get("evidence_items")
    if not isinstance(items, list):
        return 0
    return sum(1 for item in items if isinstance(item, Mapping) and item.get("status") == "found")



def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _preferred_attempt_status(previous: str | None, current: str) -> str:
    if previous == "phase2_completed" or current == "phase2_completed":
        return "phase2_completed"
    if previous == "timeout" or current == "timeout":
        return "timeout"
    return current or (previous or "")


def _runtime_summary_payload(summary: BenchmarkBPhase2RuntimeSummary) -> Mapping[str, object]:
    return {
        "attempted_samples": summary.attempted_samples,
        "phase2_completed": summary.phase2_completed,
        "timeout_count": summary.timeout_count,
        "failed_count": summary.failed_count,
        "completed_queue_ids": list(summary.completed_queue_ids),
        "incomplete_queue_ids": list(summary.incomplete_queue_ids),
    }


def _case_payload(case: BenchmarkBPhase2RuntimeCaseReport) -> Mapping[str, object]:
    return {
        "queue_id": case.queue_id,
        "entry_id": case.entry_id,
        "article_language": case.article_language,
        "target_gene": case.target_gene,
        "target_disease": case.target_disease,
        "processing_run_id": case.processing_run_id,
        "source_document_id": case.source_document_id,
        "pipeline_status": case.pipeline_status,
        "phase2_status": case.phase2_status,
        "source_pdf_path": str(case.source_pdf_path),
        "artifact_path": str(case.artifact_path),
        "artifact_exists": case.artifact_exists,
        "original_count": case.original_count,
        "translated_count": case.translated_count,
        "reconciled_count": case.reconciled_count,
        "matrix": _matrix_payload(case.matrix),
        "metrics": _metrics_payload(case.metrics),
    }


def _matrix_payload(matrix: EvidenceAugmentationMatrix) -> Mapping[str, object]:
    return {
        "english_only_evidence_count": matrix.english_only_evidence_count,
        "multilingual_evidence_count": matrix.multilingual_evidence_count,
        "non_english_added_evidence_count": matrix.non_english_added_evidence_count,
        "unknown_language_evidence_count": matrix.unknown_language_evidence_count,
        "duplicated_evidence_count": matrix.duplicated_evidence_count,
        "conflicting_evidence_count": matrix.conflicting_evidence_count,
        "traceable_added_evidence_count": matrix.traceable_added_evidence_count,
        "potential_acmg_evidence_type_counts": dict(matrix.potential_acmg_evidence_type_counts),
    }


def _metrics_payload(metrics: EvidenceAugmentationMetrics) -> Mapping[str, object]:
    return {
        "evidence_coverage_gain": metrics.evidence_coverage_gain,
        "non_english_evidence_yield": metrics.non_english_evidence_yield,
        "unique_evidence_gain": metrics.unique_evidence_gain,
        "traceable_augmentation_rate": metrics.traceable_augmentation_rate,
        "interpretation_relevant_evidence_gain": metrics.interpretation_relevant_evidence_gain,
        "reviewer_burden": metrics.reviewer_burden,
    }


def _load_json_object(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Expected JSON object in {path}")
    return cast(Mapping[str, Any], payload)


if __name__ == "__main__":
    main()
