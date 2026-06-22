"""Baseline comparison: Original-only vs Translated-only vs Dual-track (reconciled).

Evaluates all three track configurations against the same source-visible
adjudication labels, producing a side-by-side comparison of precision,
recall, and F1 to quantify the value of dual-track extraction.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from benchmark.optimization.fused75.adjudication_contracts import Fused75EntryAdjudication
from benchmark.optimization.fused75.evaluate_adjudicated import (
    AdjudicatedEntryResult,
    AdjudicatedMetric,
    evaluate_adjudicated_entry,
)

_DEFAULT_ADJUDICATION_ROOT = Path("benchmark/optimization/fused75/adjudication/dev")
_DEFAULT_FUSED_ROOT = Path("benchmark/data/ground_truth/clinvar_fused")
_DEFAULT_OUTPUT = Path("benchmark/optimization/fused75/reports/baseline_track_comparison.json")

TrackName = str  # "original", "translated", "dual"


@dataclass(frozen=True)
class TrackItem:
    field_id: str
    value: str


@dataclass
class TrackSummary:
    track: TrackName
    total_tp: int = 0
    total_fp: int = 0
    total_fn: int = 0
    per_entry: list[dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.per_entry is None:
            self.per_entry = []

    @property
    def metric(self) -> AdjudicatedMetric:
        tp, fp, fn = self.total_tp, self.total_fp, self.total_fn
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return AdjudicatedMetric(
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
            tp=tp,
            fp=fp,
            fn=fn,
        )


def _load_items_from_track(
    extraction_path: Path,
    track: TrackName,
) -> tuple[TrackItem, ...]:
    payload = json.loads(extraction_path.read_text(encoding="utf-8"))

    if track == "dual":
        reconciled = payload.get("reconciled_result")
        if isinstance(reconciled, dict) and isinstance(reconciled.get("evidence_items"), list):
            return _found_items(reconciled["evidence_items"])
        merged: list[dict[str, Any]] = []
        for key in ("original_result", "translated_result"):
            t = payload.get(key)
            if isinstance(t, dict) and isinstance(t.get("evidence_items"), list):
                merged.extend(t["evidence_items"])
        return _found_items(merged)

    track_key = f"{track}_result"
    t = payload.get(track_key)
    if isinstance(t, dict) and isinstance(t.get("evidence_items"), list):
        return _found_items(t["evidence_items"])
    return ()


def _found_items(items: Sequence[Any]) -> tuple[TrackItem, ...]:
    found: list[TrackItem] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("status", "found") != "found":
            continue
        if item.get("field_id") is None or item.get("value") is None:
            continue
        found.append(TrackItem(field_id=str(item["field_id"]), value=str(item["value"])))
    return tuple(found)


def _evaluate_track(
    track: TrackName,
    adjudications: tuple[Fused75EntryAdjudication, ...],
    fused_root: Path,
    score_field_filter: bool = True,
) -> TrackSummary:
    summary = TrackSummary(track=track)
    for adjudication in adjudications:
        extraction_path = fused_root / adjudication.entry_id / "preprocessed" / "phase_2" / "extraction_result.json"
        if not extraction_path.exists():
            continue
        items = _load_items_from_track(extraction_path, track)
        if score_field_filter:
            allowed = {label.field_id for label in adjudication.labels}
            items = tuple(i for i in items if i.field_id in allowed)
        result = evaluate_adjudicated_entry(adjudication, extracted_items=items)
        summary.total_tp += result.metric.tp
        summary.total_fp += result.metric.fp
        summary.total_fn += result.metric.fn
        entry_detail = {
            "entry_id": adjudication.entry_id,
            "tp": result.metric.tp,
            "fp": result.metric.fp,
            "fn": result.metric.fn,
            "f1": result.metric.f1,
            "field_results": [
                {"field_id": fr.field_id, "expected": fr.expected_value, "extracted": fr.extracted_value, "outcome": fr.outcome}
                for fr in result.field_results
            ],
        }
        summary.per_entry.append(entry_detail)
    return summary


def _compute_field_coverage(
    adjudications: tuple[Fused75EntryAdjudication, ...],
    fused_root: Path,
    track: TrackName,
) -> dict[str, int]:
    """Count how many entries each field is found in, per track."""
    field_entry_counts: dict[str, int] = {}
    for adjudication in adjudications:
        extraction_path = fused_root / adjudication.entry_id / "preprocessed" / "phase_2" / "extraction_result.json"
        if not extraction_path.exists():
            continue
        items = _load_items_from_track(extraction_path, track)
        seen_fields = {item.field_id for item in items}
        for field_id in seen_fields:
            field_entry_counts[field_id] = field_entry_counts.get(field_id, 0) + 1
    return dict(sorted(field_entry_counts.items()))


def run_baseline_comparison(
    *,
    adjudication_root: Path = _DEFAULT_ADJUDICATION_ROOT,
    fused_root: Path = _DEFAULT_FUSED_ROOT,
    output_path: Path = _DEFAULT_OUTPUT,
) -> dict[str, Any]:
    paths = sorted(adjudication_root.glob("*.json"))
    adjudications = tuple(
        Fused75EntryAdjudication.model_validate_json(p.read_text(encoding="utf-8"))
        for p in paths
    )
    adjudications = tuple(a for a in adjudications if a.is_complete)

    tracks = ("original", "translated", "dual")
    summaries: dict[str, TrackSummary] = {}
    for track in tracks:
        summaries[track] = _evaluate_track(track, adjudications, fused_root)

    field_coverage: dict[str, dict[str, int]] = {}
    for track in tracks:
        field_coverage[track] = _compute_field_coverage(adjudications, fused_root, track)

    # Per-field comparison: which fields are uniquely found by each track
    unique_fields: dict[str, dict[str, list[str]]] = {}
    all_fields = set()
    for cov in field_coverage.values():
        all_fields.update(cov.keys())
    for field_id in sorted(all_fields):
        found_in = [t for t in tracks if field_id in field_coverage[t]]
        if len(found_in) < len(tracks):
            unique_fields[field_id] = {
                "found_in": found_in,
                "missing_from": [t for t in tracks if t not in found_in],
                "entry_counts": {t: field_coverage[t].get(field_id, 0) for t in tracks},
            }

    report = {
        "baseline_type": "track_comparison",
        "description": "Original-only vs Translated-only vs Dual-track (reconciled) evaluation against source-visible adjudication",
        "entry_count": len(adjudications),
        "entry_ids": [a.entry_id for a in adjudications],
        "tracks": {
            track: {
                "precision": summaries[track].metric.precision,
                "recall": summaries[track].metric.recall,
                "f1": summaries[track].metric.f1,
                "tp": summaries[track].metric.tp,
                "fp": summaries[track].metric.fp,
                "fn": summaries[track].metric.fn,
                "per_entry": summaries[track].per_entry,
            }
            for track in tracks
        },
        "field_coverage": field_coverage,
        "unique_fields": unique_fields,
        "delta_vs_dual": {
            "original_vs_dual": {
                "f1_gap": round(summaries["dual"].metric.f1 - summaries["original"].metric.f1, 4),
                "recall_gap": round(summaries["dual"].metric.recall - summaries["original"].metric.recall, 4),
                "tp_gain": summaries["dual"].metric.tp - summaries["original"].metric.tp,
            },
            "translated_vs_dual": {
                "f1_gap": round(summaries["dual"].metric.f1 - summaries["translated"].metric.f1, 4),
                "recall_gap": round(summaries["dual"].metric.recall - summaries["translated"].metric.recall, 4),
                "tp_gain": summaries["dual"].metric.tp - summaries["translated"].metric.tp,
            },
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    report = run_baseline_comparison()
    print("=== Track Comparison Baseline ===\n")
    for track in ("original", "translated", "dual"):
        t = report["tracks"][track]
        print(f"{track:>12}: P={t['precision']:.4f}  R={t['recall']:.4f}  F1={t['f1']:.4f}  (TP={t['tp']} FP={t['fp']} FN={t['fn']})")
    print()
    delta = report["delta_vs_dual"]
    print("Delta vs Dual:")
    print(f"  Original-only  → F1 gap: {delta['original_vs_dual']['f1_gap']:+.4f}, TP gain: +{delta['original_vs_dual']['tp_gain']}")
    print(f"  Translated-only → F1 gap: {delta['translated_vs_dual']['f1_gap']:+.4f}, TP gain: +{delta['translated_vs_dual']['tp_gain']}")
    print()
    if report["unique_fields"]:
        print("Fields uniquely contributed by a single track:")
        for field_id, info in report["unique_fields"].items():
            print(f"  {field_id}: found in {info['found_in']}, missing from {info['missing_from']}")
    print(f"\nReport written to: benchmark/optimization/fused75/reports/baseline_track_comparison.json")


if __name__ == "__main__":
    main()
