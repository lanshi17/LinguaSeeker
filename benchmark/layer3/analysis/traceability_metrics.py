"""Formal traceability metrics for BIBM Main Paper experiments."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import re
import time
import unicodedata
from typing import Any, Mapping, TypedDict, cast

from benchmark.layer3.evaluate import GROUND_TRUTH_DIR, REPORTS_DIR


class TraceabilityMetricPayload(TypedDict):
    """Serializable traceability metric block."""

    citation_validity_rate: float | None
    hallucinated_citation_rate: float | None
    span_boundary_f1: float | None
    evidence_support_rate: float | None
    traceable_f1: float
    cross_lingual_consistency: float | None


class TraceabilityCountsPayload(TypedDict):
    """Serializable traceability count block."""

    citation_total: int
    citation_valid: int
    hallucinated: int
    span_boundary_tp: int
    span_boundary_fp: int
    span_boundary_fn: int
    evidence_total: int
    evidence_supported: int


class TraceabilityReportPayload(TypedDict):
    """Serializable traceability report."""

    report_path: str
    strategy_or_baseline_id: str
    entry_ids: list[str]
    overall: Mapping[str, object]
    by_field: Mapping[str, object]
    counts: TraceabilityCountsPayload
    warnings: list[str]


@dataclass(frozen=True)
class TraceabilityCounts:
    """Counts used to derive traceability metrics."""

    citation_total: int = 0
    citation_valid: int = 0
    hallucinated: int = 0
    span_boundary_tp: int = 0
    span_boundary_fp: int = 0
    span_boundary_fn: int = 0
    evidence_total: int = 0
    evidence_supported: int = 0


@dataclass(frozen=True)
class TraceabilityMetrics:
    """Traceability metrics for one report or field."""

    citation_validity_rate: float | None
    hallucinated_citation_rate: float | None
    span_boundary_f1: float | None
    evidence_support_rate: float | None
    traceable_f1: float
    cross_lingual_consistency: float | None


@dataclass(frozen=True)
class TraceabilityReport:
    """Complete traceability report for one strategy or baseline."""

    report_path: Path
    strategy_or_baseline_id: str
    entry_ids: tuple[str, ...]
    overall: TraceabilityMetrics
    by_field: Mapping[str, TraceabilityMetrics]
    counts: TraceabilityCounts
    warnings: tuple[str, ...]


def span_boundary_f1(predicted: str, gold: str) -> float:
    """Compute token-overlap F1 for a predicted source span against a support span."""
    predicted_tokens = _tokens(predicted)
    gold_tokens = _tokens(gold)
    if not predicted_tokens or not gold_tokens:
        return 0.0
    predicted_counts = Counter(predicted_tokens)
    gold_counts = Counter(gold_tokens)
    overlap = sum((predicted_counts & gold_counts).values())
    precision = overlap / len(predicted_tokens)
    recall = overlap / len(gold_tokens)
    return _round_metric(2 * precision * recall / (precision + recall)) if precision + recall else 0.0


def traceable_f1(*, extraction_f1: float, citation_validity_rate: float) -> float:
    """Compute extraction F1 constrained by citation-validity rate."""
    return _round_metric(extraction_f1 * citation_validity_rate)


def build_traceability_report(
    *,
    system_report_path: Path | None = None,
    strategy: str | None = None,
    baseline_report_path: Path | None = None,
    ground_truth_root: Path = GROUND_TRUTH_DIR,
) -> TraceabilityReport:
    """Build traceability metrics from a system strategy or baseline report."""
    report_path = _single_report_path(system_report_path, baseline_report_path)
    raw_report = _load_json_object(report_path)
    selected = _selected_report_payload(raw_report, strategy=strategy, baseline_report_path=baseline_report_path)
    strategy_or_baseline_id = _strategy_or_baseline_id(
        selected,
        strategy=strategy,
        baseline_report_path=baseline_report_path,
    )
    entries = _entries(selected)
    extraction_f1 = _aggregate_f1(selected)
    counts = _counts_for_entries(entries, ground_truth_root=ground_truth_root)
    by_field_counts = _counts_by_field(entries, ground_truth_root=ground_truth_root)
    by_field_metrics = {
        field_id: _metrics_from_counts(
            counts=field_counts,
            extraction_f1=_field_f1(selected, field_id),
            cross_lingual_consistency=None,
        )
        for field_id, field_counts in sorted(by_field_counts.items())
    }
    entry_ids = tuple(str(entry.get("entry_id", "")) for entry in entries if entry.get("entry_id"))
    cross_lingual_consistency = _cross_lingual_consistency(entry_ids, ground_truth_root)
    warnings = _warnings(
        counts=counts,
        entries=entries,
        cross_lingual_consistency=cross_lingual_consistency,
        baseline_report_path=baseline_report_path,
    )
    return TraceabilityReport(
        report_path=report_path,
        strategy_or_baseline_id=strategy_or_baseline_id,
        entry_ids=entry_ids,
        overall=_metrics_from_counts(
            counts=counts,
            extraction_f1=extraction_f1,
            cross_lingual_consistency=cross_lingual_consistency,
        ),
        by_field=by_field_metrics,
        counts=counts,
        warnings=warnings,
    )


def traceability_report_to_payload(report: TraceabilityReport) -> TraceabilityReportPayload:
    """Convert a traceability report to a JSON-serializable payload."""
    return {
        "report_path": str(report.report_path),
        "strategy_or_baseline_id": report.strategy_or_baseline_id,
        "entry_ids": list(report.entry_ids),
        "overall": {"traceability": _metrics_payload(report.overall)},
        "by_field": {
            field_id: {"traceability": _metrics_payload(metrics)}
            for field_id, metrics in report.by_field.items()
        },
        "counts": _counts_payload(report.counts),
        "warnings": list(report.warnings),
    }


def write_traceability_report(
    report: TraceabilityReport,
    reports_dir: Path = REPORTS_DIR,
) -> Path:
    """Persist a traceability metrics report."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    safe_label = re.sub(r"[^A-Za-z0-9_]+", "_", report.strategy_or_baseline_id).strip("_") or "traceability"
    report_path = reports_dir / f"traceability_{safe_label}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(
        json.dumps(traceability_report_to_payload(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_path


def format_traceability_report(report: TraceabilityReport) -> str:
    """Format traceability metrics for terminal review."""
    overall = report.overall
    lines = [
        f"REPORT: {report.report_path}",
        f"strategy_or_baseline_id={report.strategy_or_baseline_id} N={len(report.entry_ids)}",
        (
            f"CVR={_format_optional(overall.citation_validity_rate)} "
            f"HCR={_format_optional(overall.hallucinated_citation_rate)} "
            f"SpanBoundaryF1={_format_optional(overall.span_boundary_f1)} "
            f"ESR={_format_optional(overall.evidence_support_rate)} "
            f"TraceableF1={overall.traceable_f1} "
            f"CLC={_format_optional(overall.cross_lingual_consistency)}"
        ),
    ]
    lines.extend(f"WARNING: {warning}" for warning in report.warnings)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for traceability metrics."""
    parser = argparse.ArgumentParser(description="Compute traceability metrics for Layer 3 reports.")
    parser.add_argument("--system-report", type=Path, default=None)
    parser.add_argument("--strategy", type=str, default=None)
    parser.add_argument("--baseline-report", type=Path, default=None)
    parser.add_argument("--ground-truth-root", type=Path, default=GROUND_TRUTH_DIR)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    report = build_traceability_report(
        system_report_path=args.system_report,
        strategy=args.strategy,
        baseline_report_path=args.baseline_report,
        ground_truth_root=args.ground_truth_root,
    )
    print(format_traceability_report(report))
    if args.write:
        print(f"REPORT: {write_traceability_report(report, reports_dir=args.reports_dir)}")


def _single_report_path(system_report_path: Path | None, baseline_report_path: Path | None) -> Path:
    if (system_report_path is None) == (baseline_report_path is None):
        raise ValueError("Exactly one of system_report_path or baseline_report_path is required")
    return system_report_path or cast(Path, baseline_report_path)


def _load_json_object(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Expected JSON object in {path}")
    return cast(Mapping[str, Any], payload)


def _selected_report_payload(
    report: Mapping[str, Any],
    *,
    strategy: str | None,
    baseline_report_path: Path | None,
) -> Mapping[str, Any]:
    if baseline_report_path is not None:
        return report
    if strategy is None:
        return report
    strategies = report.get("strategies", [])
    if not isinstance(strategies, list):
        raise ValueError("--strategy requires a report with strategies")
    for raw_strategy in strategies:
        if isinstance(raw_strategy, Mapping) and raw_strategy.get("strategy") == strategy:
            return cast(Mapping[str, Any], raw_strategy)
    available = ", ".join(
        str(raw_strategy.get("strategy", ""))
        for raw_strategy in strategies
        if isinstance(raw_strategy, Mapping)
    )
    raise ValueError(f"Strategy {strategy!r} not found. Available: {available}")


def _strategy_or_baseline_id(
    report: Mapping[str, Any],
    *,
    strategy: str | None,
    baseline_report_path: Path | None,
) -> str:
    if baseline_report_path is not None:
        return str(report.get("baseline_id") or report.get("label") or baseline_report_path.stem)
    return strategy or str(report.get("strategy") or "system")


def _entries(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    per_entry = report.get("per_entry", [])
    if not isinstance(per_entry, list):
        return []
    return [entry for entry in per_entry if isinstance(entry, Mapping)]


def _field_matches(entry: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw_matches = entry.get("field_matches", [])
    if not isinstance(raw_matches, list):
        return []
    return [field_match for field_match in raw_matches if isinstance(field_match, Mapping)]


def _aggregate_f1(report: Mapping[str, Any]) -> float:
    return _metric_from_aggregate(report, ("aggregates", "overall", "f1"))


def _field_f1(report: Mapping[str, Any], field_id: str) -> float:
    return _metric_from_aggregate(report, ("aggregates", "by_field", field_id, "f1"))


def _metric_from_aggregate(report: Mapping[str, Any], path: tuple[str, ...]) -> float:
    value: object = report
    for key in path:
        if not isinstance(value, Mapping):
            return 0.0
        value = value.get(key)
    return float(value) if isinstance(value, int | float) else 0.0


def _counts_for_entries(
    entries: list[Mapping[str, Any]],
    *,
    ground_truth_root: Path,
) -> TraceabilityCounts:
    counts = TraceabilityCounts()
    for entry in entries:
        counts = _add_counts(counts, _counts_for_entry(entry, ground_truth_root=ground_truth_root))
    return counts


def _counts_by_field(
    entries: list[Mapping[str, Any]],
    *,
    ground_truth_root: Path,
) -> Mapping[str, TraceabilityCounts]:
    counts_by_field: dict[str, TraceabilityCounts] = {}
    for entry in entries:
        entry_id = str(entry.get("entry_id", ""))
        source_text = _source_text(ground_truth_root, entry_id)
        for field_match in _field_matches(entry):
            field_id = str(field_match.get("field_id", ""))
            if not field_id:
                continue
            current = counts_by_field.get(field_id, TraceabilityCounts())
            counts_by_field[field_id] = _add_counts(
                current,
                _counts_for_field_match(field_match, source_text=source_text),
            )
    return counts_by_field


def _counts_for_entry(
    entry: Mapping[str, Any],
    *,
    ground_truth_root: Path,
) -> TraceabilityCounts:
    entry_id = str(entry.get("entry_id", ""))
    source_text = _source_text(ground_truth_root, entry_id)
    counts = TraceabilityCounts()
    for field_match in _field_matches(entry):
        counts = _add_counts(counts, _counts_for_field_match(field_match, source_text=source_text))
    return counts


def _counts_for_field_match(
    field_match: Mapping[str, Any],
    *,
    source_text: str,
) -> TraceabilityCounts:
    span = _span_from_match(field_match)
    if span is None:
        return TraceabilityCounts()
    predicted_text = _span_text(span)
    if not predicted_text:
        return TraceabilityCounts(citation_total=1, hallucinated=1, evidence_total=1)
    canonical_text = _canonical_support_text(span, source_text)
    valid = _span_maps_to_source(span, source_text, predicted_text)
    boundary = _boundary_counts(predicted_text, _gold_or_canonical_text(field_match, canonical_text, predicted_text))
    evidence_supported = int(bool(field_match.get("matched")))
    return TraceabilityCounts(
        citation_total=1,
        citation_valid=int(valid),
        hallucinated=int(not valid),
        span_boundary_tp=boundary.span_boundary_tp,
        span_boundary_fp=boundary.span_boundary_fp,
        span_boundary_fn=boundary.span_boundary_fn,
        evidence_total=1,
        evidence_supported=evidence_supported,
    )


def _span_from_match(field_match: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for key in ("source_span", "source", "raw_source"):
        span = field_match.get(key)
        if isinstance(span, Mapping):
            return cast(Mapping[str, Any], span)
    return None


def _span_text(span: Mapping[str, Any]) -> str:
    value = span.get("text") or span.get("text_snippet") or span.get("raw_text") or span.get("source_text")
    return str(value).strip() if isinstance(value, str) else ""


def _span_offsets(span: Mapping[str, Any]) -> tuple[int, int] | None:
    start = span["start"] if "start" in span else span.get("start_offset")
    end = span["end"] if "end" in span else span.get("end_offset")
    if isinstance(start, int) and isinstance(end, int) and end > start:
        return start, end
    return None


def _canonical_support_text(span: Mapping[str, Any], source_text: str) -> str:
    offsets = _span_offsets(span)
    if offsets is None:
        return ""
    start, end = offsets
    if start < 0 or end > len(source_text):
        return ""
    return source_text[start:end]


def _span_maps_to_source(span: Mapping[str, Any], source_text: str, predicted_text: str) -> bool:
    if not source_text:
        return False
    canonical_text = _canonical_support_text(span, source_text)
    if canonical_text and _normalized_contains(canonical_text, predicted_text):
        return True
    return _normalized_contains(source_text, predicted_text) or _token_sequence_contains(source_text, predicted_text)


def _gold_or_canonical_text(
    field_match: Mapping[str, Any],
    canonical_text: str,
    predicted_text: str,
) -> str:
    raw_gold = field_match.get("gold_source_span")
    if isinstance(raw_gold, Mapping):
        gold_text = _span_text(cast(Mapping[str, Any], raw_gold))
        if gold_text:
            return gold_text
    return canonical_text or predicted_text


def _boundary_counts(predicted_text: str, gold_text: str) -> TraceabilityCounts:
    predicted_counts = Counter(_tokens(predicted_text))
    gold_counts = Counter(_tokens(gold_text))
    overlap = sum((predicted_counts & gold_counts).values())
    return TraceabilityCounts(
        span_boundary_tp=overlap,
        span_boundary_fp=sum(predicted_counts.values()) - overlap,
        span_boundary_fn=sum(gold_counts.values()) - overlap,
    )


def _source_text(ground_truth_root: Path, entry_id: str) -> str:
    source_path = ground_truth_root / entry_id / "source.md"
    return source_path.read_text(encoding="utf-8") if source_path.exists() else ""


def _add_counts(left: TraceabilityCounts, right: TraceabilityCounts) -> TraceabilityCounts:
    return TraceabilityCounts(
        citation_total=left.citation_total + right.citation_total,
        citation_valid=left.citation_valid + right.citation_valid,
        hallucinated=left.hallucinated + right.hallucinated,
        span_boundary_tp=left.span_boundary_tp + right.span_boundary_tp,
        span_boundary_fp=left.span_boundary_fp + right.span_boundary_fp,
        span_boundary_fn=left.span_boundary_fn + right.span_boundary_fn,
        evidence_total=left.evidence_total + right.evidence_total,
        evidence_supported=left.evidence_supported + right.evidence_supported,
    )


def _metrics_from_counts(
    *,
    counts: TraceabilityCounts,
    extraction_f1: float,
    cross_lingual_consistency: float | None,
) -> TraceabilityMetrics:
    cvr = _safe_rate(counts.citation_valid, counts.citation_total)
    return TraceabilityMetrics(
        citation_validity_rate=cvr,
        hallucinated_citation_rate=_safe_rate(counts.hallucinated, counts.citation_total),
        span_boundary_f1=_span_boundary_f1_from_counts(counts),
        evidence_support_rate=_safe_rate(counts.evidence_supported, counts.evidence_total),
        traceable_f1=traceable_f1(extraction_f1=extraction_f1, citation_validity_rate=cvr or 0.0),
        cross_lingual_consistency=cross_lingual_consistency,
    )


def _span_boundary_f1_from_counts(counts: TraceabilityCounts) -> float | None:
    denominator_precision = counts.span_boundary_tp + counts.span_boundary_fp
    denominator_recall = counts.span_boundary_tp + counts.span_boundary_fn
    if not denominator_precision or not denominator_recall:
        return None
    precision = counts.span_boundary_tp / denominator_precision
    recall = counts.span_boundary_tp / denominator_recall
    return _round_metric(2 * precision * recall / (precision + recall)) if precision + recall else 0.0


def _cross_lingual_consistency(entry_ids: tuple[str, ...], ground_truth_root: Path) -> float | None:
    agreement_count = 0
    compared_count = 0
    for entry_id in entry_ids:
        extraction_path = ground_truth_root / entry_id / "preprocessed" / "phase_2" / "extraction_result.json"
        if not extraction_path.exists():
            continue
        payload = _load_json_object(extraction_path)
        original_values = _track_values(payload.get("original_result"))
        translated_values = _track_values(payload.get("translated_result"))
        for field_id in sorted(set(original_values) | set(translated_values)):
            compared_count += 1
            agreement_count += int(bool(original_values.get(field_id, set()) & translated_values.get(field_id, set())))
    return _safe_rate(agreement_count, compared_count)


def _track_values(raw_track: object) -> Mapping[str, set[str]]:
    if not isinstance(raw_track, Mapping):
        return {}
    raw_items = raw_track.get("evidence_items", [])
    if not isinstance(raw_items, list):
        return {}
    values: dict[str, set[str]] = {}
    for raw_item in raw_items:
        if not isinstance(raw_item, Mapping):
            continue
        status = raw_item.get("status")
        if status is not None and status != "found":
            continue
        field_id = str(raw_item.get("field_id", ""))
        value = raw_item.get("value")
        if not field_id or not isinstance(value, str) or not value.strip():
            continue
        values.setdefault(field_id, set()).add(_normalize_text(value))
    return values


def _warnings(
    *,
    counts: TraceabilityCounts,
    entries: list[Mapping[str, Any]],
    cross_lingual_consistency: float | None,
    baseline_report_path: Path | None,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if counts.citation_total == 0:
        warnings.append("baseline_has_no_citation_surface" if baseline_report_path else "system_has_no_citation_surface")
    if not _has_gold_source_spans(entries):
        warnings.append("no_gold_source_span_annotations; span_boundary_f1 uses canonical offset text when available")
    if cross_lingual_consistency is None:
        warnings.append("cross_lingual_consistency_uncomputable; missing dual-track artifacts")
    return tuple(warnings)


def _has_gold_source_spans(entries: list[Mapping[str, Any]]) -> bool:
    return any(
        isinstance(field_match.get("gold_source_span"), Mapping)
        for entry in entries
        for field_match in _field_matches(entry)
    )


def _metrics_payload(metrics: TraceabilityMetrics) -> TraceabilityMetricPayload:
    return {
        "citation_validity_rate": metrics.citation_validity_rate,
        "hallucinated_citation_rate": metrics.hallucinated_citation_rate,
        "span_boundary_f1": metrics.span_boundary_f1,
        "evidence_support_rate": metrics.evidence_support_rate,
        "traceable_f1": metrics.traceable_f1,
        "cross_lingual_consistency": metrics.cross_lingual_consistency,
    }


def _counts_payload(counts: TraceabilityCounts) -> TraceabilityCountsPayload:
    return {
        "citation_total": counts.citation_total,
        "citation_valid": counts.citation_valid,
        "hallucinated": counts.hallucinated,
        "span_boundary_tp": counts.span_boundary_tp,
        "span_boundary_fp": counts.span_boundary_fp,
        "span_boundary_fn": counts.span_boundary_fn,
        "evidence_total": counts.evidence_total,
        "evidence_supported": counts.evidence_supported,
    }


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _normalize_text(text))


def _token_sequence_contains(haystack: str, needle: str) -> bool:
    haystack_tokens = _tokens(haystack)
    needle_tokens = _tokens(needle)
    if not haystack_tokens or not needle_tokens:
        return False
    if _contains_subsequence(haystack_tokens, needle_tokens):
        return True
    return _contains_subsequence(_drop_articles(haystack_tokens), _drop_articles(needle_tokens))


def _contains_subsequence(haystack_tokens: list[str], needle_tokens: list[str]) -> bool:
    if len(needle_tokens) > len(haystack_tokens):
        return False
    window_size = len(needle_tokens)
    return any(
        haystack_tokens[index : index + window_size] == needle_tokens
        for index in range(len(haystack_tokens) - window_size + 1)
    )


def _drop_articles(tokens: list[str]) -> list[str]:
    return [token for token in tokens if token not in {"a", "an", "the"}]


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _normalized_contains(haystack: str, needle: str) -> bool:
    normalized_haystack = _normalize_text(haystack)
    normalized_needle = _normalize_text(needle)
    return bool(normalized_needle) and normalized_needle in normalized_haystack


def _safe_rate(numerator: int, denominator: int) -> float | None:
    return _round_metric(numerator / denominator) if denominator else None


def _round_metric(value: float) -> float:
    return round(value, 4)


def _format_optional(value: float | None) -> str:
    if value is None:
        return "uncomputable"
    return f"{value:.4f}".rstrip("0").rstrip(".") if value % 1 else f"{value:.1f}"


if __name__ == "__main__":
    main()
