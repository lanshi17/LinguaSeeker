"""Compute aggregate and source-stratified P/R/F1 from N=50 condition reports.

Reads evaluation report JSON files produced by ``run_evaluation()`` and
computes the metrics specified in the design doc:

- precision, recall, F1 (overall and per source_dataset)
- completion rate
- average runtime per completed entry
- average token cost per completed entry (when available)

Usage::

    cd backend && uv run python -m benchmark.analysis.n50_comparison.aggregate_metrics \
        --reports-dir benchmark/data/reports/n50 \
        --output benchmark/data/reports/n50/aggregate_metrics.json
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from benchmark.core.aggregate import compute_aggregate_metrics
from benchmark.core.contracts import EntryMetrics, FieldMatch
from benchmark.core.pipeline_client import _compute_stratified_metrics


def _report_to_metrics(report: dict[str, Any]) -> list[EntryMetrics]:
    """Convert a report's per_entry list back to EntryMetrics objects."""
    all_metrics: list[EntryMetrics] = []
    for pe in report.get("per_entry", []):
        m = EntryMetrics(
            entry_id=pe["entry_id"],
            gene_symbol=pe.get("gene_symbol", ""),
            classification=pe.get("classification", ""),
            language="en",
            moi=pe.get("moi", ""),
            source_dataset=pe.get("source_dataset", ""),
            original_entry_id=pe.get("original_entry_id", ""),
            pipeline_status=pe.get("pipeline_status", "unknown"),
            run_id=pe.get("run_id"),
            status_url=pe.get("status_url"),
            error_message=pe.get("error_message"),
            duration_s=pe.get("duration_s", 0.0),
            evidence_count=pe.get("evidence_count", 0),
            found_rate=pe.get("found_rate", 0.0),
            grounding_rate=pe.get("grounding_rate", 0.0),
            standardization_accuracy=pe.get("standardization_accuracy", 0.0),
            track_consistency=pe.get("track_consistency", 0.0),
            field_matches=[
                FieldMatch(
                    field_id=f["field_id"],
                    expected_value=f.get("expected", ""),
                    matched=f.get("matched", False),
                    extracted_value=f.get("extracted", ""),
                    source_span=f.get("source_span"),
                    match_type=f.get("match_type", ""),
                    extra_found_values=f.get("extra_found_values", []),
                    best_score=f.get("best_score"),
                    source_score=f.get("source_score"),
                    confidence_score=f.get("confidence_score"),
                    agreement_score=f.get("agreement_score"),
                    status_score=f.get("status_score"),
                    verifier_support_score=f.get("verifier_support_score"),
                    target_specificity_score=f.get("target_specificity_score"),
                    contradiction_penalty=f.get("contradiction_penalty"),
                    accepted_track=f.get("accepted_track"),
                    normalized_value=f.get("normalized_value"),
                )
                for f in pe.get("field_matches", [])
            ],
            entity_matches=pe.get("entity_matches", {}),
        )
        all_metrics.append(m)
    return all_metrics


def compute_condition_metrics(report: dict[str, Any]) -> dict[str, Any]:
    """Compute full metrics for a single condition report.

    Returns a dict with overall P/R/F1, TP/FP/FN, completion rate,
    stratified P/R/F1, and runtime stats.
    """
    metrics = _report_to_metrics(report)
    aggregates = compute_aggregate_metrics(metrics)
    stratified = _compute_stratified_metrics(metrics)

    completed = [m for m in metrics if m.pipeline_status == "completed"]
    total = len(metrics)
    completion_rate = len(completed) / total if total > 0 else 0.0

    durations = [m.duration_s for m in completed if m.duration_s > 0]
    avg_duration_s = sum(durations) / len(durations) if durations else 0.0
    avg_duration_min = avg_duration_s / 60.0

    # Token cost — not directly available in current reports; placeholder
    avg_tokens = 0  # TODO: extract from trace files when available

    overall = aggregates["overall"]
    return {
        "condition_id": report.get("config", {}).get("condition_id", "unknown"),
        "n": total,
        "completed": len(completed),
        "completion_rate": round(completion_rate, 4),
        "tp": overall["true_positives"],
        "fp": overall["false_positives"],
        "fn": overall["false_positives"],
        "precision": round(overall["precision"], 4),
        "recall": round(overall["recall"], 4),
        "f1": round(overall["f1"], 4),
        "avg_min_per_entry": round(avg_duration_min, 2),
        "avg_tokens_per_entry": avg_tokens,
        "by_source_dataset": {
            src: {
                "n": m["count"],
                "precision": round(m["precision"], 4),
                "recall": round(m["recall"], 4),
                "f1": round(m["f1"], 4),
            }
            for src, m in stratified.items()
        },
    }


def aggregate_all_conditions(
    reports_dir: Path,
) -> dict[str, Any]:
    """Compute metrics for all condition reports in a directory.

    Returns a dict mapping condition_id to metrics, plus a comparison table.
    """
    results: dict[str, Any] = {}
    report_files = sorted(reports_dir.glob("*.json"))

    for rf in report_files:
        if rf.name.startswith("aggregate") or rf.name.startswith("paired"):
            continue
        report = json.loads(rf.read_text(encoding="utf-8"))
        cond_id = report.get("config", {}).get("condition_id", rf.stem)
        metrics = compute_condition_metrics(report)
        metrics["report_file"] = str(rf)
        results[cond_id] = metrics

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute aggregate metrics from N=50 condition reports",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("benchmark/data/reports/n50"),
        help="Directory containing per-condition report JSON files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark/data/reports/n50/aggregate_metrics.json"),
        help="Output file for aggregated metrics",
    )
    args = parser.parse_args()

    results = aggregate_all_conditions(args.reports_dir)

    # Build comparison table
    table_rows = []
    for cond_id, m in sorted(results.items()):
        table_rows.append({
            "condition": cond_id,
            "N": m["n"],
            "completed": m["completed"],
            "TP": m["tp"],
            "FP": m["fp"],
            "FN": m["fn"],
            "P": m["precision"],
            "R": m["recall"],
            "F1": m["f1"],
            "avg_min": m["avg_min_per_entry"],
            "avg_tokens": m["avg_tokens_per_entry"],
        })

    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "conditions": results,
        "comparison_table": table_rows,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Aggregate metrics written to: {args.output}")
    print(f"Conditions: {len(results)}")
    for row in table_rows:
        print(
            f"  {row['condition']:25s} | N={row['N']} | "
            f"P={row['P']:.4f} R={row['R']:.4f} F1={row['F1']:.4f} | "
            f"completed={row['completed']}"
        )


if __name__ == "__main__":
    main()
