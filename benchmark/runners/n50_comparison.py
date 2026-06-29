"""Unified N=50 comparison/ablation experiment runner.

Loads a condition configuration from
``benchmark/data/manifests/conditions/<condition_id>.json`` and runs the
BIBM N=50 comparison experiment described in
``docs/active/2026-06-29-bibm-n50-comparison-ablation-design.md``.

Pipeline-backed conditions (C1, C2, A1, A2, A3, A4) are executed via
:func:`benchmark.core.pipeline_client.run_evaluation` using the locked
N=50 manifest entry IDs.  The prompt-only baseline (C0) is NOT executed
here; it requires the separate
:mod:`benchmark.runners.n50_prompt_only` runner, and this script prints a
clear redirect message when C0 is selected.

Usage::

    cd backend && uv run python -m benchmark.runners.n50_comparison \
        --condition c2_full_broad \
        --base-url http://localhost:8000 \
        --concurrency 4

Reports are written to ``benchmark/data/reports/n50/`` with a
condition-specific filename.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

from loguru import logger

from benchmark.core.paths import BENCHMARK_ROOT, REPORTS_ROOT
from benchmark.core.pipeline_client import run_evaluation

__all__ = ["main", "load_condition_config", "load_manifest_entry_ids"]


# ── Filesystem constants ────────────────────────────────────────────────

CONDITIONS_DIR: Path = BENCHMARK_ROOT / "data" / "manifests" / "conditions"
"""Directory holding one JSON config file per experimental condition."""

DEFAULT_MANIFEST: Path = (
    BENCHMARK_ROOT
    / "data"
    / "manifests"
    / "unified_b8_n50_comparison_20260629.json"
)
"""Locked N=50 comparison manifest produced by the stratified sampler."""

REPORTS_N50_DIR: Path = REPORTS_ROOT / "n50"
"""Per-condition report output directory for the N=50 experiment."""

PROMPT_ONLY_RUNNER = "benchmark.runners.n50_prompt_only"
"""Module path of the dedicated C0 prompt-only runner."""


# ── Config / manifest loading ───────────────────────────────────────────


def load_condition_config(condition_id: str) -> dict[str, Any]:
    """Load a condition configuration JSON file by ``condition_id``.

    Args:
        condition_id: Filename stem of a config in :data:`CONDITIONS_DIR`,
            e.g. ``"c2_full_broad"``.

    Returns:
        Parsed condition config dict.

    Raises:
        FileNotFoundError: If no ``<condition_id>.json`` exists in
            :data:`CONDITIONS_DIR`.
        ValueError: If the JSON is malformed.
    """
    path = CONDITIONS_DIR / f"{condition_id}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Condition config not found: {path}. "
            f"Available conditions: {_list_available_condition_ids()}"
        )
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON in condition config {path}: {exc}") from exc
    if config.get("condition_id") != condition_id:
        logger.warning(
            "condition_id mismatch: filename='{}' but config.condition_id='{}'. "
            "Proceeding with the filename-derived id.",
            condition_id,
            config.get("condition_id"),
        )
    return config


def load_manifest_entry_ids(manifest_path: Path) -> list[str]:
    """Load the ordered list of entry IDs from a locked N=50 manifest.

    Args:
        manifest_path: Path to the unified N=50 manifest JSON.

    Returns:
        Ordered list of ``entry_id`` strings.

    Raises:
        FileNotFoundError: If ``manifest_path`` does not exist.
        ValueError: If the manifest has no ``entries`` list.
    """
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError(
            f"Manifest {manifest_path} has no non-empty 'entries' list."
        )
    entry_ids = [e["entry_id"] for e in entries if "entry_id" in e]
    if len(entry_ids) != len(entries):
        missing = len(entries) - len(entry_ids)
        logger.warning(
            "Manifest has {} entries but only {} entry_ids extracted ({} missing).",
            len(entries),
            len(entry_ids),
            missing,
        )
    return entry_ids


def _list_available_condition_ids() -> list[str]:
    """Return the sorted list of condition-id stems available on disk."""
    if not CONDITIONS_DIR.exists():
        return []
    return sorted(p.stem for p in CONDITIONS_DIR.glob("*.json"))


# ── Report persistence ──────────────────────────────────────────────────


def _save_report(condition_id: str, report: dict[str, Any]) -> Path:
    """Write a runner-level report to :data:`REPORTS_N50_DIR`.

    The filename encodes the condition id and a wall-clock timestamp so
    repeated runs of the same condition never overwrite each other.

    Args:
        condition_id: Condition identifier used in the filename.
        report: JSON-serializable report dict.

    Returns:
        Absolute path of the written report file.
    """
    REPORTS_N50_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = REPORTS_N50_DIR / f"{condition_id}_{ts}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ── Condition execution ─────────────────────────────────────────────────


async def _run_prompt_only(condition_id: str, config: dict[str, Any]) -> int:
    """Print the C0 redirect message and exit without running the pipeline.

    The prompt-only baseline has no agent workflow and must be executed by
    the dedicated :data:`PROMPT_ONLY_RUNNER` module.

    Args:
        condition_id: Expected to be ``"c0_prompt_only"``.
        config: The C0 condition config (unused beyond logging).

    Returns:
        Exit code ``0`` (this is an informational redirect, not an error).
    """
    logger.info(
        "Condition '{}' is the prompt-only baseline (C0).", condition_id
    )
    logger.info(
        "C0 has no agent workflow and is NOT executed by the pipeline-based "
        "runner. Run the dedicated prompt-only runner instead:"
    )
    logger.info(
        "    cd backend && uv run python -m {} --base-url <url>",
        PROMPT_ONLY_RUNNER,
    )
    logger.info(
        "Prompt-only model: {} | disabled: {}",
        config.get("prompt_only_model"),
        config.get("disabled_components", []),
    )
    return 0


async def _run_pipeline_condition(
    condition_id: str,
    config: dict[str, Any],
    entry_ids: list[str],
    base_url: str,
    concurrency: int,
    manifest_path: Path,
) -> int:
    """Execute a pipeline-backed condition via :func:`run_evaluation`.

    Forwards the ablation flags and extraction mode from the condition
    config to :func:`run_evaluation`, then saves a runner-level wrapper
    report (with provenance) alongside the raw eval report produced by
    :func:`run_evaluation`.

    Args:
        condition_id: Condition identifier.
        config: Parsed condition config.
        entry_ids: Ordered N=50 manifest entry IDs.
        base_url: Pipeline base URL.
        concurrency: Max concurrent pipeline submissions.
        manifest_path: Path to the locked manifest (recorded in provenance).

    Returns:
        ``0`` on success, ``1`` if :func:`run_evaluation` raises.
    """
    extraction_mode = config.get("extraction_mode", "broad")
    ablation_disable_review = bool(config.get("ablation_disable_review", False))
    ablation_disable_target_guard = bool(
        config.get("ablation_disable_target_guard", False)
    )
    ablation_original_only = bool(config.get("ablation_original_only", False))
    force_reextract = bool(config.get("force_reextract", True))
    extraction_profile = config.get("extraction_profile", "none")

    logger.info(
        "Running condition '{}' | mode={} | review={} target_guard={} "
        "original_only={} | entries={} | concurrency={}",
        condition_id,
        extraction_mode,
        not ablation_disable_review,
        not ablation_disable_target_guard,
        ablation_original_only,
        len(entry_ids),
        concurrency,
    )

    t0 = time.time()
    try:
        await run_evaluation(
            base_url=base_url,
            concurrency=concurrency,
            entry_ids=entry_ids,
            force_reextract=force_reextract,
            extraction_profile=extraction_profile,
            extraction_mode=extraction_mode,
            ablation_disable_review=ablation_disable_review,
            ablation_disable_target_guard=ablation_disable_target_guard,
            ablation_original_only=ablation_original_only,
        )
    except Exception as exc:  # noqa: BLE001 - surface any pipeline failure
        logger.exception("run_evaluation failed for condition '{}': {}", condition_id, exc)
        return 1
    elapsed = time.time() - t0
    logger.info(
        "Condition '{}' finished in {:.0f}s. See the eval report printed above.",
        condition_id,
        elapsed,
    )

    # Save a compact runner-level provenance wrapper so the N=50 report
    # directory records which manifest/config produced each run even when
    # the raw eval report path is elsewhere.
    wrapper = {
        "runner": "benchmark.runners.n50_comparison",
        "condition_id": condition_id,
        "condition_config": config,
        "manifest_path": str(manifest_path),
        "manifest_entry_count": len(entry_ids),
        "entry_ids": entry_ids,
        "base_url": base_url,
        "concurrency": concurrency,
        "wall_clock_s": round(elapsed, 2),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "note": (
            "Detailed per-entry metrics are written by run_evaluation to the "
            "eval report path printed in the pipeline log above. This file "
            "records run-level provenance only."
        ),
    }
    wrapper_path = _save_report(condition_id, wrapper)
    logger.info("Runner provenance saved: {}", wrapper_path)
    return 0


async def _arun(args: argparse.Namespace) -> int:
    """Async entry point: load config + manifest, dispatch to the right runner."""
    config = load_condition_config(args.condition)
    condition_id = config.get("condition_id", args.condition)

    if config.get("is_prompt_only", False):
        return await _run_prompt_only(condition_id, config)

    manifest_path = Path(args.manifest) if args.manifest else DEFAULT_MANIFEST
    entry_ids = load_manifest_entry_ids(manifest_path)
    logger.info(
        "Loaded {} entry IDs from manifest {}", len(entry_ids), manifest_path
    )
    return await _run_pipeline_condition(
        condition_id=condition_id,
        config=config,
        entry_ids=entry_ids,
        base_url=args.base_url,
        concurrency=args.concurrency,
        manifest_path=manifest_path,
    )


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="benchmark.runners.n50_comparison",
        description=(
            "Unified N=50 comparison/ablation experiment runner. "
            "Selects a condition config and executes it on the locked "
            "N=50 manifest."
        ),
    )
    parser.add_argument(
        "--condition",
        required=True,
        help=(
            "Condition id (filename stem in "
            f"{CONDITIONS_DIR}). "
            f"Available: {', '.join(_list_available_condition_ids()) or '<none>'}."
        ),
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Max concurrent pipeline submissions (default: 4).",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Pipeline base URL (default: http://localhost:8000).",
    )
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST),
        help=(
            "Path to the locked N=50 manifest JSON "
            f"(default: {DEFAULT_MANIFEST})."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for ``python -m benchmark.runners.n50_comparison``.

    Args:
        argv: Optional argument vector (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code.
    """
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="{time:HH:mm:ss} | {level:<7} | {message}",
    )
    args = _build_parser().parse_args(argv)
    return asyncio.run(_arun(args))


if __name__ == "__main__":
    raise SystemExit(main())
