"""Aggregate P/R/F1 metrics across per-entry evaluations.

Carved out of ``benchmark.layer3.evaluate`` during the 2026-06-18 framework
refactor. Behavior must stay byte-identical across the move.
"""
from __future__ import annotations

from benchmark.core.contracts import EntryMetrics

__all__ = [
    "compute_aggregate_metrics",
    "false_positive_count",
    "over_extraction_count",
]


def false_positive_count(metrics_list: list[EntryMetrics]) -> int:
    """Wrong-value mismatches plus over-extracted spurious values."""
    wrong_values = sum(
        1 for m in metrics_list for f in m.field_matches
        if f.match_type == "wrong_value"
    )
    over_extracted = sum(
        len(f.extra_found_values)
        for m in metrics_list
        for f in m.field_matches
    )
    return wrong_values + over_extracted


def over_extraction_count(metrics_list: list[EntryMetrics]) -> int:
    """Just the over-extraction count (extra found values beyond the expected one)."""
    return sum(
        len(f.extra_found_values)
        for m in metrics_list
        for f in m.field_matches
    )


# Legacy underscore-prefixed aliases kept for backward import compatibility:
# ``benchmark.layer3.evaluate._false_positive_count`` /
# ``_over_extraction_count`` are referenced from a few analyzer modules and
# tests via the shim. New code MUST use the public names above.
_false_positive_count = false_positive_count
_over_extraction_count = over_extraction_count


def compute_aggregate_metrics(all_metrics: list[EntryMetrics]) -> dict:
    """Compute aggregate P/R/F1 from per-entry metrics."""
    # Field-level P/R/F1
    tp = sum(1 for m in all_metrics for f in m.field_matches if f.matched)
    fp = false_positive_count(all_metrics)
    fn = sum(1 for m in all_metrics for f in m.field_matches if f.match_type in ("missing", "none"))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    grounded_tp = sum(
        1
        for m in all_metrics
        for f in m.field_matches
        if f.matched and f.source_span
    )
    grounded_fn = sum(
        1
        for m in all_metrics
        for f in m.field_matches
        if not (f.matched and f.source_span)
    )
    grounded_precision = grounded_tp / (grounded_tp + fp) if (grounded_tp + fp) > 0 else 0.0
    grounded_recall = (
        grounded_tp / (grounded_tp + grounded_fn)
        if (grounded_tp + grounded_fn) > 0
        else 0.0
    )
    grounded_f1 = (
        2 * grounded_precision * grounded_recall / (grounded_precision + grounded_recall)
        if (grounded_precision + grounded_recall) > 0
        else 0.0
    )
    db_ready_yield = grounded_tp

    # Per-field-type breakdown
    by_field: dict[str, dict] = {}
    for m in all_metrics:
        for f in m.field_matches:
            if f.field_id not in by_field:
                by_field[f.field_id] = {"tp": 0, "fp": 0, "fn": 0, "over_extractions": 0}
            if f.matched:
                by_field[f.field_id]["tp"] += 1
            elif f.match_type == "wrong_value":
                by_field[f.field_id]["fp"] += 1
            else:
                by_field[f.field_id]["fn"] += 1
            by_field[f.field_id]["fp"] += len(f.extra_found_values)
            by_field[f.field_id]["over_extractions"] += len(f.extra_found_values)

    field_f1 = {}
    for fid, counts in by_field.items():
        p = counts["tp"] / (counts["tp"] + counts["fp"]) if (counts["tp"] + counts["fp"]) > 0 else 0
        r = counts["tp"] / (counts["tp"] + counts["fn"]) if (counts["tp"] + counts["fn"]) > 0 else 0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0
        field_f1[fid] = {
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f, 4),
            "over_extractions": counts["over_extractions"],
        }

    # By classification
    by_cls: dict[str, list] = {}
    for m in all_metrics:
        by_cls.setdefault(m.classification, []).append(m)

    cls_metrics = {}
    for cls, metrics_list in by_cls.items():
        cls_tp = sum(1 for m in metrics_list for f in m.field_matches if f.matched)
        cls_fp = false_positive_count(metrics_list)
        cls_fn = sum(1 for m in metrics_list for f in m.field_matches if f.match_type in ("missing", "none"))
        cls_p = cls_tp / (cls_tp + cls_fp) if (cls_tp + cls_fp) > 0 else 0
        cls_r = cls_tp / (cls_tp + cls_fn) if (cls_tp + cls_fn) > 0 else 0
        cls_f1 = 2 * cls_p * cls_r / (cls_p + cls_r) if (cls_p + cls_r) > 0 else 0
        cls_metrics[cls] = {
            "count": len(metrics_list),
            "precision": round(cls_p, 4),
            "recall": round(cls_r, 4),
            "f1": round(cls_f1, 4),
            "over_extractions": over_extraction_count(metrics_list),
        }

    # Entity standardization accuracy
    std_values = [m.standardization_accuracy for m in all_metrics if m.entity_matches]
    entity_standardization_accuracy = (
        sum(std_values) / len(std_values) if std_values else 0.0
    )

    # Per-entity-type accuracy
    by_entity_type: dict[str, dict] = {}
    for m in all_metrics:
        for etype, ematch in m.entity_matches.items():
            if etype not in by_entity_type:
                by_entity_type[etype] = {"matched": 0, "total": 0}
            by_entity_type[etype]["total"] += 1
            if ematch.get("matched"):
                by_entity_type[etype]["matched"] += 1
    entity_accuracy_by_type = {
        etype: round(v["matched"] / v["total"], 4) if v["total"] > 0 else 0.0
        for etype, v in by_entity_type.items()
    }

    # Track consistency (original vs translated)
    tc_values = [m.track_consistency for m in all_metrics if m.track_consistency > 0]
    cross_lingual_consistency = (
        sum(tc_values) / len(tc_values) if tc_values else 0.0
    )

    # By MOI breakdown
    by_moi: dict[str, list] = {}
    for m in all_metrics:
        moi = m.moi
        by_moi.setdefault(moi, []).append(m)

    moi_metrics = {}
    for moi, metrics_list in by_moi.items():
        moi_tp = sum(1 for m in metrics_list for f in m.field_matches if f.matched)
        moi_fp = false_positive_count(metrics_list)
        moi_fn = sum(1 for m in metrics_list for f in m.field_matches if f.match_type in ("missing", "none"))
        moi_p = moi_tp / (moi_tp + moi_fp) if (moi_tp + moi_fp) > 0 else 0
        moi_r = moi_tp / (moi_tp + moi_fn) if (moi_tp + moi_fn) > 0 else 0
        moi_f1 = 2 * moi_p * moi_r / (moi_p + moi_r) if (moi_p + moi_r) > 0 else 0
        std_vals = [m.standardization_accuracy for m in metrics_list if m.entity_matches]
        tc_vals = [m.track_consistency for m in metrics_list if m.track_consistency > 0]
        moi_metrics[moi] = {
            "count": len(metrics_list),
            "precision": round(moi_p, 4),
            "recall": round(moi_r, 4),
            "f1": round(moi_f1, 4),
            "standardization_accuracy": round(sum(std_vals) / len(std_vals), 4) if std_vals else 0.0,
            "track_consistency": round(sum(tc_vals) / len(tc_vals), 4) if tc_vals else 0.0,
            "over_extractions": over_extraction_count(metrics_list),
        }

    return {
        "overall": {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "value_precision": round(precision, 4),
            "value_recall": round(recall, 4),
            "value_f1": round(f1, 4),
            "grounded_true_positives": grounded_tp,
            "grounded_false_negatives": grounded_fn,
            "grounded_precision": round(grounded_precision, 4),
            "grounded_recall": round(grounded_recall, 4),
            "grounded_f1": round(grounded_f1, 4),
            "db_ready_yield": db_ready_yield,
            "over_extractions": over_extraction_count(all_metrics),
            "entity_standardization_accuracy": round(entity_standardization_accuracy, 4),
            "cross_lingual_consistency": round(cross_lingual_consistency, 4),
        },
        "by_field": field_f1,
        "by_classification": cls_metrics,
        "by_moi": moi_metrics,
        "by_entity_type": entity_accuracy_by_type,
    }
