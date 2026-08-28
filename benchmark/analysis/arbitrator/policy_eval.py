"""Leave-one-entry-out policy evaluation for learned arbitrator.

Trains L2 logistic regression on 29 entries, scores candidates in the held-out
entry, selects one candidate per field using learned scores + source-validity
gates, and computes entry-level F1 against the same evaluator as ablations.
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from benchmark.analysis.arbitrator.dataset import (
    CandidateSample,
    build_dataset,
)
from benchmark.core import (
    GROUND_TRUTH_DIR,
    REPORTS_DIR,
    EntryMetrics,
    FieldMatch,
    compare_evidence,
    compute_aggregate_metrics,
)
from benchmark.analysis.reconcile.ablation import (
    ExtractedAblationItem,
    _source_to_payload,
)
from src.core.evidence_extraction.contracts import (
    DualEvidenceExtractionResult,
    Track,
)
from src.core.evidence_extraction.reconcile.contextual import (
    reconcile_with_context,
)
from src.core.evidence_extraction.reconcile.features import (
    CandidateFeatureVector,
)
from src.core.standardize_entities_and_align_knowledge.context_pack.core import (
    build_context_pack_from_expected_json,
)


@dataclass(frozen=True)
class FoldResult:
    """Result of one LOO fold."""

    held_out_entry_id: str
    contextual_f1: float
    learned_f1: float
    field_decisions: dict[str, dict[str, Any]]
    coefficients: dict[str, float]


@dataclass(frozen=True)
class PolicyEvalReport:
    """Full LOO policy evaluation report."""

    folds: list[FoldResult]
    contextual_overall_f1: float
    learned_overall_f1: float
    delta_f1: float
    per_field_contextual_f1: dict[str, float]
    per_field_learned_f1: dict[str, float]
    relationship_error_reduction: float | None


def run_loo_evaluation(
    ground_truth_dir: Path = GROUND_TRUTH_DIR,
    c_reg: float = 1.0,
) -> PolicyEvalReport:
    """Run leave-one-entry-out policy evaluation over all entries."""
    all_samples, summary = build_dataset(ground_truth_dir)
    entry_ids = sorted({s.entry_id for s in all_samples})

    folds: list[FoldResult] = []
    contextual_entry_metrics: list[EntryMetrics] = []
    learned_entry_metrics: list[EntryMetrics] = []

    for held_out_id in entry_ids:
        train_samples = [s for s in all_samples if s.entry_id != held_out_id]
        test_samples = [s for s in all_samples if s.entry_id == held_out_id]

        if not train_samples or not test_samples:
            continue

        model, scaler, coefficients = _train_fold(train_samples, c_reg=c_reg)
        fold_result, contextual_metrics, learned_metrics = _evaluate_fold(
            held_out_id,
            test_samples,
            model,
            scaler,
            ground_truth_dir,
        )
        folds.append(fold_result)
        contextual_entry_metrics.append(contextual_metrics)
        learned_entry_metrics.append(learned_metrics)

    contextual_agg = compute_aggregate_metrics(contextual_entry_metrics)
    learned_agg = compute_aggregate_metrics(learned_entry_metrics)

    contextual_f1 = cast(float, contextual_agg["overall"]["f1"])
    learned_f1 = cast(float, learned_agg["overall"]["f1"])

    per_field_contextual = {
        field_id: cast(float, metrics["f1"])
        for field_id, metrics in contextual_agg.get("by_field", {}).items()
    }
    per_field_learned = {
        field_id: cast(float, metrics["f1"])
        for field_id, metrics in learned_agg.get("by_field", {}).items()
    }

    rel_contextual = per_field_contextual.get("A.gene_disease_relationship")
    rel_learned = per_field_learned.get("A.gene_disease_relationship")
    rel_error_reduction = None
    if rel_contextual is not None and rel_learned is not None and rel_contextual < 1.0:
        contextual_error = 1.0 - rel_contextual
        learned_error = 1.0 - rel_learned
        rel_error_reduction = (contextual_error - learned_error) / contextual_error if contextual_error > 0 else None

    return PolicyEvalReport(
        folds=folds,
        contextual_overall_f1=contextual_f1,
        learned_overall_f1=learned_f1,
        delta_f1=learned_f1 - contextual_f1,
        per_field_contextual_f1=per_field_contextual,
        per_field_learned_f1=per_field_learned,
        relationship_error_reduction=rel_error_reduction,
    )


def _train_fold(
    samples: list[CandidateSample],
    c_reg: float = 1.0,
) -> tuple[LogisticRegression, StandardScaler, dict[str, float]]:
    """Train L2 logistic regression on training fold samples."""
    feature_names = CandidateFeatureVector.feature_names()
    X = np.array([s.features.to_list() for s in samples])
    y = np.array([s.label for s in samples])

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = LogisticRegression(
        C=c_reg,
        solver="lbfgs",
        max_iter=1000,
        class_weight="balanced",
        random_state=20260615,
    )
    model.fit(X_scaled, y)

    coefficients = {
        name: float(coef)
        for name, coef in zip(feature_names, model.coef_[0])
    }
    return model, scaler, coefficients


def _evaluate_fold(
    held_out_id: str,
    test_samples: list[CandidateSample],
    model: LogisticRegression,
    scaler: StandardScaler,
    ground_truth_dir: Path,
) -> tuple[FoldResult, EntryMetrics, EntryMetrics]:
    """Evaluate one held-out entry with learned vs contextual scoring."""
    artifact_path = ground_truth_dir / held_out_id / "preprocessed" / "phase_2" / "extraction_result.json"
    expected_path = ground_truth_dir / held_out_id / "expected.json"

    expected = cast(dict[str, Any], json.loads(expected_path.read_text(encoding="utf-8")))
    gold_evidence = expected.get("expected_evidence", [])
    gold_standardization = expected.get("expected_standardization", {})

    result = DualEvidenceExtractionResult.model_validate_json(
        artifact_path.read_text(encoding="utf-8")
    )
    context_pack = build_context_pack_from_expected_json(expected_path)

    contextual_output = reconcile_with_context(
        result.original_result,
        result.translated_result,
        context_pack,
    )
    contextual_items: list[ExtractedAblationItem] = []
    for decision in contextual_output.decisions:
        if decision.accepted is not None:
            item = _evidence_item_to_extracted(decision.accepted)
            if decision.accepted_score is not None:
                item["best_score"] = decision.accepted_score.score
                item["source_score"] = decision.accepted_score.source_score
                item["normalized_value"] = decision.accepted_score.normalized_value
            contextual_items.append(item)

    X_test = np.array([s.features.to_list() for s in test_samples])
    X_test_scaled = scaler.transform(X_test)
    learned_probs = model.predict_proba(X_test_scaled)[:, 1]

    field_best: dict[str, tuple[float, CandidateSample]] = {}
    for sample, prob in zip(test_samples, learned_probs):
        current = field_best.get(sample.field_id)
        if current is None or prob > current[0]:
            field_best[sample.field_id] = (prob, sample)

    learned_items: list[ExtractedAblationItem] = []
    field_decisions: dict[str, dict[str, Any]] = {}
    for field_id, (prob, sample) in field_best.items():
        for cs in test_samples:
            if cs.field_id == field_id and cs.span_id:
                source = None
                for track_result in [result.original_result, result.translated_result]:
                    for item in track_result.evidence_items:
                        if item.field_id == field_id and item.source and item.source.span_id == cs.span_id:
                            source = item
                            break
                    if source is not None:
                        break
                if source is not None:
                    extracted = _evidence_item_to_extracted(source)
                    extracted["best_score"] = float(prob)
                    learned_items.append(extracted)
                    break

        field_decisions[field_id] = {
            "learned_prob": float(prob),
            "learned_value": sample.normalized_value,
            "learned_track": sample.track,
        }

    coefficients = {
        name: float(coef)
        for name, coef in zip(CandidateFeatureVector.feature_names(), model.coef_[0])
    }

    contextual_metrics = EntryMetrics(
        entry_id=held_out_id,
        gene_symbol=str(expected.get("gene_symbol", "")),
        classification=str(expected.get("classification", "")),
        moi=str(expected.get("moi", "")),
        language="en",
        pipeline_status="completed",
        evidence_count=len(contextual_items),
        found_rate=sum(1 for i in contextual_items if i["status"] == "found") / max(len(contextual_items), 1),
        field_matches=compare_evidence(gold_evidence, contextual_items, expected_standardization=gold_standardization),
    )
    learned_metrics = EntryMetrics(
        entry_id=held_out_id,
        gene_symbol=str(expected.get("gene_symbol", "")),
        classification=str(expected.get("classification", "")),
        moi=str(expected.get("moi", "")),
        language="en",
        pipeline_status="completed",
        evidence_count=len(learned_items),
        found_rate=sum(1 for i in learned_items if i["status"] == "found") / max(len(learned_items), 1),
        field_matches=compare_evidence(gold_evidence, learned_items, expected_standardization=gold_standardization),
    )

    contextual_f1 = _entry_f1(contextual_metrics)
    learned_f1 = _entry_f1(learned_metrics)

    fold_result = FoldResult(
        held_out_entry_id=held_out_id,
        contextual_f1=contextual_f1,
        learned_f1=learned_f1,
        field_decisions=field_decisions,
        coefficients=coefficients,
    )
    return fold_result, contextual_metrics, learned_metrics


def _entry_f1(metrics: EntryMetrics) -> float:
    tp = sum(1 for m in metrics.field_matches if m.matched)
    fp = sum(1 for m in metrics.field_matches if not m.matched and m.extracted_value is not None)
    fn = sum(1 for m in metrics.field_matches if not m.matched and m.extracted_value is None)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0


def _evidence_item_to_extracted(item: Any) -> ExtractedAblationItem:
    extracted: ExtractedAblationItem = {
        "field_id": item.field_id,
        "status": item.status.value,
        "value": item.value,
        "confidence": item.confidence,
    }
    source = getattr(item, "source", None)
    if source is not None:
        extracted["source_span"] = _source_to_payload(source)
    return extracted


def _serialize_report(report: PolicyEvalReport) -> dict[str, Any]:
    return {
        "evaluation_type": "leave_one_entry_out",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_folds": len(report.folds),
        "contextual_overall_f1": report.contextual_overall_f1,
        "learned_overall_f1": report.learned_overall_f1,
        "delta_f1": report.delta_f1,
        "per_field_contextual_f1": report.per_field_contextual_f1,
        "per_field_learned_f1": report.per_field_learned_f1,
        "relationship_error_reduction": report.relationship_error_reduction,
        "gate_a_passed": _check_gate_a(report),
        "folds": [
            {
                "held_out_entry_id": fold.held_out_entry_id,
                "contextual_f1": fold.contextual_f1,
                "learned_f1": fold.learned_f1,
                "field_decisions": fold.field_decisions,
            }
            for fold in report.folds
        ],
    }


def _check_gate_a(report: PolicyEvalReport) -> bool:
    f1_gain = report.delta_f1 >= 0.010
    rel_reduction = (
        report.relationship_error_reduction is not None
        and report.relationship_error_reduction >= 0.20
        and report.learned_overall_f1 >= report.contextual_overall_f1
    )
    return f1_gain or rel_reduction


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for LOO policy evaluation."""
    parser = argparse.ArgumentParser(description="Leave-one-entry-out learned arbitrator evaluation.")
    parser.add_argument("--ground-truth-dir", type=Path, default=GROUND_TRUTH_DIR)
    parser.add_argument("--c-reg", type=float, default=1.0)
    parser.add_argument("--loo", action="store_true", help="Run LOO evaluation")
    parser.add_argument("--write", action="store_true", help="Write report to disk")
    args = parser.parse_args(argv)

    if not args.loo:
        parser.print_help()
        return

    report = run_loo_evaluation(args.ground_truth_dir, c_reg=args.c_reg)

    print(f"Contextual F1: {report.contextual_overall_f1:.4f}")
    print(f"Learned F1:    {report.learned_overall_f1:.4f}")
    print(f"Delta F1:      {report.delta_f1:+.4f}")
    print(f"Per-field contextual: {report.per_field_contextual_f1}")
    print(f"Per-field learned:    {report.per_field_learned_f1}")
    if report.relationship_error_reduction is not None:
        print(f"Relationship error reduction: {report.relationship_error_reduction:.1%}")
    print(f"Gate A passed: {_check_gate_a(report)}")

    if args.write:
        output_path = REPORTS_DIR / f"arbitrator_policy_eval_{time.strftime('%Y%m%d_%H%M%S')}.json"
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(_serialize_report(report), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Report written to: {output_path}")


if __name__ == "__main__":
    main()
