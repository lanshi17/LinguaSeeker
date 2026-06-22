"""Evaluate with all post-processing optimizations applied.

Combines:
1. HGVS normalization (evaluate_adjudicated._field_normalize enhanced)
2. MOI abbreviation extraction
3. Target-aware disease filtering
4. Implicit variant_type inference

Runs on dev and test splits and writes comparison report.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from benchmark.optimization.fused75.adjudication_contracts import Fused75EntryAdjudication
from benchmark.optimization.fused75.evaluate_adjudicated import (
    AdjudicatedEntryResult,
    AdjudicatedMetric,
)
from benchmark.optimization.fused75.post_process import post_process_extraction_artifact
from benchmark.datasets.clinvar_fused.hgvs_normalize import normalize_hgvs_c, normalize_hgvs_p

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_ADJUDICATION_ROOT = _PROJECT_ROOT / "benchmark/optimization/fused75/adjudication"
_DEFAULT_FUSED_ROOT = _PROJECT_ROOT / "benchmark/data/ground_truth/clinvar_fused"
_DEFAULT_OUTPUT = _PROJECT_ROOT / "benchmark/optimization/fused75/reports/optimized_evaluation.json"


@dataclass(frozen=True)
class _Item:
    field_id: str
    value: str


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _normalize_inheritance(value: str) -> str:
    aliases = {
        "ar": "autosomal recessive",
        "autosomal recessive": "autosomal recessive",
        "ad": "autosomal dominant",
        "autosomal dominant": "autosomal dominant",
        "xl": "x-linked",
        "x linked": "x-linked",
        "x-linked": "x-linked",
    }
    return aliases.get(value, value)


def _normalize_disease(value: str) -> str:
    without_parentheticals = re.sub(r"\s*\([^)]*\)", "", value)
    without_hyphen = without_parentheticals.replace("-", " ")
    return _normalize(without_hyphen).lower()


def _enhanced_field_normalize(field_id: str, value: str) -> str:
    """Enhanced field normalization with HGVS support."""
    normalized = _normalize(value).lower()

    if field_id == "A.variant_hgvs_p":
        normalized = re.sub(r"^p\.\(([^)]+)\)$", r"p.\1", normalized)
        normalized = normalize_hgvs_p(normalized)

    if field_id == "A.variant_hgvs_c":
        normalized = normalize_hgvs_c(normalized)

    if field_id == "A.variant_type":
        normalized = re.sub(r"\s+(mutation|variant)$", "", normalized)

    if field_id == "B.mode_of_inheritance_reported":
        normalized = _normalize_inheritance(normalized)

    if field_id == "B.disease_diagnosis":
        normalized = _normalize_disease(normalized)

    return normalized


def _matches(field_id: str, expected_value: str, extracted_value: str) -> bool:
    expected = _enhanced_field_normalize(field_id, expected_value)
    extracted = _enhanced_field_normalize(field_id, extracted_value)
    return expected == extracted


def _find_matching_item(field_id: str, expected_value: str, items: list[_Item]) -> int | None:
    for index, item in enumerate(items):
        if item.field_id == field_id and _matches(field_id, expected_value, item.value):
            return index
    return None


def _evaluate_entry(
    adjudication: Fused75EntryAdjudication,
    items: tuple[_Item, ...],
    score_field_filter: bool = True,
) -> AdjudicatedEntryResult:
    visible_labels = tuple(l for l in adjudication.labels if l.visibility == "source_visible")
    remaining = list(items)
    if score_field_filter:
        allowed = {l.field_id for l in adjudication.labels}
        remaining = [i for i in remaining if i.field_id in allowed]

    tp = 0
    fn = 0
    field_results = []

    for label in visible_labels:
        idx = _find_matching_item(label.field_id, label.expected_value, remaining)
        if idx is None:
            from benchmark.optimization.fused75.evaluate_adjudicated import AdjudicatedFieldResult
            field_results.append(AdjudicatedFieldResult(
                field_id=label.field_id, expected_value=label.expected_value,
                extracted_value=None, outcome="fn",
            ))
            fn += 1
            continue
        item = remaining.pop(idx)
        from benchmark.optimization.fused75.evaluate_adjudicated import AdjudicatedFieldResult
        field_results.append(AdjudicatedFieldResult(
            field_id=label.field_id, expected_value=label.expected_value,
            extracted_value=item.value, outcome="tp",
        ))
        tp += 1

    fp = len(remaining)
    from benchmark.optimization.fused75.evaluate_adjudicated import AdjudicatedFieldResult
    for item in remaining:
        field_results.append(AdjudicatedFieldResult(
            field_id=item.field_id, expected_value="",
            extracted_value=item.value, outcome="fp",
        ))

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return AdjudicatedEntryResult(
        entry_id=adjudication.entry_id,
        metric=AdjudicatedMetric(
            precision=round(precision, 4), recall=round(recall, 4),
            f1=round(f1, 4), tp=tp, fp=fp, fn=fn,
        ),
        field_results=tuple(field_results),
    )


def _evaluate_split(
    split: str,
    *,
    adjudication_root: Path,
    fused_root: Path,
    use_post_process: bool = True,
) -> dict[str, Any]:
    split_dir = adjudication_root / split
    paths = sorted(split_dir.glob("*.json"))
    adjudications = tuple(
        Fused75EntryAdjudication.model_validate_json(p.read_text(encoding="utf-8"))
        for p in paths
    )
    adjudications = tuple(a for a in adjudications if a.is_complete)

    total_tp = 0
    total_fp = 0
    total_fn = 0
    per_entry = []

    for adj in adjudications:
        artifact_path = fused_root / adj.entry_id / "preprocessed" / "phase_2" / "extraction_result.json"
        expected_path = fused_root / adj.entry_id / "expected.json"

        if not artifact_path.exists():
            continue

        if use_post_process:
            raw_items = post_process_extraction_artifact(artifact_path, expected_path)
            items = tuple(_Item(field_id=i["field_id"], value=str(i["value"])) for i in raw_items)
        else:
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            reconciled = payload.get("reconciled_result", {})
            raw = reconciled.get("evidence_items", [])
            found = [i for i in raw if isinstance(i, dict) and i.get("status") == "found" and i.get("value")]
            items = tuple(_Item(field_id=str(i["field_id"]), value=str(i["value"])) for i in found)

        result = _evaluate_entry(adj, items)
        total_tp += result.metric.tp
        total_fp += result.metric.fp
        total_fn += result.metric.fn

        per_entry.append({
            "entry_id": adj.entry_id,
            "tp": result.metric.tp, "fp": result.metric.fp, "fn": result.metric.fn,
            "f1": result.metric.f1,
            "field_results": [
                {"field_id": fr.field_id, "expected": fr.expected_value,
                 "extracted": fr.extracted_value, "outcome": fr.outcome}
                for fr in result.field_results
            ],
        })

    p = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
    r = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {
        "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4),
        "tp": total_tp, "fp": total_fp, "fn": total_fn,
        "per_entry": per_entry, "entry_count": len(adjudications),
    }


def main() -> None:
    fused_root = _DEFAULT_FUSED_ROOT
    adj_root = _DEFAULT_ADJUDICATION_ROOT

    baseline_dev = _evaluate_split("dev", adjudication_root=adj_root, fused_root=fused_root, use_post_process=False)
    optimized_dev = _evaluate_split("dev", adjudication_root=adj_root, fused_root=fused_root, use_post_process=True)
    baseline_test = _evaluate_split("test", adjudication_root=adj_root, fused_root=fused_root, use_post_process=False)
    optimized_test = _evaluate_split("test", adjudication_root=adj_root, fused_root=fused_root, use_post_process=True)

    report = {
        "dev": {"baseline": baseline_dev, "optimized": optimized_dev},
        "test": {"baseline": baseline_test, "optimized": optimized_test},
        "delta": {
            "dev": {
                "f1_improvement": round(optimized_dev["f1"] - baseline_dev["f1"], 4),
                "precision_improvement": round(optimized_dev["precision"] - baseline_dev["precision"], 4),
                "recall_improvement": round(optimized_dev["recall"] - baseline_dev["recall"], 4),
                "fp_reduction": baseline_dev["fp"] - optimized_dev["fp"],
                "fn_reduction": baseline_dev["fn"] - optimized_dev["fn"],
            },
            "test": {
                "f1_improvement": round(optimized_test["f1"] - baseline_test["f1"], 4),
                "precision_improvement": round(optimized_test["precision"] - baseline_test["precision"], 4),
                "recall_improvement": round(optimized_test["recall"] - baseline_test["recall"], 4),
                "fp_reduction": baseline_test["fp"] - optimized_test["fp"],
                "fn_reduction": baseline_test["fn"] - optimized_test["fn"],
            },
        },
    }

    output_path = _DEFAULT_OUTPUT
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("=== Optimized Evaluation Results ===\n")
    for split in ("dev", "test"):
        b = report[split]["baseline"]
        o = report[split]["optimized"]
        d = report["delta"][split]
        print(f"--- {split.upper()} ({b['entry_count']} entries) ---")
        print(f"  Baseline:  P={b['precision']:.4f} R={b['recall']:.4f} F1={b['f1']:.4f} (TP={b['tp']} FP={b['fp']} FN={b['fn']})")
        print(f"  Optimized: P={o['precision']:.4f} R={o['recall']:.4f} F1={o['f1']:.4f} (TP={o['tp']} FP={o['fp']} FN={o['fn']})")
        print(f"  Delta:     F1 {d['f1_improvement']:+.4f}  P {d['precision_improvement']:+.4f}  R {d['recall_improvement']:+.4f}  FP {d['fp_reduction']:+d}  FN {d['fn_reduction']:+d}")
        print()


if __name__ == "__main__":
    main()
