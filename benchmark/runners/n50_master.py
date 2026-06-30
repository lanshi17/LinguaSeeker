"""Master orchestrator for the full N=50 comparison and ablation experiment.

Runs all pipeline-based conditions (C1, C2, A1, A2, A3, A4) sequentially
on the locked N=50 manifest, then triggers the analysis pipeline.

C0 (prompt-only) is dispatched separately via ``n50_prompt_only.py``.

Usage::

    cd backend && POSTGRES_PASSWORD=<vault_pw> PYTHONPATH="..:." uv run python -m benchmark.runners.n50_master \\
        --base-url http://localhost:8000 --concurrency 4

This is a long-running job (~20+ hours for 6 conditions × 50 entries at
~3.5 min/entry with concurrency 4). Progress is logged per condition and
per entry. Each condition produces an independent report file in
``benchmark/data/reports/n50/``.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

from loguru import logger

from benchmark.core.pipeline_client import run_evaluation

# Conditions to run via the pipeline (C0 is handled separately).
PIPELINE_CONDITIONS: list[str] = [
    "c2_full_broad",
    "c1_catalog",
    "a1_no_reflection",
    "a2_no_review",
    "a3_no_target_guard",
    "a4_original_only",
]

CONDITIONS_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "benchmark" / "data" / "manifests" / "conditions"
)
MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "benchmark" / "data" / "manifests"
    / "unified_b8_n50_comparison_20260629.json"
)
REPORTS_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "benchmark" / "data" / "reports" / "n50"
)


def _load_condition(condition_id: str) -> dict[str, Any]:
    """Load a condition config file."""
    path = CONDITIONS_DIR / f"{condition_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_manifest_entry_ids() -> list[str]:
    """Load the 50 entry IDs from the frozen manifest."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return [e["entry_id"] for e in manifest["entries"]]


async def run_condition(
    condition_id: str,
    base_url: str,
    concurrency: int,
    api_key: str | None = None,
) -> str:
    """Run a single condition on all 50 entries.

    Returns the path to the generated report.
    """
    config = _load_condition(condition_id)
    entry_ids = _load_manifest_entry_ids()

    logger.info(
        "=== Starting condition: {} ({} entries, mode={}, flags: review={} guard={} orig_only={}) ===",
        condition_id,
        len(entry_ids),
        config["extraction_mode"],
        config["ablation_disable_review"],
        config["ablation_disable_target_guard"],
        config["ablation_original_only"],
    )

    t0 = time.time()
    await run_evaluation(
        base_url=base_url,
        concurrency=concurrency,
        entry_ids=entry_ids,
        force_reextract=config.get("force_reextract", True),
        api_key=api_key,
        extraction_profile=config.get("extraction_profile", "none"),
        extraction_mode=config["extraction_mode"],
        ablation_disable_review=config["ablation_disable_review"],
        ablation_disable_target_guard=config["ablation_disable_target_guard"],
        ablation_original_only=config["ablation_original_only"],
        review_reject_policy=config.get("review_reject_policy", "hard_veto"),
    )
    elapsed = time.time() - t0
    logger.info("=== Condition {} completed in {:.0f}s ({:.1f}h) ===", condition_id, elapsed, elapsed / 3600)
    return condition_id


async def run_all_conditions(
    base_url: str,
    concurrency: int,
    api_key: str | None = None,
    conditions: list[str] | None = None,
) -> None:
    """Run all pipeline conditions sequentially."""
    conditions = conditions or PIPELINE_CONDITIONS
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    t0 = time.time()

    for cond_id in conditions:
        try:
            await run_condition(cond_id, base_url, concurrency, api_key=api_key)
            results.append({"condition": cond_id, "status": "completed"})
        except Exception as e:
            logger.error("Condition {} failed: {}", cond_id, e)
            results.append({"condition": cond_id, "status": "failed", "error": str(e)})

    total_elapsed = time.time() - t0
    logger.info("=== All conditions completed in {:.0f}s ({:.1f}h) ===", total_elapsed, total_elapsed / 3600)

    # Write master summary
    summary_path = REPORTS_DIR / "master_summary.json"
    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_duration_s": round(total_elapsed, 2),
        "conditions": results,
        "design_doc": "docs/active/2026-06-29-bibm-n50-comparison-ablation-design.md",
        "manifest": str(MANIFEST_PATH),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Master summary written to: {}", summary_path)

    # Print next steps
    logger.info("")
    logger.info("=== Next Steps ===")
    logger.info("1. Run C0 prompt-only: cd backend && uv run python -m benchmark.runners.n50_prompt_only")
    logger.info("2. Aggregate metrics: uv run python -m benchmark.analysis.n50_comparison.aggregate_metrics")
    logger.info("3. Paired tests: uv run python -m benchmark.analysis.n50_comparison.paired_tests --reference <c2_report> --comparison <other_report>")
    logger.info("4. Case study: uv run python -m benchmark.analysis.n50_comparison.case_study --full-broad <c2_report> --no-reflection <a1_report> --manifest {}",
                MANIFEST_PATH)
    logger.info("5. Final tables: uv run python -m benchmark.analysis.n50_comparison.generate_tables")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Master orchestrator for the full N=50 experiment",
    )
    parser.add_argument("--base-url", default="http://localhost:8000", help="Pipeline base URL")
    parser.add_argument("--concurrency", type=int, default=4, help="Max concurrent submissions")
    parser.add_argument("--api-key", default=None, help="API key for authentication")
    parser.add_argument(
        "--conditions",
        nargs="+",
        default=None,
        help="Specific conditions to run (default: all pipeline conditions)",
    )
    args = parser.parse_args()

    asyncio.run(run_all_conditions(
        base_url=args.base_url,
        concurrency=args.concurrency,
        api_key=args.api_key,
        conditions=args.conditions,
    ))


if __name__ == "__main__":
    main()
