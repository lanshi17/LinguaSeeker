"""Aggregate Benchmark B phase-2 runtime metrics from sample reports.

Unlike the runtime_metrics analyzer, this script does not require extraction
artifacts on disk. It produces a conservative runtime report from the sample
runner reports: every attempted queue_id is counted, completed queue_ids come
from rows with ``status == "phase2_completed"``, and failed queue_ids come from
rows with ``status == "phase2_failed"``. Per-case evidence-augmentation metrics
are populated only for completed queue_ids that have a matching frozen entry in
the supplied baseline runtime report.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping
import time


CHECKOUT_ROOT = Path("/data/yangzs/Projects/01_ACMG_Lingua")


def _load_json(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = payload.get("rows")
    return [r for r in rows if isinstance(r, Mapping)] if isinstance(rows, list) else []


def _preferred(current: str | None, candidate: str) -> str:
    if current == "phase2_completed":
        return current
    if candidate == "phase2_completed":
        return candidate
    if current == "phase2_failed":
        return current
    if candidate == "phase2_failed":
        return candidate
    return candidate if current is None else current


def _baseline_per_case(
    baseline_payload: Mapping[str, Any] | None,
) -> dict[str, Mapping[str, Any]]:
    if not baseline_payload:
        return {}
    cases = baseline_payload.get("per_case")
    if not isinstance(cases, list):
        return {}
    out: dict[str, Mapping[str, Any]] = {}
    for case in cases:
        if isinstance(case, Mapping) and isinstance(case.get("queue_id"), str):
            out[str(case["queue_id"])] = case
    return out


def _to_checkout_relative(path: str) -> str:
    if not path:
        return path
    try:
        return str(Path(path).relative_to(CHECKOUT_ROOT))
    except ValueError:
        return path


def aggregate(
    sample_report_paths: tuple[Path, ...],
    *,
    baseline_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    attempted: dict[str, dict[str, Any]] = {}
    for report_path in sample_report_paths:
        payload = _load_json(report_path)
        for row in _rows(payload):
            queue_id = str(row.get("queue_id") or "")
            status = str(row.get("status") or "")
            if not queue_id or status == "planned":
                continue
            entry = attempted.setdefault(
                queue_id,
                {
                    "queue_id": queue_id,
                    "entry_id": str(row.get("entry_id") or ""),
                    "article_language": str(row.get("article_language") or ""),
                    "target_gene": str(row.get("target_gene") or ""),
                    "target_disease": str(row.get("target_disease") or ""),
                    "status": status,
                    "source_report": _to_checkout_relative(str(report_path)),
                    "source_pdf_path": _to_checkout_relative(str(row.get("source_pdf_path") or "")),
                    "processing_run_id": str(row.get("processing_run_id") or ""),
                },
            )
            entry["status"] = _preferred(entry["status"], status)

    completed_ids = sorted(qid for qid, entry in attempted.items() if entry["status"] == "phase2_completed")
    failed_ids = sorted(qid for qid, entry in attempted.items() if entry["status"] == "phase2_failed")
    other_ids = sorted(
        qid for qid, entry in attempted.items() if entry["status"] not in {"phase2_completed", "phase2_failed"}
    )

    baseline_cases = _baseline_per_case(baseline_payload)
    per_case: list[dict[str, Any]] = []
    for queue_id in completed_ids:
        entry = attempted[queue_id]
        baseline_case = baseline_cases.get(queue_id, {})
        per_case.append(
            {
                "queue_id": queue_id,
                "entry_id": entry["entry_id"],
                "article_language": entry["article_language"],
                "target_gene": entry["target_gene"],
                "target_disease": entry["target_disease"],
                "processing_run_id": entry["processing_run_id"],
                "phase2_status": "completed",
                "matrix": baseline_case.get("matrix", {}),
                "metrics": baseline_case.get("metrics", {}),
            }
        )
    for queue_id in failed_ids:
        entry = attempted[queue_id]
        per_case.append(
            {
                "queue_id": queue_id,
                "entry_id": entry["entry_id"],
                "article_language": entry["article_language"],
                "target_gene": entry["target_gene"],
                "target_disease": entry["target_disease"],
                "processing_run_id": entry["processing_run_id"],
                "phase2_status": "failed",
                "matrix": {},
                "metrics": {},
            }
        )

    coverage_gains = [
        float(case.get("metrics", {}).get("evidence_coverage_gain", 0.0)) for case in per_case if case["phase2_status"] == "completed"
    ]
    non_english_yields = [
        float(case.get("metrics", {}).get("non_english_evidence_yield", 0.0)) for case in per_case if case["phase2_status"] == "completed"
    ]
    unique_gains = [
        int(case.get("metrics", {}).get("unique_evidence_gain", 0)) for case in per_case if case["phase2_status"] == "completed"
    ]
    traceable_rates = [
        float(case.get("metrics", {}).get("traceable_augmentation_rate", 0.0)) for case in per_case if case["phase2_status"] == "completed"
    ]
    interpretation_gains = [
        float(case.get("metrics", {}).get("interpretation_relevant_evidence_gain", 0.0)) for case in per_case if case["phase2_status"] == "completed"
    ]
    burdens = [
        float(case.get("metrics", {}).get("reviewer_burden", 0.0)) for case in per_case if case["phase2_status"] == "completed"
    ]

    def _mean(values: list[float]) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0

    attempted_entries = sorted(attempted.values(), key=lambda entry: entry["queue_id"])
    attempted_distinct_entries = sorted({entry["entry_id"] for entry in attempted_entries if entry["entry_id"]})
    attempted_languages = sorted({entry["article_language"] for entry in attempted_entries if entry["article_language"]})
    completed_entries = [entry for entry in attempted_entries if entry["status"] == "phase2_completed"]
    completed_distinct_entries = sorted({entry["entry_id"] for entry in completed_entries if entry["entry_id"]})
    completed_languages = sorted({entry["article_language"] for entry in completed_entries if entry["article_language"]})

    baseline_reused_note = (
        "overall coverage/yield/augmentation fields are NOT pilot results: the runtime pilot has no checkout-local extraction "
        "artifacts, so these fields are populated from the frozen baseline report for auditing only and must not be cited as "
        "pilot evidence-coverage improvement. Set to null/non-reportable for paper-facing tables."
    )

    for case in per_case:
        if case["phase2_status"] == "completed":
            case["metrics_source"] = "baseline-reused"

    return {
        "evaluation_id": "benchmark_b_phase2_runtime_metrics",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {
            "sample_report_paths": [
                _to_checkout_relative(str(path)) for path in sample_report_paths
            ],
            "reports_dir": _to_checkout_relative(str(Path("benchmark/layer3/reports"))),
            "note": (
                "Aggregated from sample runner reports without requiring extraction artifacts on disk. "
                "Per-case evidence-augmentation metrics are reused from the frozen baseline report for completed queue_ids only; "
                "the overall coverage/yield/augmentation fields are baseline-reused audit values, not pilot results."
            ),
        },
        "runtime_summary": {
            "attempted_samples": len(attempted),
            "phase2_completed": len(completed_ids),
            "failed_count": len(failed_ids),
            "timeout_count": len(other_ids),
            "completed_queue_ids": completed_ids,
            "failed_queue_ids": failed_ids,
            "incomplete_queue_ids": other_ids,
            "attempted_distinct_entries": attempted_distinct_entries,
            "attempted_languages": attempted_languages,
            "completed_distinct_entries": completed_distinct_entries,
            "completed_languages": completed_languages,
        },
        "overall": {
            "evidence_coverage_gain": None,
            "non_english_evidence_yield": None,
            "unique_evidence_gain": None,
            "traceable_augmentation_rate": None,
            "interpretation_relevant_evidence_gain": None,
            "reviewer_burden": None,
            "reportable": False,
            "baseline_reused_note": baseline_reused_note,
            "audit_baseline_means": {
                "evidence_coverage_gain": _mean(coverage_gains),
                "non_english_evidence_yield": _mean(non_english_yields),
                "unique_evidence_gain": sum(unique_gains),
                "traceable_augmentation_rate": _mean(traceable_rates),
                "interpretation_relevant_evidence_gain": _mean(interpretation_gains),
                "reviewer_burden": _mean(burdens),
            },
        },
        "per_case": per_case,
        "warnings": [
            f"{queue_id}: extraction artifact not present on disk; per-case metrics reused from frozen baseline"
            for queue_id in completed_ids
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-report", action="append", type=Path, required=True)
    parser.add_argument("--baseline-runtime-report", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    baseline_payload: Mapping[str, Any] | None = None
    if args.baseline_runtime_report:
        baseline_payload = _load_json(args.baseline_runtime_report)

    report = aggregate(tuple(args.sample_report), baseline_payload=baseline_payload)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = report["runtime_summary"]
    print(
        f"attempted={summary['attempted_samples']} "
        f"completed={summary['phase2_completed']} "
        f"failed={summary['failed_count']} "
        f"timeout={summary['timeout_count']}"
    )
    print(f"REPORT: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
