"""Benchmark readiness checks for Layer 3 cross-lingual evaluation."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any, Mapping, TypedDict, cast

from benchmark.core import GROUND_TRUTH_DIR, REPORTS_DIR
from benchmark.analysis.dataset_curation.alignment_annotation_protocol import validate_alignment_annotation_payload


class BenchmarkReadinessRowPayload(TypedDict):
    """Serializable readiness row."""

    entry_id: str
    status: str
    annotation_path: str | None
    message: str


class BenchmarkReadinessOverallPayload(TypedDict):
    """Serializable readiness summary."""

    total_entries: int
    annotated_count: int
    invalid_count: int
    missing_count: int
    alignment_annotation_coverage: float
    invalid_entry_ids: list[str]
    missing_entry_ids: list[str]


class BenchmarkReadinessPayload(TypedDict):
    """Serializable readiness report."""

    evaluation_id: str
    timestamp: str
    config: Mapping[str, object]
    overall: BenchmarkReadinessOverallPayload
    rows: list[BenchmarkReadinessRowPayload]
    warnings: list[str]


@dataclass(frozen=True)
class BenchmarkReadinessConfig:
    """Configuration for benchmark readiness checks."""

    ground_truth_root: Path = GROUND_TRUTH_DIR
    reports_dir: Path = REPORTS_DIR
    entry_ids: tuple[str, ...] = ()
    limit: int | None = None


@dataclass(frozen=True)
class BenchmarkReadinessRow:
    """Readiness status for one frozen benchmark entry."""

    entry_id: str
    status: str
    annotation_path: Path | None = None
    message: str = ""


@dataclass(frozen=True)
class BenchmarkReadinessOverall:
    """Aggregate readiness summary."""

    total_entries: int
    annotated_count: int
    invalid_count: int
    missing_count: int
    alignment_annotation_coverage: float
    invalid_entry_ids: tuple[str, ...]
    missing_entry_ids: tuple[str, ...]


@dataclass(frozen=True)
class BenchmarkReadinessReport:
    """Complete benchmark readiness report."""

    config: BenchmarkReadinessConfig
    overall: BenchmarkReadinessOverall
    rows: tuple[BenchmarkReadinessRow, ...]
    warnings: tuple[str, ...]


def build_benchmark_readiness_report(config: BenchmarkReadinessConfig) -> BenchmarkReadinessReport:
    """Build a readiness report for Benchmark A alignment annotations."""
    entry_ids = _entry_ids(config)
    rows: list[BenchmarkReadinessRow] = []
    warnings: list[str] = []
    ready_entry_ids: list[str] = []
    invalid_entry_ids: list[str] = []
    missing_entry_ids: list[str] = []

    for entry_id in entry_ids:
        annotation_path = config.ground_truth_root / entry_id / "alignment_annotations.json"
        if annotation_path.exists():
            try:
                validate_alignment_annotation_payload(
                    json.loads(annotation_path.read_text(encoding="utf-8")),
                    source_path=annotation_path,
                )
            except Exception as exc:
                invalid_entry_ids.append(entry_id)
                rows.append(
                    BenchmarkReadinessRow(
                        entry_id=entry_id,
                        status="invalid_alignment_annotations",
                        annotation_path=annotation_path,
                        message=str(exc),
                    )
                )
                warnings.append(f"{entry_id}: invalid alignment_annotations.json ({exc})")
                continue
            ready_entry_ids.append(entry_id)
            rows.append(
                BenchmarkReadinessRow(
                    entry_id=entry_id,
                    status="annotated",
                    annotation_path=annotation_path,
                    message="Alignment annotations are present.",
                )
            )
        else:
            missing_entry_ids.append(entry_id)
            rows.append(
                BenchmarkReadinessRow(
                    entry_id=entry_id,
                    status="missing_alignment_annotations",
                    message="alignment_annotations.json is missing.",
                )
            )
            warnings.append(f"{entry_id}: missing alignment_annotations.json")

    annotated_count = len(ready_entry_ids)
    overall = BenchmarkReadinessOverall(
        total_entries=len(entry_ids),
        annotated_count=annotated_count,
        invalid_count=len(invalid_entry_ids),
        missing_count=len(entry_ids) - len(ready_entry_ids),
        alignment_annotation_coverage=_rate(annotated_count, len(entry_ids)),
        invalid_entry_ids=tuple(invalid_entry_ids),
        missing_entry_ids=tuple(missing_entry_ids),
    )
    return BenchmarkReadinessReport(
        config=config,
        overall=overall,
        rows=tuple(rows),
        warnings=tuple(warnings),
    )


def write_benchmark_readiness_report(
    report: BenchmarkReadinessReport,
    reports_dir: Path | None = None,
) -> Path:
    """Persist a benchmark readiness report as JSON."""
    output_dir = reports_dir or report.config.reports_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"benchmark_readiness_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(benchmark_readiness_report_to_payload(report), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def benchmark_readiness_report_to_payload(report: BenchmarkReadinessReport) -> BenchmarkReadinessPayload:
    """Convert a readiness report to a JSON-serializable payload."""
    return {
        "evaluation_id": f"benchmark_readiness_{time.strftime('%Y%m%d_%H%M%S')}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {
            "ground_truth_root": str(report.config.ground_truth_root),
            "entry_ids": list(report.config.entry_ids),
            "limit": report.config.limit,
        },
        "overall": {
            "total_entries": report.overall.total_entries,
            "annotated_count": report.overall.annotated_count,
            "invalid_count": report.overall.invalid_count,
            "missing_count": report.overall.missing_count,
            "alignment_annotation_coverage": report.overall.alignment_annotation_coverage,
            "invalid_entry_ids": list(report.overall.invalid_entry_ids),
            "missing_entry_ids": list(report.overall.missing_entry_ids),
        },
        "rows": [
            {
                "entry_id": row.entry_id,
                "status": row.status,
                "annotation_path": str(row.annotation_path) if row.annotation_path is not None else None,
                "message": row.message,
            }
            for row in report.rows
        ],
        "warnings": list(report.warnings),
    }


def format_benchmark_readiness_report(report: BenchmarkReadinessReport) -> str:
    """Format readiness metrics for terminal review."""
    overall = report.overall
    return (
        f"AlignmentAnnotationCoverage={overall.alignment_annotation_coverage} "
        f"Annotated={overall.annotated_count}/{overall.total_entries} "
        f"Missing={overall.missing_count} "
        f"N={overall.total_entries}"
    )


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for benchmark readiness checks."""
    parser = argparse.ArgumentParser(description="Check Benchmark A readiness for alignment annotations.")
    parser.add_argument("--ground-truth-root", type=Path, default=GROUND_TRUTH_DIR)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--entries", nargs="*", default=())
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    report = build_benchmark_readiness_report(
        BenchmarkReadinessConfig(
            ground_truth_root=args.ground_truth_root,
            reports_dir=args.reports_dir,
            entry_ids=tuple(args.entries),
            limit=args.limit,
        )
    )
    print(format_benchmark_readiness_report(report))
    if args.write:
        print(f"REPORT: {write_benchmark_readiness_report(report, reports_dir=args.reports_dir)}")


def _entry_ids(config: BenchmarkReadinessConfig) -> tuple[str, ...]:
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


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _load_json_object(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Expected JSON object in {path}")
    return cast(Mapping[str, Any], payload)


if __name__ == "__main__":
    main()
