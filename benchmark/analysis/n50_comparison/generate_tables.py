"""Generate the main comparison and ablation tables for the N=50 experiment.

Produces the two output tables specified in the design doc:

1. Main Comparison Table (C0, C1, C2)
2. Ablation Table (C2, A1, A2, A3, A4 with delta F1 and paired p-values)

Usage::

    cd backend && uv run python -m benchmark.analysis.n50_comparison.generate_tables \
        --reports-dir benchmark/data/reports/n50 \
        --manifest benchmark/data/manifests/unified_b8_n50_comparison_20260629.json \
        --output benchmark/data/reports/n50/final_tables.json
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from benchmark.analysis.n50_comparison.aggregate_metrics import (
    compute_condition_metrics,
)
from benchmark.analysis.n50_comparison.paired_tests import (
    _load_report,
    run_all_paired_tests,
)


# Condition ordering and labels from the design doc.
MAIN_CONDITIONS = ["c0_prompt_only", "c1_catalog", "c2_full_broad"]
ABLATION_CONDITIONS = ["c2_full_broad", "a1_no_reflection", "a2_no_review", "a3_no_target_guard", "a4_original_only"]

CONDITION_LABELS: dict[str, str] = {
    "c0_prompt_only": "prompt-only",
    "c1_catalog": "catalog workflow",
    "c2_full_broad": "full broad workflow",
    "a1_no_reflection": "no reflection",
    "a2_no_review": "no review validation",
    "a3_no_target_guard": "no target guard",
    "a4_original_only": "original-only",
}

ABLATION_DISABLED_COMPONENTS: dict[str, str] = {
    "c2_full_broad": "none",
    "a1_no_reflection": "reflection/retry loop",
    "a2_no_review": "review pass",
    "a3_no_target_guard": "target specificity guard",
    "a4_original_only": "translated branch",
}

ABLATION_INTERPRETATIONS: dict[str, str] = {
    "c2_full_broad": "main condition",
    "a1_no_reflection": "reflection contribution",
    "a2_no_review": "review contribution",
    "a3_no_target_guard": "target-context contribution",
    "a4_original_only": "input-branch contribution",
}


def _find_report(reports_dir: Path, condition_id: str) -> Path | None:
    """Find the most recent report file for a condition."""
    candidates = sorted(
        reports_dir.glob(f"*{condition_id}*.json"),
        reverse=True,
    )
    # Exclude aggregate/paired/table files
    candidates = [
        c for c in candidates
        if not c.name.startswith(("aggregate", "paired", "final", "case"))
    ]
    return candidates[0] if candidates else None


def generate_main_comparison_table(
    reports_dir: Path,
) -> dict[str, Any]:
    """Generate the main comparison table (C0, C1, C2)."""
    rows: list[dict[str, Any]] = []
    for cond_id in MAIN_CONDITIONS:
        report_path = _find_report(reports_dir, cond_id)
        if report_path is None:
            rows.append({
                "condition": CONDITION_LABELS.get(cond_id, cond_id),
                "N": 50,
                "completed": "TBD",
                "TP": "TBD", "FP": "TBD", "FN": "TBD",
                "P": "TBD", "R": "TBD", "F1": "TBD",
                "avg_min": "TBD", "avg_tokens": "TBD",
            })
            continue
        report = _load_report(report_path)
        m = compute_condition_metrics(report)
        rows.append({
            "condition": CONDITION_LABELS.get(cond_id, cond_id),
            "N": m["n"],
            "completed": m["completed"],
            "TP": m["tp"], "FP": m["fp"], "FN": m["fn"],
            "P": m["precision"], "R": m["recall"], "F1": m["f1"],
            "avg_min": m["avg_min_per_entry"], "avg_tokens": m["avg_tokens_per_entry"],
        })
    return {"title": "Main Comparison Table", "rows": rows}


def generate_ablation_table(
    reports_dir: Path,
) -> dict[str, Any]:
    """Generate the ablation table with delta F1 and paired p-values."""
    # Find the full broad report as reference
    fb_path = _find_report(reports_dir, "c2_full_broad")
    fb_report = _load_report(fb_path) if fb_path else None
    fb_metrics = compute_condition_metrics(fb_report) if fb_report else None

    rows: list[dict[str, Any]] = []
    for cond_id in ABLATION_CONDITIONS:
        report_path = _find_report(reports_dir, cond_id)
        if report_path is None:
            rows.append({
                "condition": CONDITION_LABELS.get(cond_id, cond_id),
                "disabled": ABLATION_DISABLED_COMPONENTS.get(cond_id, ""),
                "N": 50,
                "P": "TBD", "R": "TBD", "F1": "TBD",
                "delta_f1": "TBD", "paired_p": "TBD",
                "interpretation": ABLATION_INTERPRETATIONS.get(cond_id, ""),
            })
            continue

        report = _load_report(report_path)
        m = compute_condition_metrics(report)

        delta_f1 = "—"
        paired_p = "—"
        if fb_metrics and cond_id != "c2_full_broad":
            tests = run_all_paired_tests(fb_report, report)
            delta_f1 = tests["paired_t"]["mean_diff"]
            paired_p = tests["paired_t"]["p_value"]

        rows.append({
            "condition": CONDITION_LABELS.get(cond_id, cond_id),
            "disabled": ABLATION_DISABLED_COMPONENTS.get(cond_id, ""),
            "N": m["n"],
            "P": m["precision"], "R": m["recall"], "F1": m["f1"],
            "delta_f1": delta_f1,
            "paired_p": paired_p,
            "interpretation": ABLATION_INTERPRETATIONS.get(cond_id, ""),
        })

    return {"title": "Ablation Table", "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate final N=50 comparison and ablation tables",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("benchmark/data/reports/n50"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark/data/reports/n50/final_tables.json"),
    )
    args = parser.parse_args()

    main_table = generate_main_comparison_table(args.reports_dir)
    ablation_table = generate_ablation_table(args.reports_dir)

    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "design_doc": "docs/active/2026-06-29-bibm-n50-comparison-ablation-design.md",
        "main_comparison": main_table,
        "ablation": ablation_table,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Final tables written to: {args.output}")

    # Print tables
    print("\n=== Main Comparison Table ===")
    print(f"{'condition':25s} {'N':>3s} {'comp':>4s} {'TP':>4s} {'FP':>4s} {'FN':>4s} {'P':>7s} {'R':>7s} {'F1':>7s} {'min':>6s} {'tok':>8s}")
    for row in main_table["rows"]:
        print(f"{row['condition']:25s} {str(row['N']):>3s} {str(row['completed']):>4s} {str(row['TP']):>4s} {str(row['FP']):>4s} {str(row['FN']):>4s} {str(row['P']):>7s} {str(row['R']):>7s} {str(row['F1']):>7s} {str(row['avg_min']):>6s} {str(row['avg_tokens']):>8s}")

    print("\n=== Ablation Table ===")
    print(f"{'condition':25s} {'disabled':30s} {'N':>3s} {'P':>7s} {'R':>7s} {'F1':>7s} {'ΔF1':>7s} {'p':>8s} {'interpretation'}")
    for row in ablation_table["rows"]:
        print(f"{row['condition']:25s} {row['disabled']:30s} {str(row['N']):>3s} {str(row['P']):>7s} {str(row['R']):>7s} {str(row['F1']):>7s} {str(row['delta_f1']):>7s} {str(row['paired_p']):>8s} {row['interpretation']}")


if __name__ == "__main__":
    main()
