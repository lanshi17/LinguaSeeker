"""Diagnose source-grounding signals from layer-3 benchmark reports."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping, TypedDict, cast

from benchmark.core import REPORTS_ROOT

# eval_*.json reports moved to benchmark/data/reports/eval/ in Phase 4
# of the 2026-06-18 framework refactor; legacy name kept for callers.
LAYER3_REPORTS_DIR = REPORTS_ROOT / "eval"


class RawReport(TypedDict, total=False):
    """Loose JSON shape for persisted benchmark reports."""

    total_entries: int
    per_entry: list[Mapping[str, Any]]


@dataclass(frozen=True)
class GroundingDiagnostics:
    """Summary of citation-validity data available in a benchmark report."""

    report_path: Path
    total_entries: int
    entries_with_grounding_rate: int
    mean_grounding_rate: float
    span_evidence_count: int
    valid_span_count: int
    invalid_span_count: int
    citation_validity_rate: float | None
    hallucinated_citation_rate: float | None
    grounded_matched: int
    grounded_wrong_or_over: int
    ungrounded_matched: int
    ungrounded_wrong_or_over: int
    missing_span_evidence: bool


def latest_report_path(reports_dir: Path = LAYER3_REPORTS_DIR) -> Path:
    """Return the newest layer-3 report by modification time."""
    candidates = list(reports_dir.glob("eval_*.json"))
    if not candidates:
        raise FileNotFoundError(f"No eval_*.json reports found in {reports_dir}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _load_report(report_path: Path) -> RawReport:
    with report_path.open(encoding="utf-8") as file_obj:
        return cast(RawReport, json.load(file_obj))


def _float_value(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def _entries(report: RawReport) -> list[Mapping[str, Any]]:
    per_entry = report.get("per_entry", [])
    if not isinstance(per_entry, list):
        return []
    return [entry for entry in per_entry if isinstance(entry, Mapping)]


def _field_matches(entry: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    field_matches = entry.get("field_matches", [])
    if not isinstance(field_matches, list):
        return []
    return [item for item in field_matches if isinstance(item, Mapping)]


def _span_from_match(field_match: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for key in ("source_span", "source", "raw_source"):
        span = field_match.get(key)
        if isinstance(span, Mapping):
            return span
    return None


def _has_valid_span(span: Mapping[str, Any]) -> bool:
    text = (
        span.get("text")
        or span.get("text_snippet")
        or span.get("raw_text")
        or span.get("source_text")
    )
    start = span["start"] if "start" in span else span.get("start_offset")
    end = span["end"] if "end" in span else span.get("end_offset")
    return isinstance(text, str) and bool(text.strip()) and isinstance(start, int) and isinstance(end, int) and end > start


def _is_wrong_or_over(field_match: Mapping[str, Any]) -> bool:
    match_type = field_match.get("match_type")
    extras = field_match.get("extra_found_values", [])
    has_extras = isinstance(extras, list) and bool(extras)
    return match_type == "wrong_value" or has_extras


def _safe_rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def build_grounding_diagnostics(report_path: Path) -> GroundingDiagnostics:
    """Build source-grounding diagnostics from one layer-3 report."""
    report = _load_report(report_path)
    entries = _entries(report)
    grounding_rates = [
        rate
        for entry in entries
        if (rate := _float_value(entry.get("grounding_rate"))) is not None
    ]

    span_evidence_count = 0
    valid_span_count = 0
    invalid_span_count = 0
    grounded_matched = 0
    grounded_wrong_or_over = 0
    ungrounded_matched = 0
    ungrounded_wrong_or_over = 0

    for entry in entries:
        for field_match in _field_matches(entry):
            span = _span_from_match(field_match)
            has_span_record = span is not None
            valid_span = bool(span and _has_valid_span(span))
            if has_span_record:
                span_evidence_count += 1
                if valid_span:
                    valid_span_count += 1
                else:
                    invalid_span_count += 1

            matched = bool(field_match.get("matched"))
            wrong_or_over = _is_wrong_or_over(field_match)
            if valid_span:
                grounded_matched += int(matched)
                grounded_wrong_or_over += int(wrong_or_over)
            elif has_span_record:
                ungrounded_matched += int(matched)
                ungrounded_wrong_or_over += int(wrong_or_over)

    return GroundingDiagnostics(
        report_path=report_path,
        total_entries=int(report.get("total_entries", len(entries)) or 0),
        entries_with_grounding_rate=len(grounding_rates),
        mean_grounding_rate=round(sum(grounding_rates) / len(grounding_rates), 4) if grounding_rates else 0.0,
        span_evidence_count=span_evidence_count,
        valid_span_count=valid_span_count,
        invalid_span_count=invalid_span_count,
        citation_validity_rate=_safe_rate(valid_span_count, span_evidence_count),
        hallucinated_citation_rate=_safe_rate(invalid_span_count, span_evidence_count),
        grounded_matched=grounded_matched,
        grounded_wrong_or_over=grounded_wrong_or_over,
        ungrounded_matched=ungrounded_matched,
        ungrounded_wrong_or_over=ungrounded_wrong_or_over,
        missing_span_evidence=span_evidence_count == 0,
    )


def _format_rate(value: float | None) -> str:
    if value is None:
        return "uncomputable"
    return f"{value:.4f}".rstrip("0").rstrip(".") if value % 1 else f"{value:.1f}"


def format_grounding_diagnostics(diagnostics: GroundingDiagnostics) -> str:
    """Format source-grounding diagnostics for terminal review."""
    lines = [
        f"REPORT: {diagnostics.report_path}",
        (
            f"N={diagnostics.total_entries} "
            f"entries_with_grounding_rate={diagnostics.entries_with_grounding_rate} "
            f"mean_grounding_rate={_format_rate(diagnostics.mean_grounding_rate)}"
        ),
        (
            f"CVR={_format_rate(diagnostics.citation_validity_rate)} "
            f"HCR={_format_rate(diagnostics.hallucinated_citation_rate)} "
            f"span_evidence={diagnostics.span_evidence_count} "
            f"valid={diagnostics.valid_span_count} "
            f"invalid={diagnostics.invalid_span_count}"
        ),
        (
            "grounded: "
            f"matched={diagnostics.grounded_matched} "
            f"wrong_or_over={diagnostics.grounded_wrong_or_over}"
        ),
        (
            "ungrounded: "
            f"matched={diagnostics.ungrounded_matched} "
            f"wrong_or_over={diagnostics.ungrounded_wrong_or_over}"
        ),
    ]
    if diagnostics.missing_span_evidence:
        lines.append(
            "WARNING: CVR/HCR are uncomputable because the report has missing per-evidence source spans."
        )
    return "\n".join(lines)


def main() -> None:
    """Run grounding diagnostics against the latest layer-3 report."""
    print(format_grounding_diagnostics(build_grounding_diagnostics(latest_report_path())))


if __name__ == "__main__":
    main()
