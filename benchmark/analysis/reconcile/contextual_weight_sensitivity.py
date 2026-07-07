"""Replay contextual reconcile weight sensitivity over persisted Phase 2 artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from benchmark.core import (
    GROUND_TRUTH_UNIFIED_ROOT,
    EntryMetrics,
    compare_evidence,
    compute_aggregate_metrics,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualEvidenceExtractionResult,
    EvidenceItem,
    SourceLocation,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.contextual import (
    _accepted_rationale,
    _annotate_accepted,
    _score_candidate,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.contracts import (
    CandidateScore,
    ReconcileParams,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.core import (
    _Candidate,
    _build_candidates,
    _first_conflicting_score,
)
from src.core.standardize_entities_and_align_knowledge.context_pack.contracts import (
    TargetContextPack,
)
from src.core.standardize_entities_and_align_knowledge.context_pack.core import (
    build_context_pack_from_expected_json,
)

DEFAULT_MERGED_REPORT = Path("benchmark/data/reports/eval_unified_e8772325_retry_merged_20260706_003640.json")
DEFAULT_PIPELINE_ROOT = Path("data/pipeline")
DEFAULT_REPORTS_DIR = Path("benchmark/paper/reports/reconcile_weight_sensitivity")
DEFAULT_WEIGHTS = {
    "source": 0.30,
    "agreement": 0.20,
    "verifier_support": 0.20,
    "target_specificity": 0.15,
    "confidence": 0.10,
    "status": 0.05,
    "contradiction_penalty": 0.25,
}
POSITIVE_WEIGHT_KEYS = (
    "source",
    "agreement",
    "verifier_support",
    "target_specificity",
    "confidence",
    "status",
)


@dataclass(frozen=True)
class ContextualWeights:
    """Linear weights for the current contextual scorer decomposition."""

    name: str
    source: float
    agreement: float
    verifier_support: float
    target_specificity: float
    confidence: float
    status: float
    contradiction_penalty: float

    def positive_total(self) -> float:
        """Return the sum of additive feature weights."""
        return (
            self.source
            + self.agreement
            + self.verifier_support
            + self.target_specificity
            + self.confidence
            + self.status
        )


@dataclass(frozen=True)
class ScoredField:
    """Precomputed candidate score components for one field."""

    field_id: str
    scored: tuple[tuple[_Candidate, CandidateScore], ...]


@dataclass(frozen=True)
class PreparedEntry:
    """One entry with expected data and precomputed contextual score components."""

    entry_id: str
    gene_symbol: str
    classification: str
    moi: str
    source_dataset: str
    original_entry_id: str
    run_id: str
    expected_evidence: list[dict[str, Any]]
    expected_standardization: dict[str, str]
    context_pack: TargetContextPack
    fields: tuple[ScoredField, ...]


@dataclass(frozen=True)
class StrategyResult:
    """One weight strategy result row."""

    weights: ContextualWeights
    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    false_negatives: int
    changed_value_rate: float
    changed_expected_value_rate: float
    status_counts: dict[str, int]


@dataclass(frozen=True)
class ContextualWeightSensitivityReport:
    """Full W2 contextual weight-sensitivity replay result."""

    generated_at: str
    merged_report: Path
    pipeline_root: Path
    ground_truth_dir: Path
    entry_count: int
    missing_entries: tuple[str, ...]
    rows: tuple[StrategyResult, ...]


def run_contextual_weight_sensitivity(
    merged_report: Path = DEFAULT_MERGED_REPORT,
    pipeline_root: Path = DEFAULT_PIPELINE_ROOT,
    ground_truth_dir: Path = GROUND_TRUTH_UNIFIED_ROOT,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    *,
    write: bool = True,
) -> ContextualWeightSensitivityReport:
    """Run current 7-term contextual weight sensitivity with zero LLM calls."""
    prepared_entries, missing_entries = _prepare_entries(merged_report, pipeline_root, ground_truth_dir)
    strategies = _build_weight_grid()
    default_predictions = _prediction_signatures(prepared_entries, strategies[0])
    expected_fields = _expected_field_sets(prepared_entries)
    rows = tuple(
        _evaluate_strategy(strategy, prepared_entries, default_predictions, expected_fields)
        for strategy in strategies
    )
    report = ContextualWeightSensitivityReport(
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        merged_report=merged_report,
        pipeline_root=pipeline_root,
        ground_truth_dir=ground_truth_dir,
        entry_count=len(prepared_entries),
        missing_entries=tuple(missing_entries),
        rows=rows,
    )
    if write:
        _write_report(report, reports_dir)
    return report


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Replay W2 sensitivity using the current contextual 7-term scorer.",
    )
    parser.add_argument("--merged-report", type=Path, default=DEFAULT_MERGED_REPORT)
    parser.add_argument("--pipeline-root", type=Path, default=DEFAULT_PIPELINE_ROOT)
    parser.add_argument("--ground-truth-dir", type=Path, default=GROUND_TRUTH_UNIFIED_ROOT)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)

    report = run_contextual_weight_sensitivity(
        merged_report=args.merged_report,
        pipeline_root=args.pipeline_root,
        ground_truth_dir=args.ground_truth_dir,
        reports_dir=args.reports_dir,
        write=not args.no_write,
    )
    default_row = report.rows[0]
    best_row = max(report.rows, key=lambda row: row.f1)
    print(
        "contextual_7term: "
        f"N={report.entry_count} missing={len(report.missing_entries)} "
        f"default_F1={default_row.f1:.4f} best_F1={best_row.f1:.4f} "
        f"grid={len(report.rows)}"
    )


def _prepare_entries(
    merged_report: Path,
    pipeline_root: Path,
    ground_truth_dir: Path,
) -> tuple[list[PreparedEntry], list[str]]:
    report_payload = json.loads(merged_report.read_text(encoding="utf-8"))
    prepared_entries: list[PreparedEntry] = []
    missing_entries: list[str] = []
    for raw_entry in report_payload["per_entry"]:
        entry_id = str(raw_entry["entry_id"])
        run_id = str(raw_entry.get("run_id") or "")
        artifact_path = pipeline_root / run_id / "phase_2" / "extraction_result.json"
        expected_path = ground_truth_dir / entry_id / "expected.json"
        if not run_id or not artifact_path.exists() or not expected_path.exists():
            missing_entries.append(entry_id)
            continue
        expected_payload = json.loads(expected_path.read_text(encoding="utf-8"))
        result = DualEvidenceExtractionResult.model_validate_json(
            artifact_path.read_text(encoding="utf-8"),
        )
        context_pack = build_context_pack_from_expected_json(expected_path)
        prepared_entries.append(
            PreparedEntry(
                entry_id=entry_id,
                gene_symbol=str(raw_entry.get("gene_symbol", "")),
                classification=str(raw_entry.get("classification", "")),
                moi=str(raw_entry.get("moi", "")),
                source_dataset=str(raw_entry.get("source_dataset", "")),
                original_entry_id=str(raw_entry.get("original_entry_id", "")),
                run_id=run_id,
                expected_evidence=list(expected_payload.get("expected_evidence", [])),
                expected_standardization=dict(expected_payload.get("expected_standardization", {})),
                context_pack=context_pack,
                fields=_prepare_scored_fields(result, context_pack),
            )
        )
    return prepared_entries, missing_entries


def _prepare_scored_fields(
    result: DualEvidenceExtractionResult,
    context_pack: TargetContextPack,
) -> tuple[ScoredField, ...]:
    fields: list[ScoredField] = []
    for phenotype in (False, True):
        candidates = _build_candidates(
            result.original_result,
            result.translated_result,
            phenotype=phenotype,
        )
        for field_id in sorted({candidate.item.field_id for candidate in candidates}):
            field_candidates = tuple(candidate for candidate in candidates if candidate.item.field_id == field_id)
            scored = tuple(
                (candidate, _score_candidate(candidate, field_candidates, context_pack))
                for candidate in field_candidates
            )
            fields.append(ScoredField(field_id=field_id, scored=scored))
    return tuple(fields)


def _build_weight_grid() -> tuple[ContextualWeights, ...]:
    strategies: list[ContextualWeights] = [_weights_from_positive("default", DEFAULT_WEIGHTS)]
    seen = {tuple(_weight_values(strategies[0]))}

    for key in POSITIVE_WEIGHT_KEYS:
        for factor in (0.0, 0.5, 0.75, 1.25, 1.5):
            positive = {name: DEFAULT_WEIGHTS[name] for name in POSITIVE_WEIGHT_KEYS}
            positive[key] *= factor
            name = f"{key}_x{factor:g}_renorm"
            candidate = _weights_from_positive(name, positive)
            fingerprint = tuple(_weight_values(candidate))
            if fingerprint not in seen:
                seen.add(fingerprint)
                strategies.append(candidate)

    for penalty in (0.0, 0.10, 0.40, 0.50, 0.75):
        candidate = replace(strategies[0], name=f"contradiction_{penalty:.2f}", contradiction_penalty=penalty)
        fingerprint = tuple(_weight_values(candidate))
        if fingerprint not in seen:
            seen.add(fingerprint)
            strategies.append(candidate)

    presets = (
        ("source_heavy", {"source": 0.45, "agreement": 0.15, "verifier_support": 0.15, "target_specificity": 0.10, "confidence": 0.10, "status": 0.05}),
        ("verifier_heavy", {"source": 0.20, "agreement": 0.15, "verifier_support": 0.35, "target_specificity": 0.20, "confidence": 0.07, "status": 0.03}),
        ("target_heavy", {"source": 0.20, "agreement": 0.15, "verifier_support": 0.20, "target_specificity": 0.30, "confidence": 0.10, "status": 0.05}),
        ("agreement_heavy", {"source": 0.25, "agreement": 0.35, "verifier_support": 0.15, "target_specificity": 0.10, "confidence": 0.10, "status": 0.05}),
        ("confidence_status_heavy", {"source": 0.20, "agreement": 0.15, "verifier_support": 0.15, "target_specificity": 0.10, "confidence": 0.25, "status": 0.15}),
    )
    for name, positive in presets:
        candidate = _weights_from_positive(name, positive)
        fingerprint = tuple(_weight_values(candidate))
        if fingerprint not in seen:
            seen.add(fingerprint)
            strategies.append(candidate)

    return tuple(strategies)


def _weights_from_positive(
    name: str,
    positive_weights: dict[str, float],
    contradiction_penalty: float = DEFAULT_WEIGHTS["contradiction_penalty"],
) -> ContextualWeights:
    total = sum(max(0.0, positive_weights[key]) for key in POSITIVE_WEIGHT_KEYS)
    if total <= 0.0:
        raise ValueError("positive contextual weights must have a positive sum")
    normalized = {
        key: round(max(0.0, positive_weights[key]) / total, 6)
        for key in POSITIVE_WEIGHT_KEYS
    }
    return ContextualWeights(
        name=name,
        source=normalized["source"],
        agreement=normalized["agreement"],
        verifier_support=normalized["verifier_support"],
        target_specificity=normalized["target_specificity"],
        confidence=normalized["confidence"],
        status=normalized["status"],
        contradiction_penalty=round(contradiction_penalty, 6),
    )


def _evaluate_strategy(
    weights: ContextualWeights,
    entries: list[PreparedEntry],
    default_predictions: dict[str, dict[str, str]],
    expected_fields: dict[str, set[str]],
) -> StrategyResult:
    metrics = [_evaluate_entry(weights, entry) for entry in entries]
    aggregate = compute_aggregate_metrics(metrics)["overall"]
    predictions = _prediction_signatures(entries, weights)
    changed_rate = _changed_value_rate(predictions, default_predictions, expected_fields=None)
    expected_changed_rate = _changed_value_rate(predictions, default_predictions, expected_fields=expected_fields)
    return StrategyResult(
        weights=weights,
        precision=float(aggregate["precision"]),
        recall=float(aggregate["recall"]),
        f1=float(aggregate["f1"]),
        true_positives=int(aggregate["true_positives"]),
        false_positives=int(aggregate["false_positives"]),
        false_negatives=int(aggregate["false_negatives"]),
        changed_value_rate=changed_rate,
        changed_expected_value_rate=expected_changed_rate,
        status_counts=dict(Counter(metric.pipeline_status for metric in metrics)),
    )


def _evaluate_entry(weights: ContextualWeights, entry: PreparedEntry) -> EntryMetrics:
    extracted_items = _build_extracted_items(weights, entry)
    metrics = EntryMetrics(
        entry_id=entry.entry_id,
        gene_symbol=entry.gene_symbol,
        classification=entry.classification,
        language="en",
        moi=entry.moi,
        run_id=entry.run_id,
        pipeline_status="completed",
        source_dataset=entry.source_dataset,
        original_entry_id=entry.original_entry_id,
    )
    metrics.evidence_count = len(extracted_items)
    metrics.found_rate = (
        sum(1 for item in extracted_items if item["status"] == "found") / len(extracted_items)
        if extracted_items
        else 0.0
    )
    metrics.field_matches = compare_evidence(
        entry.expected_evidence,
        extracted_items,
        expected_standardization=entry.expected_standardization,
    )
    return metrics


def _build_extracted_items(
    weights: ContextualWeights,
    entry: PreparedEntry,
) -> list[dict[str, object]]:
    return [
        _to_scored_extracted_item(accepted, score)
        for accepted, score in _accepted_items(weights, entry.fields, entry.context_pack)
    ]


def _accepted_items(
    weights: ContextualWeights,
    fields: tuple[ScoredField, ...],
    context_pack: TargetContextPack,
) -> list[tuple[EvidenceItem, CandidateScore]]:
    params = ReconcileParams()
    accepted_items: list[tuple[EvidenceItem, CandidateScore]] = []
    for field in fields:
        ranked = sorted(
            (
                (candidate, _with_weighted_score(score, weights))
                for candidate, score in field.scored
            ),
            key=lambda entry: (
                -entry[1].score,
                entry[1].field_id,
                entry[1].normalized_value,
                entry[1].track.value,
            ),
        )
        if not ranked:
            continue
        accepted_candidate, accepted_score = ranked[0]
        competing_score = _first_conflicting_score(accepted_score, ranked)
        requires_review = (
            competing_score is not None
            and accepted_score.score - competing_score.score < params.conflict_margin
        )
        accepted = _annotate_accepted(
            accepted_candidate.item,
            _accepted_rationale(accepted_score, requires_review),
            accepted_score,
            requires_review,
            context_pack,
        )
        accepted_items.append((accepted, accepted_score))
    return accepted_items


def _with_weighted_score(score: CandidateScore, weights: ContextualWeights) -> CandidateScore:
    return replace(score, score=_weighted_score(score, weights))


def _weighted_score(score: CandidateScore, weights: ContextualWeights) -> float:
    """Calculate the current 7-term contextual formula with alternate weights."""
    return round(
        weights.source * score.source_score
        + weights.agreement * score.agreement_score
        + weights.verifier_support * score.verifier_support_score
        + weights.target_specificity * score.target_specificity_score
        + weights.confidence * score.confidence_score
        + weights.status * score.status_score
        - weights.contradiction_penalty * score.contradiction_penalty,
        12,
    )


def _prediction_signatures(
    entries: list[PreparedEntry],
    weights: ContextualWeights,
) -> dict[str, dict[str, str]]:
    signatures: dict[str, dict[str, str]] = {}
    for entry in entries:
        signatures[entry.entry_id] = {
            item["field_id"]: str(item.get("value", "")).strip().casefold()
            for item in _build_extracted_items(weights, entry)
            if item.get("field_id")
        }
    return signatures


def _expected_field_sets(entries: list[PreparedEntry]) -> dict[str, set[str]]:
    return {
        entry.entry_id: {str(item["field_id"]) for item in entry.expected_evidence}
        for entry in entries
    }


def _changed_value_rate(
    predictions: dict[str, dict[str, str]],
    default_predictions: dict[str, dict[str, str]],
    *,
    expected_fields: dict[str, set[str]] | None,
) -> float:
    changed = 0
    total = 0
    for entry_id, default_entry in default_predictions.items():
        candidate_entry = predictions.get(entry_id, {})
        if expected_fields is None:
            field_ids = set(default_entry) | set(candidate_entry)
        else:
            field_ids = expected_fields.get(entry_id, set())
        for field_id in field_ids:
            total += 1
            if default_entry.get(field_id) != candidate_entry.get(field_id):
                changed += 1
    return round(changed / total, 4) if total else 0.0


def _to_scored_extracted_item(
    item: EvidenceItem,
    score: CandidateScore,
) -> dict[str, object]:
    extracted = _to_extracted_item(item)
    extracted.update(_score_to_payload(score))
    return extracted


def _to_extracted_item(item: EvidenceItem) -> dict[str, object]:
    extracted: dict[str, object] = {
        "field_id": item.field_id,
        "status": item.status.value,
        "value": item.value,
        "confidence": item.confidence,
    }
    if item.source is not None:
        extracted["source_span"] = _source_to_payload(item.source)
    return extracted


def _score_to_payload(score: CandidateScore) -> dict[str, object]:
    return {
        "best_score": score.score,
        "source_score": score.source_score,
        "confidence_score": score.confidence_score,
        "agreement_score": score.agreement_score,
        "status_score": score.status_score,
        "verifier_support_score": score.verifier_support_score,
        "target_specificity_score": score.target_specificity_score,
        "contradiction_penalty": score.contradiction_penalty,
        "accepted_track": score.track.value,
        "normalized_value": score.normalized_value,
    }


def _source_to_payload(source: SourceLocation) -> dict[str, object]:
    return {
        "span_id": source.span_id,
        "page": source.page,
        "start_offset": source.start_offset,
        "end_offset": source.end_offset,
        "text_snippet": source.text_snippet,
        "source_precision": source.source_precision.value,
    }


def _write_report(
    report: ContextualWeightSensitivityReport,
    reports_dir: Path,
) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    stem = f"reconcile_contextual_weight_sensitivity_full150_{timestamp}"
    json_path = reports_dir / f"{stem}.json"
    csv_path = reports_dir / f"{stem}.csv"
    md_path = reports_dir / f"{stem}.md"
    json_path.write_text(
        json.dumps(_report_to_payload(report, csv_path, md_path), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_csv(report, csv_path)
    md_path.write_text(_render_markdown(report, json_path, csv_path), encoding="utf-8")


def _report_to_payload(
    report: ContextualWeightSensitivityReport,
    csv_path: Path,
    md_path: Path,
) -> dict[str, object]:
    default_row = report.rows[0]
    best_row = max(report.rows, key=lambda row: row.f1)
    worst_row = min(report.rows, key=lambda row: row.f1)
    return {
        "generated_at": report.generated_at,
        "scope": "full150_contextual_7term",
        "formula": (
            "source + agreement + verifier_support + target_specificity + "
            "confidence + status - contradiction_penalty"
        ),
        "default_weights": _weights_to_payload(default_row.weights),
        "inputs": {
            "merged_report": str(report.merged_report),
            "pipeline_root": str(report.pipeline_root),
            "ground_truth_dir": str(report.ground_truth_dir),
        },
        "entry_count": report.entry_count,
        "missing_entry_count": len(report.missing_entries),
        "missing_entries": list(report.missing_entries),
        "grid_size": len(report.rows),
        "summary": {
            "default_f1": default_row.f1,
            "best_strategy": best_row.weights.name,
            "best_f1": best_row.f1,
            "worst_strategy": worst_row.weights.name,
            "worst_f1": worst_row.f1,
            "f1_range": round(best_row.f1 - worst_row.f1, 4),
            "strategies_within_0_01_f1_of_default": sum(
                1 for row in report.rows if abs(row.f1 - default_row.f1) <= 0.01
            ),
            "strategies_within_0_02_f1_of_default": sum(
                1 for row in report.rows if abs(row.f1 - default_row.f1) <= 0.02
            ),
            "max_changed_value_rate_vs_default": max(row.changed_value_rate for row in report.rows),
            "max_changed_expected_value_rate_vs_default": max(
                row.changed_expected_value_rate for row in report.rows
            ),
        },
        "rows": [_row_to_payload(row) for row in report.rows],
        "csv": str(csv_path),
        "markdown": str(md_path),
        "caveats": [
            "This supersedes the old 4-term source/confidence/agreement/status W2 replay.",
            "Candidate score components are recomputed from persisted Phase 2 original/translated artifacts using the current contextual verifier code.",
            "The replay does not call LLMs or remote services.",
        ],
    }


def _write_csv(report: ContextualWeightSensitivityReport, csv_path: Path) -> None:
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(_row_to_payload(report.rows[0]).keys()),
        )
        writer.writeheader()
        for row in report.rows:
            writer.writerow(_row_to_payload(row))


def _render_markdown(
    report: ContextualWeightSensitivityReport,
    json_path: Path,
    csv_path: Path,
) -> str:
    default_row = report.rows[0]
    ranked_rows = sorted(report.rows, key=lambda row: (-row.f1, row.weights.name))
    best_row = ranked_rows[0]
    worst_row = min(report.rows, key=lambda row: row.f1)
    lines = [
        "# Contextual Reconcile Weight Sensitivity Full150",
        "",
        f"Generated at: `{report.generated_at}`",
        "",
        "This report replays W2 with the current contextual 7-term formula:",
        "",
        "`0.30 source + 0.20 agreement + 0.20 verifier_support + "
        "0.15 target_specificity + 0.10 confidence + 0.05 status - "
        "0.25 contradiction_penalty`.",
        "",
        "It supersedes the old 4-term W2 report based on "
        "`source/confidence/agreement/status`.",
        "",
        f"Entries: `{report.entry_count}`; missing artifacts: `{len(report.missing_entries)}`; "
        f"grid size: `{len(report.rows)}`.",
        "",
        "Summary:",
        f"- Default F1: `{default_row.f1:.4f}`.",
        f"- Best F1: `{best_row.f1:.4f}` (`{best_row.weights.name}`); "
        f"worst F1: `{worst_row.f1:.4f}` (`{worst_row.weights.name}`).",
        f"- F1 range: `{best_row.f1 - worst_row.f1:.4f}`.",
        f"- Max changed accepted value rate: `{max(row.changed_value_rate for row in report.rows):.4f}`.",
        "- Max changed expected-field value rate: "
        f"`{max(row.changed_expected_value_rate for row in report.rows):.4f}`.",
        "",
        f"JSON: `{json_path}`",
        f"CSV: `{csv_path}`",
        "",
        "| Strategy | source | agreement | verifier | target | confidence | status | penalty | P | R | F1 | value-change |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in ranked_rows[:25]:
        weights = row.weights
        lines.append(
            f"| {weights.name} | {weights.source:.4f} | {weights.agreement:.4f} | "
            f"{weights.verifier_support:.4f} | {weights.target_specificity:.4f} | "
            f"{weights.confidence:.4f} | {weights.status:.4f} | "
            f"{weights.contradiction_penalty:.4f} | {row.precision:.4f} | "
            f"{row.recall:.4f} | {row.f1:.4f} | {row.changed_value_rate:.4f} |"
        )
    lines.extend(
        [
            "",
            "Caveats:",
            "- Pure local replay; no LLM calls or remote DB calls.",
            "- Uses persisted Phase 2 original/translated artifacts keyed by the Tier3 merged full150 report.",
            "- Does not validate W3 grounding ablation pairing; W3 needs same-code paired runs.",
            "",
        ]
    )
    return "\n".join(lines)


def _row_to_payload(row: StrategyResult) -> dict[str, object]:
    return {
        "strategy": row.weights.name,
        **_weights_to_payload(row.weights),
        "precision": row.precision,
        "recall": row.recall,
        "f1": row.f1,
        "true_positives": row.true_positives,
        "false_positives": row.false_positives,
        "false_negatives": row.false_negatives,
        "changed_value_rate": row.changed_value_rate,
        "changed_expected_value_rate": row.changed_expected_value_rate,
        "status_counts": row.status_counts,
    }


def _weights_to_payload(weights: ContextualWeights) -> dict[str, float]:
    return {
        "source": weights.source,
        "agreement": weights.agreement,
        "verifier_support": weights.verifier_support,
        "target_specificity": weights.target_specificity,
        "confidence": weights.confidence,
        "status": weights.status,
        "contradiction_penalty": weights.contradiction_penalty,
    }


def _weight_values(weights: ContextualWeights) -> tuple[float, ...]:
    return (
        weights.source,
        weights.agreement,
        weights.verifier_support,
        weights.target_specificity,
        weights.confidence,
        weights.status,
        weights.contradiction_penalty,
    )


if __name__ == "__main__":
    main()
