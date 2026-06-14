"""Compare latest layer-3 system and baseline reports."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping, cast

from benchmark.layer3.evaluate import (
    GROUND_TRUTH_DIR,
    REPORTS_DIR,
    EntryMetrics,
    FieldMatch,
    compare_evidence,
    compute_aggregate_metrics,
)


@dataclass(frozen=True)
class ComparisonRow:
    """One row in the system-vs-baseline comparison."""

    label: str
    report_path: Path
    total_entries: int
    precision: float
    recall: float
    f1: float
    adjusted: bool = False
    repaired_missing_entries: int = 0
    matched_to_system_entries: bool = False


@dataclass(frozen=True)
class BaselineComparison:
    """Comparison built from latest persisted reports."""

    rows: list[ComparisonRow]


def build_comparison(
    reports_dir: Path = REPORTS_DIR,
    ground_truth_dir: Path = GROUND_TRUTH_DIR,
    system_report_path: Path | None = None,
    match_system_entries: bool = False,
) -> BaselineComparison:
    """Build a comparison from latest system and baseline reports."""
    rows: list[ComparisonRow] = []
    system_path = system_report_path or _latest_report(reports_dir, "eval_*.json")
    system_report = _load_json(system_path)
    system_metrics, repaired_missing = _system_entry_metrics(system_report, ground_truth_dir)
    rows.append(_system_row(system_path, system_report, system_metrics, repaired_missing))
    system_entry_ids = {metric.entry_id for metric in system_metrics}

    for baseline_id, report_path in sorted(_latest_baseline_reports(reports_dir).items()):
        report = _load_json(report_path)
        rows.append(_baseline_row(
            baseline_id,
            report_path,
            report,
            system_entry_ids=system_entry_ids,
            match_system_entries=match_system_entries,
        ))
    return BaselineComparison(rows=rows)


def format_comparison(comparison: BaselineComparison) -> str:
    """Format comparison rows for terminal output."""
    lines = ["label N P R F1 report notes"]
    system_n = comparison.rows[0].total_entries if comparison.rows else 0
    for row in comparison.rows:
        notes: list[str] = []
        if row.adjusted:
            notes.append(f"adjusted repaired_missing={row.repaired_missing_entries}")
        if row.matched_to_system_entries:
            notes.append("matched_to_system_entries")
        if row.label != "SYSTEM" and row.total_entries != system_n:
            notes.append(f"N_mismatch_vs_system={system_n}")
        lines.append(
            f"{row.label} {row.total_entries} "
            f"{_format_number(row.precision)} {_format_number(row.recall)} {_format_number(row.f1)} "
            f"{row.report_path.name} {'; '.join(notes)}"
        )
    return "\n".join(lines)


def _system_row(
    report_path: Path,
    report: Mapping[str, Any],
    metrics: list[EntryMetrics],
    repaired_missing: int,
) -> ComparisonRow:
    if repaired_missing:
        overall = cast(Mapping[str, Any], compute_aggregate_metrics(metrics)["overall"])
        adjusted = True
    else:
        overall = _overall(report)
        adjusted = False
    return ComparisonRow(
        label="SYSTEM",
        report_path=report_path,
        total_entries=int(report.get("total_entries", 0)),
        precision=_float_metric(overall, "precision"),
        recall=_float_metric(overall, "recall"),
        f1=_float_metric(overall, "f1"),
        adjusted=adjusted,
        repaired_missing_entries=repaired_missing,
    )


def _baseline_row(
    baseline_id: str,
    report_path: Path,
    report: Mapping[str, Any],
    system_entry_ids: set[str],
    match_system_entries: bool,
) -> ComparisonRow:
    if match_system_entries:
        metrics = _baseline_entry_metrics(report, system_entry_ids)
        overall = cast(Mapping[str, Any], compute_aggregate_metrics(metrics)["overall"])
        return ComparisonRow(
            label=baseline_id,
            report_path=report_path,
            total_entries=len(metrics),
            precision=_float_metric(overall, "precision"),
            recall=_float_metric(overall, "recall"),
            f1=_float_metric(overall, "f1"),
            matched_to_system_entries=True,
        )
    overall = _overall(report)
    return ComparisonRow(
        label=baseline_id,
        report_path=report_path,
        total_entries=int(report.get("total_entries", 0)),
        precision=_float_metric(overall, "precision"),
        recall=_float_metric(overall, "recall"),
        f1=_float_metric(overall, "f1"),
    )


def _system_entry_metrics(
    report: Mapping[str, Any],
    ground_truth_dir: Path,
) -> tuple[list[EntryMetrics], int]:
    per_entry = report.get("per_entry", [])
    if not isinstance(per_entry, list):
        return [], 0
    metrics_list: list[EntryMetrics] = []
    repaired_missing = 0
    for raw_entry in per_entry:
        if not isinstance(raw_entry, Mapping):
            continue
        entry_id = str(raw_entry.get("entry_id", ""))
        metrics = EntryMetrics(
            entry_id=entry_id,
            gene_symbol=str(raw_entry.get("gene_symbol", "")),
            classification=str(raw_entry.get("classification", "")),
            language=str(raw_entry.get("language", "en")),
            moi=str(raw_entry.get("moi", "")),
            pipeline_status=str(raw_entry.get("pipeline_status", "")),
        )
        field_matches = _parse_field_matches(raw_entry.get("field_matches", []))
        if field_matches:
            metrics.field_matches = field_matches
        else:
            expected = _load_expected_entry(ground_truth_dir, entry_id)
            if expected:
                metrics.field_matches = compare_evidence(
                    list(expected.get("expected_evidence", [])),
                    [],
                    expected_standardization=expected.get("expected_standardization"),
                )
                repaired_missing += 1
        metrics_list.append(metrics)
    return metrics_list, repaired_missing


def _baseline_entry_metrics(
    report: Mapping[str, Any],
    system_entry_ids: set[str],
) -> list[EntryMetrics]:
    per_entry = report.get("per_entry", [])
    if not isinstance(per_entry, list):
        return []
    metrics_list: list[EntryMetrics] = []
    for raw_entry in per_entry:
        if not isinstance(raw_entry, Mapping):
            continue
        entry_id = str(raw_entry.get("entry_id", ""))
        if entry_id not in system_entry_ids:
            continue
        metrics = EntryMetrics(
            entry_id=entry_id,
            gene_symbol=str(raw_entry.get("gene_symbol", "")),
            classification=str(raw_entry.get("classification", "")),
            language=str(raw_entry.get("language", "en")),
            moi=str(raw_entry.get("moi", "")),
            pipeline_status=str(raw_entry.get("pipeline_status", "")),
        )
        metrics.field_matches = _parse_field_matches(raw_entry.get("field_matches", []))
        metrics_list.append(metrics)
    return metrics_list


def _parse_field_matches(raw_matches: object) -> list[FieldMatch]:
    if not isinstance(raw_matches, list):
        return []
    matches: list[FieldMatch] = []
    for raw_match in raw_matches:
        if not isinstance(raw_match, Mapping):
            continue
        source_span = raw_match.get("source_span")
        matches.append(
            FieldMatch(
                field_id=str(raw_match.get("field_id", "")),
                expected_value=str(raw_match.get("expected", "")),
                matched=bool(raw_match.get("matched", False)),
                extracted_value=(
                    str(raw_match["extracted"])
                    if raw_match.get("extracted") is not None
                    else None
                ),
                source_span=source_span if isinstance(source_span, dict) else None,
                match_type=str(raw_match.get("match_type", "none")),
                extra_found_values=[
                    str(value)
                    for value in raw_match.get("extra_found_values", [])
                    if isinstance(value, str)
                ],
            )
        )
    return matches


def _load_expected_entry(ground_truth_dir: Path, entry_id: str) -> Mapping[str, Any]:
    expected_path = ground_truth_dir / entry_id / "expected.json"
    if not expected_path.exists():
        return {}
    return _load_json(expected_path)


def _latest_report(reports_dir: Path, pattern: str) -> Path:
    candidates = list(reports_dir.glob(pattern))
    if not candidates:
        raise FileNotFoundError(f"No {pattern} reports found in {reports_dir}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _latest_baseline_reports(reports_dir: Path) -> dict[str, Path]:
    reports: dict[str, Path] = {}
    mtimes: dict[str, float] = {}
    for report_path in reports_dir.glob("baseline_b*.json"):
        report = _load_json(report_path)
        baseline_id = str(report.get("baseline_id", ""))
        if not baseline_id:
            continue
        mtime = report_path.stat().st_mtime
        if baseline_id not in reports or mtime > mtimes[baseline_id]:
            reports[baseline_id] = report_path
            mtimes[baseline_id] = mtime
    return reports


def _load_json(path: Path) -> Mapping[str, Any]:
    with path.open(encoding="utf-8") as file_obj:
        data = json.load(file_obj)
    return data if isinstance(data, Mapping) else {}


def _overall(report: Mapping[str, Any]) -> Mapping[str, Any]:
    aggregates = report.get("aggregates", {})
    if not isinstance(aggregates, Mapping):
        return {}
    overall = aggregates.get("overall", {})
    return overall if isinstance(overall, Mapping) else {}


def _float_metric(metrics: Mapping[str, Any], key: str) -> float:
    value = metrics.get(key, 0.0)
    return float(value) if isinstance(value, int | float) else 0.0


def _format_number(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".") if value % 1 else f"{value:.1f}"


def main() -> None:
    """Print latest system-vs-baseline comparison."""
    parser = argparse.ArgumentParser(description="Compare latest layer-3 system and baseline reports.")
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--ground-truth-dir", type=Path, default=GROUND_TRUTH_DIR)
    parser.add_argument("--system-report", type=Path, default=None)
    parser.add_argument("--matched-only", action="store_true")
    args = parser.parse_args()
    print(format_comparison(build_comparison(
        reports_dir=args.reports_dir,
        ground_truth_dir=args.ground_truth_dir,
        system_report_path=args.system_report,
        match_system_entries=args.matched_only,
    )))


if __name__ == "__main__":
    main()
