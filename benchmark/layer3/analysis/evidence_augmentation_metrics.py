"""Multilingual evidence augmentation matrix metrics for Layer 3 benchmarks."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import re
import time
from typing import Any, Mapping, TypedDict, cast

from benchmark.layer3.evaluate import GROUND_TRUTH_DIR, REPORTS_DIR


class EvidenceAugmentationMatrixPayload(TypedDict):
    """Serializable evidence augmentation matrix."""

    english_only_evidence_count: int
    multilingual_evidence_count: int
    non_english_added_evidence_count: int
    duplicated_evidence_count: int
    conflicting_evidence_count: int
    traceable_added_evidence_count: int
    potential_acmg_evidence_type_counts: Mapping[str, int]


class EvidenceAugmentationMetricPayload(TypedDict):
    """Serializable aggregate augmentation metrics."""

    evidence_coverage_gain: float
    non_english_evidence_yield: float
    unique_evidence_gain: int
    traceable_augmentation_rate: float
    interpretation_relevant_evidence_gain: float
    reviewer_burden: float


class EvidenceAugmentationCasePayload(TypedDict):
    """Serializable per-case augmentation report."""

    entry_id: str
    target_gene: str
    target_disease: str
    matrix: EvidenceAugmentationMatrixPayload
    metrics: EvidenceAugmentationMetricPayload


class EvidenceAugmentationReportPayload(TypedDict):
    """Serializable augmentation report."""

    evaluation_id: str
    timestamp: str
    config: Mapping[str, object]
    overall: EvidenceAugmentationMetricPayload
    per_case: list[EvidenceAugmentationCasePayload]
    warnings: list[str]


@dataclass(frozen=True)
class AugmentationMetricConfig:
    """Configuration for evidence augmentation metrics."""

    ground_truth_root: Path = GROUND_TRUTH_DIR
    reports_dir: Path = REPORTS_DIR
    entry_ids: tuple[str, ...] = ()
    limit: int | None = None


@dataclass(frozen=True)
class EvidenceAugmentationMatrix:
    """Evidence-count matrix for one variant / gene-disease case."""

    english_only_evidence_count: int
    multilingual_evidence_count: int
    non_english_added_evidence_count: int
    duplicated_evidence_count: int
    conflicting_evidence_count: int
    traceable_added_evidence_count: int
    potential_acmg_evidence_type_counts: Mapping[str, int]


@dataclass(frozen=True)
class EvidenceAugmentationMetrics:
    """Derived augmentation metrics."""

    evidence_coverage_gain: float
    non_english_evidence_yield: float
    unique_evidence_gain: int
    traceable_augmentation_rate: float
    interpretation_relevant_evidence_gain: float
    reviewer_burden: float


@dataclass(frozen=True)
class EvidenceAugmentationCaseReport:
    """Per-case evidence augmentation report."""

    entry_id: str
    target_gene: str
    target_disease: str
    matrix: EvidenceAugmentationMatrix
    metrics: EvidenceAugmentationMetrics


@dataclass(frozen=True)
class EvidenceAugmentationReport:
    """Complete evidence augmentation report."""

    config: AugmentationMetricConfig
    overall: EvidenceAugmentationMetrics
    per_case: tuple[EvidenceAugmentationCaseReport, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class _EvidenceKey:
    """Normalized identity for de-duplication."""

    field_id: str
    value: str


def build_evidence_augmentation_report(config: AugmentationMetricConfig) -> EvidenceAugmentationReport:
    """Build multilingual evidence augmentation metrics from Phase 2 artifacts."""
    cases: list[EvidenceAugmentationCaseReport] = []
    warnings: list[str] = []
    for entry in _entries(config):
        entry_id = str(entry.get("entry_id", ""))
        artifact_path = config.ground_truth_root / entry_id / "preprocessed" / "phase_2" / "extraction_result.json"
        if not artifact_path.exists():
            warnings.append(f"{entry_id}: missing extraction_result.json")
            continue
        items = _accepted_items(_load_json_object(artifact_path))
        matrix = _build_matrix(items)
        cases.append(
            EvidenceAugmentationCaseReport(
                entry_id=entry_id,
                target_gene=str(entry.get("gene_symbol", "")),
                target_disease=str(entry.get("disease_label", "")),
                matrix=matrix,
                metrics=_metrics_from_matrix(matrix),
            )
        )
    return EvidenceAugmentationReport(
        config=config,
        overall=_aggregate_metrics(tuple(cases)),
        per_case=tuple(cases),
        warnings=tuple(warnings),
    )


def write_evidence_augmentation_report(report: EvidenceAugmentationReport, reports_dir: Path | None = None) -> Path:
    """Persist an evidence augmentation report as JSON."""
    output_dir = reports_dir or report.config.reports_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"evidence_augmentation_metrics_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(evidence_augmentation_report_to_payload(report), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def evidence_augmentation_report_to_payload(report: EvidenceAugmentationReport) -> EvidenceAugmentationReportPayload:
    """Convert an augmentation report to a JSON-serializable payload."""
    return {
        "evaluation_id": f"evidence_augmentation_metrics_{time.strftime('%Y%m%d_%H%M%S')}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {
            "ground_truth_root": str(report.config.ground_truth_root),
            "entry_ids": list(report.config.entry_ids),
            "limit": report.config.limit,
        },
        "overall": _metrics_payload(report.overall),
        "per_case": [_case_payload(case) for case in report.per_case],
        "warnings": list(report.warnings),
    }


def format_evidence_augmentation_report(report: EvidenceAugmentationReport) -> str:
    """Format aggregate augmentation metrics for terminal review."""
    overall = report.overall
    return (
        f"EvidenceCoverageGain={overall.evidence_coverage_gain} "
        f"NonEnglishYield={overall.non_english_evidence_yield} "
        f"TraceableAugmentationRate={overall.traceable_augmentation_rate} "
        f"ReviewerBurden={overall.reviewer_burden} "
        f"N={len(report.per_case)}"
    )


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for evidence augmentation metrics."""
    parser = argparse.ArgumentParser(description="Compute multilingual evidence augmentation metrics.")
    parser.add_argument("--ground-truth-root", type=Path, default=GROUND_TRUTH_DIR)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--entries", nargs="*", default=())
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    report = build_evidence_augmentation_report(
        AugmentationMetricConfig(
            ground_truth_root=args.ground_truth_root,
            reports_dir=args.reports_dir,
            entry_ids=tuple(args.entries),
            limit=args.limit,
        )
    )
    print(format_evidence_augmentation_report(report))
    if args.write:
        print(f"REPORT: {write_evidence_augmentation_report(report, reports_dir=args.reports_dir)}")


def _entries(config: AugmentationMetricConfig) -> list[Mapping[str, object]]:
    requested = set(config.entry_ids)
    selection_path = config.ground_truth_root / "selection.json"
    if selection_path.exists():
        raw_selection = json.loads(selection_path.read_text(encoding="utf-8"))
        if not isinstance(raw_selection, list):
            raise ValueError(f"Expected list in {selection_path}")
        entries = [cast(Mapping[str, object], item) for item in raw_selection if isinstance(item, Mapping)]
    else:
        entries = [{"entry_id": path.name} for path in sorted(config.ground_truth_root.iterdir()) if path.is_dir()]
    filtered = [entry for entry in entries if not requested or str(entry.get("entry_id", "")) in requested]
    return filtered[: config.limit] if config.limit is not None else filtered


def _accepted_items(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    reconciled = payload.get("reconciled_result")
    if isinstance(reconciled, Mapping):
        return _found_items(reconciled.get("evidence_items", []))
    items: list[Mapping[str, Any]] = []
    for track_key in ("original_result", "translated_result"):
        raw_track = payload.get(track_key)
        if isinstance(raw_track, Mapping):
            items.extend(_found_items(raw_track.get("evidence_items", [])))
    return items


def _found_items(raw_items: object) -> list[Mapping[str, Any]]:
    if not isinstance(raw_items, list):
        return []
    return [
        cast(Mapping[str, Any], item)
        for item in raw_items
        if isinstance(item, Mapping) and item.get("status") == "found"
    ]


def _build_matrix(items: list[Mapping[str, Any]]) -> EvidenceAugmentationMatrix:
    english_items = [item for item in items if _is_english(item)]
    non_english_items = [item for item in items if not _is_english(item)]
    english_keys = {_evidence_key(item) for item in english_items}
    non_english_added = [item for item in non_english_items if _evidence_key(item) not in english_keys]
    duplicated_count = sum(1 for item in non_english_items if _evidence_key(item) in english_keys)
    conflict_fields = _conflict_fields(items)
    acmg_counts = Counter(
        acmg_type
        for item in non_english_added
        for acmg_type in _potential_acmg_types(item)
    )
    return EvidenceAugmentationMatrix(
        english_only_evidence_count=len(english_items),
        multilingual_evidence_count=len(items),
        non_english_added_evidence_count=len(non_english_added),
        duplicated_evidence_count=duplicated_count,
        conflicting_evidence_count=len(conflict_fields),
        traceable_added_evidence_count=sum(1 for item in non_english_added if _has_traceable_source(item)),
        potential_acmg_evidence_type_counts=dict(sorted(acmg_counts.items())),
    )


def _metrics_from_matrix(matrix: EvidenceAugmentationMatrix) -> EvidenceAugmentationMetrics:
    added = matrix.non_english_added_evidence_count
    interpretation_relevant_count = sum(matrix.potential_acmg_evidence_type_counts.values())
    return EvidenceAugmentationMetrics(
        evidence_coverage_gain=_rate(added, matrix.english_only_evidence_count),
        non_english_evidence_yield=_rate(
            added + matrix.duplicated_evidence_count,
            matrix.multilingual_evidence_count,
        ),
        unique_evidence_gain=added,
        traceable_augmentation_rate=_rate(matrix.traceable_added_evidence_count, added),
        interpretation_relevant_evidence_gain=_rate(interpretation_relevant_count, added),
        reviewer_burden=_rate(matrix.conflicting_evidence_count, added),
    )


def _aggregate_metrics(cases: tuple[EvidenceAugmentationCaseReport, ...]) -> EvidenceAugmentationMetrics:
    english_count = sum(case.matrix.english_only_evidence_count for case in cases)
    multilingual_count = sum(case.matrix.multilingual_evidence_count for case in cases)
    added_count = sum(case.matrix.non_english_added_evidence_count for case in cases)
    duplicated_count = sum(case.matrix.duplicated_evidence_count for case in cases)
    traceable_count = sum(case.matrix.traceable_added_evidence_count for case in cases)
    conflict_count = sum(case.matrix.conflicting_evidence_count for case in cases)
    interpretation_relevant_count = sum(
        sum(case.matrix.potential_acmg_evidence_type_counts.values())
        for case in cases
    )
    return EvidenceAugmentationMetrics(
        evidence_coverage_gain=_rate(added_count, english_count),
        non_english_evidence_yield=_rate(added_count + duplicated_count, multilingual_count),
        unique_evidence_gain=added_count,
        traceable_augmentation_rate=_rate(traceable_count, added_count),
        interpretation_relevant_evidence_gain=_rate(interpretation_relevant_count, added_count),
        reviewer_burden=_rate(conflict_count, added_count),
    )


def _is_english(item: Mapping[str, Any]) -> bool:
    explicit = item.get("is_english")
    if isinstance(explicit, bool):
        return explicit
    language = str(item.get("evidence_source_language") or item.get("article_language") or "").strip().casefold()
    return language in {"en", "eng", "english"}


def _evidence_key(item: Mapping[str, Any]) -> _EvidenceKey:
    return _EvidenceKey(
        field_id=str(item.get("field_id", "")),
        value=_normalize_value(item.get("value")),
    )


def _conflict_fields(items: list[Mapping[str, Any]]) -> set[str]:
    values_by_field: defaultdict[str, set[str]] = defaultdict(set)
    languages_by_field: defaultdict[str, set[str]] = defaultdict(set)
    for item in items:
        field_id = str(item.get("field_id", ""))
        if not field_id:
            continue
        values_by_field[field_id].add(_normalize_value(item.get("value")))
        languages_by_field[field_id].add("en" if _is_english(item) else "non_en")
    return {
        field_id
        for field_id, values in values_by_field.items()
        if len(values) > 1 and len(languages_by_field[field_id]) > 1
    }


def _has_traceable_source(item: Mapping[str, Any]) -> bool:
    source = item.get("source") or item.get("raw_source")
    if not isinstance(source, Mapping):
        return False
    span_id = source.get("span_id")
    text = source.get("text_snippet") or source.get("text") or source.get("raw_text")
    return isinstance(span_id, str) and bool(span_id.strip()) and isinstance(text, str) and bool(text.strip())


def _potential_acmg_types(item: Mapping[str, Any]) -> tuple[str, ...]:
    codes = item.get("assigned_acmg_codes")
    if isinstance(codes, list):
        mapped = tuple(_map_acmg_code(str(code)) for code in codes if _map_acmg_code(str(code)))
        if mapped:
            return tuple(sorted(set(mapped)))
    field_id = str(item.get("field_id", "")).casefold()
    if "functional" in field_id or "assay" in field_id:
        return ("PS3/BS3",)
    if "segregation" in field_id:
        return ("PP1",)
    if "frequency" in field_id or "allele" in field_id:
        return ("PM2/BA1/BS1",)
    if "phenotype" in field_id or "case" in field_id:
        return ("phenotype/case evidence",)
    return ()


def _map_acmg_code(code: str) -> str:
    normalized = code.strip().upper()
    if normalized in {"PS3", "BS3"}:
        return "PS3/BS3"
    if normalized == "PP1":
        return "PP1"
    if normalized in {"PM2", "BA1", "BS1"}:
        return "PM2/BA1/BS1"
    if normalized in {"PP4"}:
        return "phenotype/case evidence"
    return ""


def _normalize_value(value: object) -> str:
    if isinstance(value, list):
        return "|".join(sorted(_normalize_text(str(item)) for item in value if _normalize_text(str(item))))
    return _normalize_text(str(value or ""))


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _case_payload(case: EvidenceAugmentationCaseReport) -> EvidenceAugmentationCasePayload:
    return {
        "entry_id": case.entry_id,
        "target_gene": case.target_gene,
        "target_disease": case.target_disease,
        "matrix": _matrix_payload(case.matrix),
        "metrics": _metrics_payload(case.metrics),
    }


def _matrix_payload(matrix: EvidenceAugmentationMatrix) -> EvidenceAugmentationMatrixPayload:
    return {
        "english_only_evidence_count": matrix.english_only_evidence_count,
        "multilingual_evidence_count": matrix.multilingual_evidence_count,
        "non_english_added_evidence_count": matrix.non_english_added_evidence_count,
        "duplicated_evidence_count": matrix.duplicated_evidence_count,
        "conflicting_evidence_count": matrix.conflicting_evidence_count,
        "traceable_added_evidence_count": matrix.traceable_added_evidence_count,
        "potential_acmg_evidence_type_counts": matrix.potential_acmg_evidence_type_counts,
    }


def _metrics_payload(metrics: EvidenceAugmentationMetrics) -> EvidenceAugmentationMetricPayload:
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
