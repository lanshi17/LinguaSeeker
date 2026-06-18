"""Paired G2 statistics for BIBM reconcile ablation reports."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from math import comb
from pathlib import Path
import random
import time
from typing import Any, Mapping, TypedDict, cast

from benchmark.core import REPORTS_DIR

DEFAULT_BASELINE_STRATEGY = "grounded_hard_rule"
DEFAULT_CANDIDATE_STRATEGY = "context_verifier_reconcile"
DEFAULT_BOOTSTRAP_SAMPLES = 10_000
DEFAULT_SEED = 20260613
DEFAULT_MIN_MAIN_PAPER_N = 30


class RawStrategyPayload(TypedDict, total=False):
    """Loose persisted strategy shape from reconcile ablation JSON."""

    strategy: str
    total_entries: int
    status_counts: Mapping[str, int]
    per_entry: list[Mapping[str, Any]]


class RawAblationPayload(TypedDict, total=False):
    """Loose persisted reconcile ablation report shape."""

    evaluation_id: str
    strategies: list[RawStrategyPayload]


class G2StatisticsPayload(TypedDict):
    """Serializable G2 statistics payload."""

    source_report_path: str
    baseline_strategy: str
    candidate_strategy: str
    sample_size: int
    baseline_f1: float
    candidate_f1: float
    delta_f1: float
    bootstrap_samples: int
    bootstrap_ci_low: float
    bootstrap_ci_high: float
    sign_test_p: float
    significant: bool
    main_paper_ready: bool
    baseline_over_extractions: int
    candidate_over_extractions: int
    delta_over_extractions: int
    baseline_hcr: float | None
    candidate_hcr: float | None
    delta_hcr: float | None
    warnings: list[str]


@dataclass(frozen=True)
class EntryCounts:
    """Field-level counts for one entry under one strategy."""

    entry_id: str
    pipeline_status: str
    true_positives: int
    false_positives: int
    false_negatives: int
    over_extractions: int
    span_evidence: int
    invalid_spans: int


@dataclass(frozen=True)
class G2Statistics:
    """Paired statistical gate for one reconcile ablation comparison."""

    source_report_path: Path
    baseline_strategy: str
    candidate_strategy: str
    sample_size: int
    baseline_metric: float
    candidate_metric: float
    delta_metric: float
    bootstrap_samples: int
    bootstrap_ci_low: float
    bootstrap_ci_high: float
    sign_test_p: float
    significant: bool
    main_paper_ready: bool
    baseline_over_extractions: int
    candidate_over_extractions: int
    delta_over_extractions: int
    baseline_hcr: float | None
    candidate_hcr: float | None
    delta_hcr: float | None
    warnings: tuple[str, ...]


def build_g2_statistics(
    report_path: Path,
    *,
    baseline_strategy: str = DEFAULT_BASELINE_STRATEGY,
    candidate_strategy: str = DEFAULT_CANDIDATE_STRATEGY,
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    seed: int = DEFAULT_SEED,
    min_main_paper_n: int = DEFAULT_MIN_MAIN_PAPER_N,
) -> G2Statistics:
    """Build paired bootstrap/sign-test statistics from a reconcile ablation report."""
    if bootstrap_samples < 1:
        raise ValueError("bootstrap_samples must be >= 1")
    report = _load_report(report_path)
    strategy_entries = _strategy_entries(report)
    baseline_entries = _counts_by_entry(_required_strategy(strategy_entries, baseline_strategy))
    candidate_entries = _counts_by_entry(_required_strategy(strategy_entries, candidate_strategy))
    common_entry_ids = tuple(sorted(set(baseline_entries) & set(candidate_entries)))
    if not common_entry_ids:
        raise ValueError(
            f"No common entries between {baseline_strategy} and {candidate_strategy}"
        )

    baseline_counts = tuple(baseline_entries[entry_id] for entry_id in common_entry_ids)
    candidate_counts = tuple(candidate_entries[entry_id] for entry_id in common_entry_ids)
    baseline_metric = _f1(_sum_counts(baseline_counts))
    candidate_metric = _f1(_sum_counts(candidate_counts))
    deltas = _paired_bootstrap_deltas(
        baseline_counts,
        candidate_counts,
        bootstrap_samples=bootstrap_samples,
        seed=seed,
    )
    bootstrap_ci_low = _round_metric(_percentile(deltas, 0.025))
    bootstrap_ci_high = _round_metric(_percentile(deltas, 0.975))
    sign_test_p = _round_metric(_paired_sign_test_p(baseline_counts, candidate_counts))
    non_completed_entries = _non_completed_count(baseline_counts, candidate_counts)
    significant = bootstrap_ci_low > 0.0 and sign_test_p < 0.05
    warnings = _warnings(
        sample_size=len(common_entry_ids),
        min_main_paper_n=min_main_paper_n,
        non_completed_entries=non_completed_entries,
        missing_baseline_entries=len(set(candidate_entries) - set(baseline_entries)),
        missing_candidate_entries=len(set(baseline_entries) - set(candidate_entries)),
        significant=significant,
    )
    baseline_over_extractions = sum(entry.over_extractions for entry in baseline_counts)
    candidate_over_extractions = sum(entry.over_extractions for entry in candidate_counts)
    baseline_hcr = _hcr(_sum_counts(baseline_counts))
    candidate_hcr = _hcr(_sum_counts(candidate_counts))
    return G2Statistics(
        source_report_path=report_path,
        baseline_strategy=baseline_strategy,
        candidate_strategy=candidate_strategy,
        sample_size=len(common_entry_ids),
        baseline_metric=baseline_metric,
        candidate_metric=candidate_metric,
        delta_metric=_round_metric(candidate_metric - baseline_metric),
        bootstrap_samples=bootstrap_samples,
        bootstrap_ci_low=bootstrap_ci_low,
        bootstrap_ci_high=bootstrap_ci_high,
        sign_test_p=sign_test_p,
        significant=significant,
        main_paper_ready=significant and len(common_entry_ids) >= min_main_paper_n and non_completed_entries == 0,
        baseline_over_extractions=baseline_over_extractions,
        candidate_over_extractions=candidate_over_extractions,
        delta_over_extractions=candidate_over_extractions - baseline_over_extractions,
        baseline_hcr=baseline_hcr,
        candidate_hcr=candidate_hcr,
        delta_hcr=_optional_delta(candidate_hcr, baseline_hcr),
        warnings=warnings,
    )


def g2_statistics_to_payload(statistics: G2Statistics) -> G2StatisticsPayload:
    """Convert G2 statistics to a JSON-serializable payload."""
    return {
        "source_report_path": str(statistics.source_report_path),
        "baseline_strategy": statistics.baseline_strategy,
        "candidate_strategy": statistics.candidate_strategy,
        "sample_size": statistics.sample_size,
        "baseline_f1": statistics.baseline_metric,
        "candidate_f1": statistics.candidate_metric,
        "delta_f1": statistics.delta_metric,
        "bootstrap_samples": statistics.bootstrap_samples,
        "bootstrap_ci_low": statistics.bootstrap_ci_low,
        "bootstrap_ci_high": statistics.bootstrap_ci_high,
        "sign_test_p": statistics.sign_test_p,
        "significant": statistics.significant,
        "main_paper_ready": statistics.main_paper_ready,
        "baseline_over_extractions": statistics.baseline_over_extractions,
        "candidate_over_extractions": statistics.candidate_over_extractions,
        "delta_over_extractions": statistics.delta_over_extractions,
        "baseline_hcr": statistics.baseline_hcr,
        "candidate_hcr": statistics.candidate_hcr,
        "delta_hcr": statistics.delta_hcr,
        "warnings": list(statistics.warnings),
    }


def write_g2_statistics(
    statistics: G2Statistics,
    reports_dir: Path = REPORTS_DIR,
) -> Path:
    """Persist a G2 statistics report."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"g2_statistics_{time.strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(
        json.dumps(g2_statistics_to_payload(statistics), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_path


def format_g2_statistics(statistics: G2Statistics) -> str:
    """Format G2 statistics for terminal review."""
    lines = [
        f"REPORT: {statistics.source_report_path}",
        (
            f"{statistics.candidate_strategy} vs {statistics.baseline_strategy}: "
            f"N={statistics.sample_size} "
            f"candidate_f1={statistics.candidate_metric} "
            f"baseline_f1={statistics.baseline_metric} "
            f"delta_f1={statistics.delta_metric}"
        ),
        (
            f"95% CI=[{statistics.bootstrap_ci_low}, {statistics.bootstrap_ci_high}] "
            f"sign_test_p={statistics.sign_test_p} "
            f"significant={statistics.significant} "
            f"main_paper_ready={statistics.main_paper_ready}"
        ),
        (
            f"over_extractions: candidate={statistics.candidate_over_extractions} "
            f"baseline={statistics.baseline_over_extractions} "
            f"delta={statistics.delta_over_extractions}"
        ),
        (
            f"HCR: candidate={_format_optional(statistics.candidate_hcr)} "
            f"baseline={_format_optional(statistics.baseline_hcr)} "
            f"delta={_format_optional(statistics.delta_hcr)}"
        ),
    ]
    lines.extend(f"WARNING: {warning}" for warning in statistics.warnings)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for G2 paired statistics."""
    parser = argparse.ArgumentParser(description="Compute paired G2 statistics for reconcile ablations.")
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--baseline-strategy", default=DEFAULT_BASELINE_STRATEGY)
    parser.add_argument("--candidate-strategy", default=DEFAULT_CANDIDATE_STRATEGY)
    parser.add_argument("--bootstrap-samples", type=int, default=DEFAULT_BOOTSTRAP_SAMPLES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--min-main-paper-n", type=int, default=DEFAULT_MIN_MAIN_PAPER_N)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    report_path = args.report or latest_reconcile_ablation_report()
    statistics = build_g2_statistics(
        report_path,
        baseline_strategy=args.baseline_strategy,
        candidate_strategy=args.candidate_strategy,
        bootstrap_samples=args.bootstrap_samples,
        seed=args.seed,
        min_main_paper_n=args.min_main_paper_n,
    )
    print(format_g2_statistics(statistics))
    if args.write:
        output_path = write_g2_statistics(statistics)
        print(f"REPORT: {output_path}")


def latest_reconcile_ablation_report(reports_dir: Path = REPORTS_DIR) -> Path:
    """Return the newest reconcile ablation report by modification time."""
    candidates = list(reports_dir.glob("reconcile_ablation_*.json"))
    if not candidates:
        raise FileNotFoundError(f"No reconcile_ablation_*.json reports found in {reports_dir}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


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


def _counts_by_entry(entries: list[Mapping[str, Any]]) -> Mapping[str, EntryCounts]:
    return {
        str(entry["entry_id"]): _entry_counts(entry)
        for entry in entries
        if "entry_id" in entry
    }


def _entry_counts(entry: Mapping[str, Any]) -> EntryCounts:
    field_matches = _field_matches(entry)
    true_positives = sum(1 for match in field_matches if bool(match.get("matched")))
    false_positives = sum(
        1
        for match in field_matches
        if match.get("match_type") == "wrong_value"
    ) + sum(len(_extra_values(match)) for match in field_matches)
    false_negatives = sum(
        1
        for match in field_matches
        if match.get("match_type") in ("missing", "none")
    )
    span_evidence = 0
    invalid_spans = 0
    for match in field_matches:
        span = match.get("source_span")
        if isinstance(span, Mapping):
            span_evidence += 1
            invalid_spans += int(not _has_valid_span(span))
    return EntryCounts(
        entry_id=str(entry.get("entry_id", "")),
        pipeline_status=str(entry.get("pipeline_status", "")),
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        over_extractions=sum(len(_extra_values(match)) for match in field_matches),
        span_evidence=span_evidence,
        invalid_spans=invalid_spans,
    )


def _field_matches(entry: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    field_matches = entry.get("field_matches", [])
    if not isinstance(field_matches, list):
        return []
    return [match for match in field_matches if isinstance(match, Mapping)]


def _extra_values(field_match: Mapping[str, Any]) -> list[object]:
    extra_values = field_match.get("extra_found_values", [])
    return extra_values if isinstance(extra_values, list) else []


def _has_valid_span(span: Mapping[str, Any]) -> bool:
    text = span.get("text") or span.get("text_snippet")
    start = span["start"] if "start" in span else span.get("start_offset")
    end = span["end"] if "end" in span else span.get("end_offset")
    return isinstance(text, str) and bool(text.strip()) and isinstance(start, int) and isinstance(end, int) and end > start


def _sum_counts(entries: tuple[EntryCounts, ...]) -> EntryCounts:
    return EntryCounts(
        entry_id="aggregate",
        pipeline_status="aggregate",
        true_positives=sum(entry.true_positives for entry in entries),
        false_positives=sum(entry.false_positives for entry in entries),
        false_negatives=sum(entry.false_negatives for entry in entries),
        over_extractions=sum(entry.over_extractions for entry in entries),
        span_evidence=sum(entry.span_evidence for entry in entries),
        invalid_spans=sum(entry.invalid_spans for entry in entries),
    )


def _precision(counts: EntryCounts) -> float:
    denominator = counts.true_positives + counts.false_positives
    return counts.true_positives / denominator if denominator else 0.0


def _recall(counts: EntryCounts) -> float:
    denominator = counts.true_positives + counts.false_negatives
    return counts.true_positives / denominator if denominator else 0.0


def _f1(counts: EntryCounts) -> float:
    precision = _precision(counts)
    recall = _recall(counts)
    return _round_metric(2 * precision * recall / (precision + recall)) if precision + recall else 0.0


def _hcr(counts: EntryCounts) -> float | None:
    if counts.span_evidence == 0:
        return None
    return _round_metric(counts.invalid_spans / counts.span_evidence)


def _paired_bootstrap_deltas(
    baseline_counts: tuple[EntryCounts, ...],
    candidate_counts: tuple[EntryCounts, ...],
    *,
    bootstrap_samples: int,
    seed: int,
) -> list[float]:
    rng = random.Random(seed)
    sample_size = len(baseline_counts)
    deltas: list[float] = []
    for _ in range(bootstrap_samples):
        indices = [rng.randrange(sample_size) for _ in range(sample_size)]
        baseline_sample = tuple(baseline_counts[index] for index in indices)
        candidate_sample = tuple(candidate_counts[index] for index in indices)
        deltas.append(_round_metric(_f1(_sum_counts(candidate_sample)) - _f1(_sum_counts(baseline_sample))))
    return deltas


def _paired_sign_test_p(
    baseline_counts: tuple[EntryCounts, ...],
    candidate_counts: tuple[EntryCounts, ...],
) -> float:
    positives = 0
    negatives = 0
    for baseline_entry, candidate_entry in zip(baseline_counts, candidate_counts, strict=True):
        delta = _f1(_sum_counts((candidate_entry,))) - _f1(_sum_counts((baseline_entry,)))
        positives += int(delta > 0)
        negatives += int(delta < 0)
    trials = positives + negatives
    if trials == 0:
        return 1.0
    tail = sum(comb(trials, index) for index in range(min(positives, negatives) + 1)) / (2 ** trials)
    return min(1.0, 2 * tail)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("Cannot compute percentile of an empty sample")
    sorted_values = sorted(values)
    rank = percentile * (len(sorted_values) - 1)
    lower_index = int(rank)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = rank - lower_index
    return sorted_values[lower_index] + (sorted_values[upper_index] - sorted_values[lower_index]) * fraction


def _non_completed_count(
    baseline_counts: tuple[EntryCounts, ...],
    candidate_counts: tuple[EntryCounts, ...],
) -> int:
    return sum(
        1
        for baseline_entry, candidate_entry in zip(baseline_counts, candidate_counts, strict=True)
        if baseline_entry.pipeline_status != "completed" or candidate_entry.pipeline_status != "completed"
    )


def _warnings(
    *,
    sample_size: int,
    min_main_paper_n: int,
    non_completed_entries: int,
    missing_baseline_entries: int,
    missing_candidate_entries: int,
    significant: bool,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if sample_size < min_main_paper_n:
        warnings.append(
            f"sample_size={sample_size} below main-paper threshold N={min_main_paper_n}; treat as smoke/diagnostic only"
        )
    if non_completed_entries:
        warnings.append(
            f"non_completed_entries={non_completed_entries}; all paired ablation entries must complete before G2"
        )
    if missing_baseline_entries or missing_candidate_entries:
        warnings.append(
            "strategy_entry_mismatch="
            f"missing_from_baseline:{missing_baseline_entries},"
            f"missing_from_candidate:{missing_candidate_entries}"
        )
    if not significant:
        warnings.append("paired_delta_not_significant; do not claim superiority")
    return tuple(warnings)


def _optional_delta(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return _round_metric(left - right)


def _format_optional(value: float | None) -> str:
    return "uncomputable" if value is None else str(value)


def _round_metric(value: float) -> float:
    return round(value, 4)


if __name__ == "__main__":
    main()
