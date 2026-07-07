"""Build main-benchmark comparison rows from system and baseline reports."""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any, Literal, Mapping, TypedDict, cast

from benchmark.core import GROUND_TRUTH_ROOT
from benchmark.core.paths import PAPER_REPORTS_ROOT


CoverageStatus = Literal["complete", "partial", "mismatch"]


class BenchmarkMethodRow(TypedDict):
    """One method row in the main-benchmark baseline matrix."""

    method_id: str
    method_name: str
    role: str
    model: str
    prompt_mode: str
    ground_truth_dir: str
    expected_entries: int
    total_entries: int
    completed_entries: int
    error_entries: int
    coverage_status: CoverageStatus
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    error_rate: float
    avg_latency_s: float
    report_path: str
    warnings: str


class BenchmarkMatrixPayload(TypedDict):
    """Serializable main-benchmark baseline matrix payload."""

    generated_at: str
    ground_truth_dir: str
    expected_entries: int
    rows: list[BenchmarkMethodRow]


@dataclass(frozen=True)
class ReportPaths:
    """Paths written by the baseline matrix exporter."""

    json: Path
    csv: Path
    markdown: Path


def build_baseline_matrix(
    *,
    report_paths: tuple[Path, ...],
    ground_truth_dir: Path = GROUND_TRUTH_ROOT,
    expected_entries: int | None = None,
) -> BenchmarkMatrixPayload:
    """Build a comparable method matrix from finished benchmark reports."""
    expected_count = expected_entries if expected_entries is not None else count_ground_truth_entries(ground_truth_dir)
    rows = [
        _row_from_report(
            report_path=report_path,
            report=_load_json_object(report_path),
            expected_entries=expected_count,
        )
        for report_path in report_paths
    ]
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "ground_truth_dir": str(ground_truth_dir),
        "expected_entries": expected_count,
        "rows": rows,
    }


def count_ground_truth_entries(ground_truth_dir: Path) -> int:
    """Count entries addressable by the baseline runner for a ground-truth root."""
    selection_path = ground_truth_dir / "selection.json"
    manifest_path = ground_truth_dir / "manifest.json"
    if selection_path.exists():
        payload = json.loads(selection_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"Expected selection list in {selection_path}")
        return sum(1 for item in payload if _entry_has_source(ground_truth_dir, _entry_id(item)))
    if manifest_path.exists():
        payload = _load_json_object(manifest_path)
        entries = _list(payload.get("entries"))
        return sum(1 for item in entries if _entry_has_source(ground_truth_dir, _manifest_entry_id(item)))
    return sum(1 for path in ground_truth_dir.glob("*/expected.json") if (path.parent / "source.md").exists())


def write_baseline_matrix(
    payload: BenchmarkMatrixPayload,
    *,
    reports_dir: Path = PAPER_REPORTS_ROOT,
) -> ReportPaths:
    """Persist the matrix as JSON, CSV, and Markdown."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    json_path = reports_dir / f"main_benchmark_baseline_matrix_{timestamp}.json"
    csv_path = reports_dir / f"main_benchmark_baseline_matrix_{timestamp}.csv"
    markdown_path = reports_dir / f"main_benchmark_baseline_matrix_{timestamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(payload["rows"], csv_path)
    markdown_path.write_text(_format_markdown(payload), encoding="utf-8")
    return ReportPaths(json=json_path, csv=csv_path, markdown=markdown_path)


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for the main-benchmark baseline matrix."""
    parser = argparse.ArgumentParser(description="Build the main-benchmark baseline comparison matrix.")
    parser.add_argument("--ground-truth-dir", type=Path, default=GROUND_TRUTH_ROOT)
    parser.add_argument("--expected-entries", type=int, default=None)
    parser.add_argument("--reports", nargs="+", type=Path, required=True)
    parser.add_argument("--reports-dir", type=Path, default=PAPER_REPORTS_ROOT / "main_benchmark_baseline_matrix")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    payload = build_baseline_matrix(
        report_paths=tuple(args.reports),
        ground_truth_dir=args.ground_truth_dir,
        expected_entries=args.expected_entries,
    )
    if args.write:
        paths = write_baseline_matrix(payload, reports_dir=args.reports_dir)
        print(f"JSON: {paths.json}")
        print(f"CSV: {paths.csv}")
        print(f"MARKDOWN: {paths.markdown}")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def _row_from_report(
    *,
    report_path: Path,
    report: Mapping[str, Any],
    expected_entries: int,
) -> BenchmarkMethodRow:
    aggregates = _mapping(report.get("aggregates"))
    overall = _mapping(aggregates.get("overall"))
    config = _mapping(report.get("config"))
    total_entries = _int(report.get("total_entries"))
    per_entry = _list(report.get("per_entry"))
    error_entries = sum(
        1
        for entry in per_entry
        if isinstance(entry, Mapping) and str(entry.get("pipeline_status") or "") == "error"
    )
    completed_entries = max(total_entries - error_entries, 0)
    warnings = _warnings(total_entries=total_entries, expected_entries=expected_entries, error_entries=error_entries)
    return {
        "method_id": _method_id(report),
        "method_name": _method_name(report),
        "role": "system" if not report.get("baseline_id") else "baseline",
        "model": str(config.get("model") or config.get("model_baseline_id") or ""),
        "prompt_mode": str(config.get("prompt_mode") or config.get("model_baseline_name") or ""),
        "ground_truth_dir": str(config.get("ground_truth_dir") or config.get("ground_truth_root") or ""),
        "expected_entries": expected_entries,
        "total_entries": total_entries,
        "completed_entries": completed_entries,
        "error_entries": error_entries,
        "coverage_status": _coverage_status(total_entries, expected_entries),
        "true_positives": _int(overall.get("true_positives")),
        "false_positives": _int(overall.get("false_positives")),
        "false_negatives": _int(overall.get("false_negatives")),
        "precision": _float(overall.get("precision")),
        "recall": _float(overall.get("recall")),
        "f1": _float(overall.get("f1")),
        "error_rate": _float(error_entries / total_entries) if total_entries else 0.0,
        "avg_latency_s": _float(_float(report.get("total_duration_s")) / total_entries) if total_entries else 0.0,
        "report_path": str(report_path),
        "warnings": "; ".join(warnings),
    }


def _method_id(report: Mapping[str, Any]) -> str:
    baseline_id = str(report.get("baseline_id") or "").strip()
    if baseline_id:
        return baseline_id
    evaluation_id = str(report.get("evaluation_id") or "").strip()
    return "LinguaSeeker" if evaluation_id.startswith("eval_") else "system"


def _method_name(report: Mapping[str, Any]) -> str:
    baseline_name = str(report.get("baseline_name") or "").strip()
    if baseline_name:
        return baseline_name
    evaluation_id = str(report.get("evaluation_id") or "").strip()
    return evaluation_id or _method_id(report)


def _coverage_status(total_entries: int, expected_entries: int) -> CoverageStatus:
    if total_entries == expected_entries:
        return "complete"
    if total_entries < expected_entries:
        return "partial"
    return "mismatch"


def _warnings(*, total_entries: int, expected_entries: int, error_entries: int) -> list[str]:
    warnings: list[str] = []
    if total_entries != expected_entries:
        warnings.append(f"coverage {total_entries}/{expected_entries}")
    if error_entries:
        warnings.append(f"{error_entries} error entries")
    return warnings


def _write_csv(rows: list[BenchmarkMethodRow], csv_path: Path) -> None:
    columns = list(BenchmarkMethodRow.__annotations__)
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _format_markdown(payload: BenchmarkMatrixPayload) -> str:
    lines = [
        "# Main Benchmark Baseline Matrix",
        "",
        f"Generated at: `{payload['generated_at']}`",
        f"Ground truth: `{payload['ground_truth_dir']}`",
        f"Expected entries: `{payload['expected_entries']}`",
        "",
    ]
    rows = payload["rows"]
    if not rows:
        lines.append("_No reports supplied._")
        return "\n".join(lines).rstrip() + "\n"
    columns = list(BenchmarkMethodRow.__annotations__)
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join("---" for _ in columns) + " |")
    for row in rows:
        lines.append("| " + " | ".join(_markdown_cell(row[column]) for column in columns) + " |")
    return "\n".join(lines).rstrip() + "\n"


def _load_json_object(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Expected JSON object in {path}")
    return cast(Mapping[str, Any], payload)


def _entry_has_source(root: Path, entry_id: str) -> bool:
    return bool(entry_id) and (root / entry_id / "source.md").exists()


def _entry_id(item: object) -> str:
    if not isinstance(item, Mapping):
        return ""
    return str(item.get("entry_id") or "")


def _manifest_entry_id(item: object) -> str:
    if not isinstance(item, Mapping):
        return ""
    return str(item.get("unified_id") or item.get("entry_id") or "")


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return cast(Mapping[str, Any], value)
    return {}


def _list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return []


def _int(value: object) -> int:
    if value is None or value == "":
        return 0
    return int(value)


def _float(value: object) -> float:
    if value is None or value == "":
        return 0.0
    return round(float(value), 4)


def _markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    main()
