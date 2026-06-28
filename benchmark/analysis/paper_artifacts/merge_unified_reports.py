"""Merge per-shard benchmark reports into a single unified report.

Recomputes all aggregates (overall, by_source_dataset, by_field, etc.)
from the merged per_entry data using the same TP/FP/FN rules as
benchmark.core.aggregate.

Usage:
    cd backend
    uv run python -m benchmark.analysis.paper_artifacts.merge_unified_reports \
        --input ../benchmark/data/reports/eval_unified_*shard*.json \
        --output ../benchmark/data/reports/eval_unified_merged_b8_20260627.json
"""
from __future__ import annotations

import argparse
import glob
import json
import time
import uuid
from collections import defaultdict
from pathlib import Path

from benchmark.core.aggregate import (
    compute_aggregate_metrics,
    false_positive_count,
    over_extraction_count,
)
from benchmark.core.contracts import EntryMetrics, FieldMatch


def _load_shard_reports(paths: list[Path]) -> list[dict]:
    """Load and merge per_entry arrays from multiple shard reports."""
    all_entries: list[dict] = []
    for p in sorted(paths):
        report = json.loads(p.read_text())
        all_entries.extend(report.get("per_entry", []))
    return all_entries


def _reconstruct_metrics(entries: list[dict]) -> list[EntryMetrics]:
    """Reconstruct EntryMetrics objects from serialized per_entry dicts."""
    metrics: list[EntryMetrics] = []
    for e in entries:
        field_matches = []
        for fm in e.get("field_matches", []):
            field_matches.append(FieldMatch(
                field_id=fm.get("field_id", ""),
                expected_value=fm.get("expected_value", ""),
                matched=fm.get("matched", False),
                extracted_value=fm.get("extracted_value"),
                match_type=fm.get("match_type", "none"),
                extra_found_values=fm.get("extra_found_values", []),
            ))

        entity_matches = {}
        for em in e.get("entity_matches", []):
            if isinstance(em, dict):
                entity_matches[em.get("raw_text", "")] = em.get("matched", False)
            elif isinstance(em, (list, tuple)) and len(em) >= 2:
                entity_matches[em[0]] = em[1]

        metrics.append(EntryMetrics(
            entry_id=e.get("entry_id", ""),
            gene_symbol=e.get("gene_symbol", ""),
            classification=e.get("classification", ""),
            language=e.get("language", ""),
            moi=e.get("moi", ""),
            source_dataset=e.get("source_dataset", ""),
            original_entry_id=e.get("original_entry_id", ""),
            run_id=e.get("run_id", ""),
            pipeline_status=e.get("pipeline_status", ""),
            error_message=e.get("error_message"),
            duration_s=e.get("duration_s", 0),
            evidence_count=e.get("evidence_count", 0),
            found_rate=e.get("found_rate", 0.0),
            grounding_rate=e.get("grounding_rate", 0.0),
            standardization_accuracy=e.get("standardization_accuracy", 0.0),
            track_consistency=e.get("track_consistency", 0.0),
            field_matches=field_matches,
            entity_matches=entity_matches,
        ))
    return metrics


def compute_by_source_dataset(all_metrics: list[EntryMetrics]) -> dict[str, dict]:
    """Compute per-source-dataset P/R/F1 using the same rules as overall.

    Rules from benchmark.core.aggregate:
      TP = count(field.matched is True)
      FP = count(field.match_type == "wrong_value") + sum(len(field.extra_found_values))
      FN = count(field.match_type in ("missing", "none"))
    """
    by_src: dict[str, list[EntryMetrics]] = defaultdict(list)
    for m in all_metrics:
        by_src[m.source_dataset].append(m)

    result: dict[str, dict] = {}
    for src, metrics_list in sorted(by_src.items()):
        tp = sum(1 for m in metrics_list for f in m.field_matches if f.matched)
        fp = false_positive_count(metrics_list)
        fn = sum(
            1 for m in metrics_list for f in m.field_matches
            if f.match_type in ("missing", "none")
        )
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        result[src] = {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "over_extractions": over_extraction_count(metrics_list),
            "count": len(metrics_list),
        }
    return result


def build_merged_report(
    shard_paths: list[Path],
    total_duration: float | None = None,
) -> dict:
    """Build a merged report from shard files with correct aggregates."""
    all_entries = _load_shard_reports(shard_paths)
    all_metrics = _reconstruct_metrics(all_entries)

    # Compute overall + per-field + per-classification + per-MOI via library
    aggregates = compute_aggregate_metrics(all_metrics)

    # Compute by_source_dataset with the SAME rules
    aggregates["by_source_dataset"] = compute_by_source_dataset(all_metrics)

    # Add timeout_and_errors
    aggregates["timeout_and_errors"] = [
        {
            "entry_id": e.get("entry_id"),
            "source_dataset": e.get("source_dataset"),
            "status": e.get("pipeline_status"),
            "error": e.get("error_message", ""),
        }
        for e in all_entries
        if e.get("pipeline_status") != "completed"
    ]

    if total_duration is None:
        # Try to sum from shard reports
        total_duration = 0.0
        for p in shard_paths:
            r = json.loads(p.read_text())
            total_duration += r.get("total_duration_s", 0)

    return {
        "evaluation_id": f"eval_unified_{uuid.uuid4().hex[:8]}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {
            "base_url": "http://localhost:8000",
            "concurrency": 1,
            "limit": None,
            "ground_truth_root": "/data/yangzs/Projects/01_ACMG_Lingua/benchmark/data/ground_truth/unified",
            "dataset": "unified",
            "extraction_profile": "none",
            "extraction_mode": "b8",
            "shard_index": None,
            "shard_size": None,
            "merged_from_shards": [str(p.name) for p in shard_paths],
        },
        "total_entries": len(all_entries),
        "total_duration_s": total_duration,
        "aggregates": _to_serializable(aggregates),
        "per_entry": all_entries,
    }


def _to_serializable(obj: object) -> object:
    """Recursively convert objects to JSON-serializable types."""
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(item) for item in obj]
    if hasattr(obj, "__dict__"):
        return _to_serializable(obj.__dict__)
    return obj


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", action="append", required=True, default=[],
        help="Glob patterns or paths for shard report JSON files",
    )
    parser.add_argument(
        "--output", type=Path, required=True,
        help="Output path for the merged report",
    )
    args = parser.parse_args()

    # Resolve globs
    paths: list[Path] = []
    for pattern in args.input:
        expanded = glob.glob(pattern)
        if expanded:
            paths.extend(Path(p) for p in expanded)
        else:
            p = Path(pattern)
            if p.exists():
                paths.append(p)
    if not paths:
        print("No input files found.")
        return

    report = build_merged_report(paths)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    # Print summary
    overall = report["aggregates"]["overall"]
    by_src = report["aggregates"]["by_source_dataset"]
    print(f"Merged {report['total_entries']} entries from {len(paths)} shards")
    print(f"Overall: TP={overall['true_positives']} FP={overall['false_positives']} FN={overall['false_negatives']}")
    print(f"  P={overall['precision']:.4f} R={overall['recall']:.4f} F1={overall['f1']:.4f}")

    src_tp = sum(v["true_positives"] for v in by_src.values())
    src_fp = sum(v["false_positives"] for v in by_src.values())
    src_fn = sum(v["false_negatives"] for v in by_src.values())
    print(f"By_source sums: TP={src_tp} FP={src_fp} FN={src_fn}")
    assert src_tp == overall["true_positives"], f"TP mismatch: {src_tp} != {overall['true_positives']}"
    assert src_fp == overall["false_positives"], f"FP mismatch: {src_fp} != {overall['false_positives']}"
    assert src_fn == overall["false_negatives"], f"FN mismatch: {src_fn} != {overall['false_negatives']}"
    print("✓ by_source_dataset sums match overall")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
