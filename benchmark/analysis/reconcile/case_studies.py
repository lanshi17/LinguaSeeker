"""Extract traceable case studies from reconcile ablation reports."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any, Mapping, TypedDict, cast

from benchmark.analysis.paper_artifacts.g2_statistics import (
    DEFAULT_CANDIDATE_STRATEGY,
    latest_reconcile_ablation_report,
)
from benchmark.core import REPORTS_DIR

DEFAULT_BASELINE_STRATEGY = "dual_union"


class RawStrategyPayload(TypedDict, total=False):
    """Loose persisted strategy shape from reconcile ablation JSON."""

    strategy: str
    per_entry: list[Mapping[str, Any]]


class RawAblationPayload(TypedDict, total=False):
    """Loose persisted reconcile ablation report shape."""

    evaluation_id: str
    strategies: list[RawStrategyPayload]


class CaseStudyPayload(TypedDict):
    """Serializable case-study row."""

    entry_id: str
    field_id: str
    improvement_type: str
    expected: str
    baseline_strategy: str
    baseline_extracted: str | None
    baseline_match_type: str
    candidate_strategy: str
    candidate_extracted: str | None
    candidate_match_type: str
    removed_extra_values: list[str]
    source_snippet: str | None
    source_precision: str | None


class CaseStudyReportPayload(TypedDict):
    """Serializable case-study report."""

    source_report_path: str
    baseline_strategy: str
    candidate_strategy: str
    total_cases: int
    cases: list[CaseStudyPayload]


@dataclass(frozen=True)
class CaseStudy:
    """One traceable reconcile improvement example."""

    entry_id: str
    field_id: str
    improvement_type: str
    expected: str
    baseline_strategy: str
    baseline_extracted: str | None
    baseline_match_type: str
    candidate_strategy: str
    candidate_extracted: str | None
    candidate_match_type: str
    removed_extra_values: tuple[str, ...]
    source_snippet: str | None
    source_precision: str | None


@dataclass(frozen=True)
class CaseStudyReport:
    """Case studies extracted from one ablation report."""

    source_report_path: Path
    baseline_strategy: str
    candidate_strategy: str
    cases: tuple[CaseStudy, ...]
    report_path: Path | None = None

    @property
    def total_cases(self) -> int:
        """Number of extracted case studies."""
        return len(self.cases)


def build_case_study_report(
    report_path: Path,
    *,
    baseline_strategy: str = DEFAULT_BASELINE_STRATEGY,
    candidate_strategy: str = DEFAULT_CANDIDATE_STRATEGY,
) -> CaseStudyReport:
    """Build case studies where the candidate strategy improves over baseline."""
    report = _load_report(report_path)
    strategy_entries = _strategy_entries(report)
    baseline_entries = _entries_by_id(_required_strategy(strategy_entries, baseline_strategy))
    candidate_entries = _entries_by_id(_required_strategy(strategy_entries, candidate_strategy))
    cases: list[CaseStudy] = []
    for entry_id in sorted(set(baseline_entries) & set(candidate_entries)):
        baseline_matches = _matches_by_field(baseline_entries[entry_id])
        candidate_matches = _matches_by_field(candidate_entries[entry_id])
        for field_id in sorted(set(baseline_matches) & set(candidate_matches)):
            baseline_match = baseline_matches[field_id]
            candidate_match = candidate_matches[field_id]
            cases.extend(
                _case_studies_for_field(
                    entry_id=entry_id,
                    field_id=field_id,
                    baseline_strategy=baseline_strategy,
                    candidate_strategy=candidate_strategy,
                    baseline_match=baseline_match,
                    candidate_match=candidate_match,
                )
            )
    return CaseStudyReport(
        source_report_path=report_path,
        baseline_strategy=baseline_strategy,
        candidate_strategy=candidate_strategy,
        cases=tuple(cases),
    )


def case_study_report_to_payload(report: CaseStudyReport) -> CaseStudyReportPayload:
    """Convert a case-study report to a JSON-serializable payload."""
    return {
        "source_report_path": str(report.source_report_path),
        "baseline_strategy": report.baseline_strategy,
        "candidate_strategy": report.candidate_strategy,
        "total_cases": report.total_cases,
        "cases": [_case_study_to_payload(case) for case in report.cases],
    }


def write_case_study_report(
    report: CaseStudyReport,
    reports_dir: Path = REPORTS_DIR,
) -> Path:
    """Persist a case-study report."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"reconcile_case_studies_{time.strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(
        json.dumps(case_study_report_to_payload(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_path


def format_case_study_report(report: CaseStudyReport) -> str:
    """Format case studies for terminal review."""
    lines = [
        f"REPORT: {report.source_report_path}",
        (
            f"{report.candidate_strategy} vs {report.baseline_strategy}: "
            f"cases={report.total_cases}"
        ),
    ]
    for case in report.cases:
        lines.append(
            f"{case.improvement_type} {case.entry_id} {case.field_id}: "
            f"baseline={case.baseline_extracted!r}/{case.baseline_match_type} "
            f"candidate={case.candidate_extracted!r}/{case.candidate_match_type} "
            f"removed={list(case.removed_extra_values)}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for reconcile case-study extraction."""
    parser = argparse.ArgumentParser(description="Extract reconcile ablation case studies.")
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--baseline-strategy", default=DEFAULT_BASELINE_STRATEGY)
    parser.add_argument("--candidate-strategy", default=DEFAULT_CANDIDATE_STRATEGY)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    report = build_case_study_report(
        args.report or latest_reconcile_ablation_report(),
        baseline_strategy=args.baseline_strategy,
        candidate_strategy=args.candidate_strategy,
    )
    print(format_case_study_report(report))
    if args.write:
        output_path = write_case_study_report(report)
        print(f"REPORT: {output_path}")


def _case_studies_for_field(
    *,
    entry_id: str,
    field_id: str,
    baseline_strategy: str,
    candidate_strategy: str,
    baseline_match: Mapping[str, Any],
    candidate_match: Mapping[str, Any],
) -> list[CaseStudy]:
    cases: list[CaseStudy] = []
    if baseline_match.get("match_type") in ("wrong_value", "missing", "none") and bool(candidate_match.get("matched")):
        cases.append(
            _build_case_study(
                entry_id=entry_id,
                field_id=field_id,
                improvement_type="field_corrected",
                baseline_strategy=baseline_strategy,
                candidate_strategy=candidate_strategy,
                baseline_match=baseline_match,
                candidate_match=candidate_match,
                removed_extra_values=(),
            )
        )
    removed_extra_values = tuple(
        sorted(set(_extra_values(baseline_match)) - set(_extra_values(candidate_match)))
    )
    if removed_extra_values:
        cases.append(
            _build_case_study(
                entry_id=entry_id,
                field_id=field_id,
                improvement_type="over_extraction_removed",
                baseline_strategy=baseline_strategy,
                candidate_strategy=candidate_strategy,
                baseline_match=baseline_match,
                candidate_match=candidate_match,
                removed_extra_values=removed_extra_values,
            )
        )
    return cases


def _build_case_study(
    *,
    entry_id: str,
    field_id: str,
    improvement_type: str,
    baseline_strategy: str,
    candidate_strategy: str,
    baseline_match: Mapping[str, Any],
    candidate_match: Mapping[str, Any],
    removed_extra_values: tuple[str, ...],
) -> CaseStudy:
    source_span = _source_span(candidate_match) or _source_span(baseline_match)
    return CaseStudy(
        entry_id=entry_id,
        field_id=field_id,
        improvement_type=improvement_type,
        expected=str(candidate_match.get("expected") or baseline_match.get("expected") or ""),
        baseline_strategy=baseline_strategy,
        baseline_extracted=_optional_string(baseline_match.get("extracted")),
        baseline_match_type=str(baseline_match.get("match_type") or ""),
        candidate_strategy=candidate_strategy,
        candidate_extracted=_optional_string(candidate_match.get("extracted")),
        candidate_match_type=str(candidate_match.get("match_type") or ""),
        removed_extra_values=removed_extra_values,
        source_snippet=_optional_string(source_span.get("text_snippet")) if source_span else None,
        source_precision=_optional_string(source_span.get("source_precision")) if source_span else None,
    )


def _case_study_to_payload(case: CaseStudy) -> CaseStudyPayload:
    return {
        "entry_id": case.entry_id,
        "field_id": case.field_id,
        "improvement_type": case.improvement_type,
        "expected": case.expected,
        "baseline_strategy": case.baseline_strategy,
        "baseline_extracted": case.baseline_extracted,
        "baseline_match_type": case.baseline_match_type,
        "candidate_strategy": case.candidate_strategy,
        "candidate_extracted": case.candidate_extracted,
        "candidate_match_type": case.candidate_match_type,
        "removed_extra_values": list(case.removed_extra_values),
        "source_snippet": case.source_snippet,
        "source_precision": case.source_precision,
    }


def _load_report(report_path: Path) -> RawAblationPayload:
    with report_path.open(encoding="utf-8") as file_obj:
        return cast(RawAblationPayload, json.load(file_obj))


def _strategy_entries(report: RawAblationPayload) -> Mapping[str, list[Mapping[str, Any]]]:
    strategies = report.get("strategies", [])
    entries_by_strategy: dict[str, list[Mapping[str, Any]]] = {}
    for strategy in strategies:
        strategy_name = strategy.get("strategy")
        per_entry = strategy.get("per_entry", [])
        if isinstance(strategy_name, str) and isinstance(per_entry, list):
            entries_by_strategy[strategy_name] = [
                entry for entry in per_entry if isinstance(entry, Mapping)
            ]
    return entries_by_strategy


def _required_strategy(
    entries_by_strategy: Mapping[str, list[Mapping[str, Any]]],
    strategy: str,
) -> list[Mapping[str, Any]]:
    entries = entries_by_strategy.get(strategy)
    if entries is None:
        available = ", ".join(sorted(entries_by_strategy))
        raise ValueError(f"Strategy {strategy!r} not found. Available: {available}")
    return entries


def _entries_by_id(entries: list[Mapping[str, Any]]) -> Mapping[str, Mapping[str, Any]]:
    return {
        str(entry["entry_id"]): entry
        for entry in entries
        if "entry_id" in entry
    }


def _matches_by_field(entry: Mapping[str, Any]) -> Mapping[str, Mapping[str, Any]]:
    field_matches = entry.get("field_matches", [])
    if not isinstance(field_matches, list):
        return {}
    return {
        str(field_match["field_id"]): field_match
        for field_match in field_matches
        if isinstance(field_match, Mapping) and "field_id" in field_match
    }


def _extra_values(field_match: Mapping[str, Any]) -> tuple[str, ...]:
    extra_values = field_match.get("extra_found_values", [])
    if not isinstance(extra_values, list):
        return ()
    return tuple(str(value) for value in extra_values)


def _source_span(field_match: Mapping[str, Any]) -> Mapping[str, Any] | None:
    span = field_match.get("source_span")
    return span if isinstance(span, Mapping) else None


def _optional_string(value: object) -> str | None:
    return str(value) if value is not None else None


if __name__ == "__main__":
    main()
