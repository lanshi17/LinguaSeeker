"""Diagnose structured extraction quality from layer-3 benchmark reports."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping, TypedDict, cast

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
AXES = ("by_field", "by_classification", "by_moi")


class RawReport(TypedDict, total=False):
    """Loose JSON shape for persisted layer-3 evaluation reports."""

    total_entries: int
    aggregates: Mapping[str, Any]
    per_entry: list[Mapping[str, Any]]


@dataclass(frozen=True)
class OverallMetrics:
    """Top-level extraction metrics."""

    precision: float
    recall: float
    f1: float
    entity_standardization_accuracy: float
    cross_lingual_consistency: float
    over_extractions: int


@dataclass(frozen=True)
class AxisRow:
    """One diagnostic row for a report aggregate axis."""

    axis: str
    key: str
    precision: float
    recall: float
    f1: float
    over_extractions: int


@dataclass(frozen=True)
class ExtractionDiagnostics:
    """Human-reviewable extraction diagnostics derived from one report."""

    report_path: Path
    total_entries: int
    overall: OverallMetrics
    axis_rows: list[AxisRow]
    match_type_counts: Counter[str]
    pipeline_status_counts: Counter[str]


def latest_report_path(reports_dir: Path = REPORTS_DIR) -> Path:
    """Return the newest layer-3 evaluation report by modification time."""
    candidates = list(reports_dir.glob("eval_*.json"))
    if not candidates:
        raise FileNotFoundError(f"No eval_*.json reports found in {reports_dir}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _load_report(report_path: Path) -> RawReport:
    """Load one persisted layer-3 report JSON."""
    with report_path.open(encoding="utf-8") as file_obj:
        return cast(RawReport, json.load(file_obj))


def _float_metric(metrics: Mapping[str, Any], key: str) -> float:
    value = metrics.get(key, 0.0)
    return float(value) if isinstance(value, int | float) else 0.0


def _int_metric(metrics: Mapping[str, Any], key: str) -> int:
    value = metrics.get(key, 0)
    return int(value) if isinstance(value, int | float) else 0


def _overall_metrics(raw: Mapping[str, Any]) -> OverallMetrics:
    return OverallMetrics(
        precision=_float_metric(raw, "precision"),
        recall=_float_metric(raw, "recall"),
        f1=_float_metric(raw, "f1"),
        entity_standardization_accuracy=_float_metric(raw, "entity_standardization_accuracy"),
        cross_lingual_consistency=_float_metric(raw, "cross_lingual_consistency"),
        over_extractions=_int_metric(raw, "over_extractions"),
    )


def _axis_rows(aggregates: Mapping[str, Any]) -> list[AxisRow]:
    rows: list[AxisRow] = []
    for axis in AXES:
        axis_data = aggregates.get(axis, {})
        if not isinstance(axis_data, Mapping):
            continue
        for key in sorted(axis_data):
            metrics = axis_data[key]
            if not isinstance(metrics, Mapping):
                continue
            rows.append(
                AxisRow(
                    axis=axis,
                    key=str(key),
                    precision=_float_metric(metrics, "precision"),
                    recall=_float_metric(metrics, "recall"),
                    f1=_float_metric(metrics, "f1"),
                    over_extractions=_int_metric(metrics, "over_extractions"),
                )
            )
    return rows


def _field_matches(entry: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    field_matches = entry.get("field_matches", [])
    if not isinstance(field_matches, list):
        return []
    return [item for item in field_matches if isinstance(item, Mapping)]


def build_diagnostics(report_path: Path) -> ExtractionDiagnostics:
    """Build extraction diagnostics from one layer-3 report."""
    report = _load_report(report_path)
    aggregates = report.get("aggregates", {})
    if not isinstance(aggregates, Mapping):
        aggregates = {}
    overall_raw = aggregates.get("overall", {})
    if not isinstance(overall_raw, Mapping):
        overall_raw = {}
    per_entry = report.get("per_entry", [])
    if not isinstance(per_entry, list):
        per_entry = []

    match_type_counts: Counter[str] = Counter()
    pipeline_status_counts: Counter[str] = Counter()
    for entry in per_entry:
        if not isinstance(entry, Mapping):
            continue
        pipeline_status_counts[str(entry.get("pipeline_status", "?"))] += 1
        for field_match in _field_matches(entry):
            match_type_counts[str(field_match.get("match_type", "?"))] += 1

    return ExtractionDiagnostics(
        report_path=report_path,
        total_entries=int(report.get("total_entries", 0)),
        overall=_overall_metrics(overall_raw),
        axis_rows=_axis_rows(aggregates),
        match_type_counts=match_type_counts,
        pipeline_status_counts=pipeline_status_counts,
    )


def _format_number(value: float | int) -> str:
    if isinstance(value, int):
        return str(value)
    return f"{value:.4f}".rstrip("0").rstrip(".") if value % 1 else f"{value:.1f}"


def format_diagnostics(diagnostics: ExtractionDiagnostics) -> str:
    """Format diagnostics as a terminal-readable report."""
    overall = diagnostics.overall
    lines = [
        f"REPORT: {diagnostics.report_path}",
        (
            f"N={diagnostics.total_entries}  overall: "
            f"P={_format_number(overall.precision)} "
            f"R={_format_number(overall.recall)} "
            f"F1={_format_number(overall.f1)} "
            f"std={_format_number(overall.entity_standardization_accuracy)} "
            f"tc={_format_number(overall.cross_lingual_consistency)} "
            f"over={overall.over_extractions}"
        ),
    ]

    for axis in AXES:
        lines.append("")
        lines.append(f"== {axis} ==")
        axis_rows = [row for row in diagnostics.axis_rows if row.axis == axis]
        for row in axis_rows:
            lines.append(
                f"  {row.key:30s} "
                f"P={_format_number(row.precision)} "
                f"R={_format_number(row.recall)} "
                f"F1={_format_number(row.f1)} "
                f"over={row.over_extractions}"
            )

    lines.append("")
    lines.append("== match_type distribution ==")
    for key, count in sorted(diagnostics.match_type_counts.items()):
        lines.append(f"  {key}: {count}")

    lines.append("")
    lines.append("== pipeline_status distribution ==")
    for key, count in sorted(diagnostics.pipeline_status_counts.items()):
        lines.append(f"  {key}: {count}")

    return "\n".join(lines)


def main() -> None:
    """Run the extraction diagnostic against the latest layer-3 report."""
    print(format_diagnostics(build_diagnostics(latest_report_path())))


if __name__ == "__main__":
    main()
