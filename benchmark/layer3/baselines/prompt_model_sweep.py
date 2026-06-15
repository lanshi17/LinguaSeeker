"""Run prompt-only extraction baselines across multiple provider model aliases."""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import time

from loguru import logger

from benchmark.layer3.baselines.llm_common import make_extractor
from benchmark.layer3.baselines.model_sweep_contracts import (
    PromptModelSpec,
    PromptModelSweepManifest,
    load_prompt_model_sweep_manifest,
)
from benchmark.layer3.baselines.runner import BaselineConfig, run_baseline_evaluation
from benchmark.layer3.evaluate import GROUND_TRUTH_DIR, REPORTS_DIR


def build_baseline_config(
    *,
    manifest: PromptModelSweepManifest,
    spec: PromptModelSpec,
    ground_truth_dir: Path,
    reports_dir: Path,
    entry_ids: tuple[str, ...],
    limit: int | None,
    save_report: bool,
) -> BaselineConfig:
    """Build a baseline runner config for one model in the sweep."""
    return BaselineConfig(
        baseline_id=spec.baseline_id,
        baseline_name=spec.baseline_name,
        ground_truth_dir=ground_truth_dir,
        reports_dir=reports_dir,
        entry_ids=entry_ids,
        limit=limit,
        save_report=save_report,
        metadata={
            "run_label": manifest.run_label,
            "prompt_mode": manifest.prompt_mode,
            "provider_family": spec.provider_family,
            "model": spec.model,
            "temperature": manifest.temperature,
            "max_tokens": manifest.max_tokens,
            "input_max_chars": manifest.input_max_chars,
            "run_date": time.strftime("%Y-%m-%d"),
        },
    )


def build_extractor(*, manifest: PromptModelSweepManifest, spec: PromptModelSpec):
    """Build the configured prompt-only extractor for one model spec."""
    return make_extractor(
        mode=manifest.prompt_mode,
        model_override=spec.model,
        temperature=manifest.temperature,
        max_tokens_override=manifest.max_tokens,
        input_max_chars=manifest.input_max_chars,
        use_raw_client=True,
    )


async def run_model_sweep(
    *,
    manifest_path: Path,
    ground_truth_dir: Path = GROUND_TRUTH_DIR,
    reports_dir: Path = REPORTS_DIR,
    entry_ids: tuple[str, ...] = (),
    limit: int | None = None,
    save_report: bool = True,
    continue_on_error: bool = False,
) -> list[Path]:
    """Run all model specs in a prompt-only sweep manifest."""
    manifest = load_prompt_model_sweep_manifest(manifest_path)
    report_paths: list[Path] = []
    for spec in manifest.models:
        try:
            extractor = build_extractor(manifest=manifest, spec=spec)
            report = await run_baseline_evaluation(
                build_baseline_config(
                    manifest=manifest,
                    spec=spec,
                    ground_truth_dir=ground_truth_dir,
                    reports_dir=reports_dir,
                    entry_ids=entry_ids,
                    limit=limit,
                    save_report=save_report,
                ),
                extractor.extract,
            )
        except Exception:
            if not continue_on_error:
                raise
            logger.exception("Prompt model sweep failed for {} ({})", spec.baseline_id, spec.model)
            continue
        if report.report_path is not None:
            report_paths.append(report.report_path)
    return report_paths


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for prompt-only model sweeps."""
    parser = argparse.ArgumentParser(description="Run prompt-only model-sweep baselines.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--ground-truth-dir", type=Path, default=GROUND_TRUTH_DIR)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--entries", nargs="*", default=())
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-save", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args(argv)

    report_paths = asyncio.run(
        run_model_sweep(
            manifest_path=args.manifest,
            ground_truth_dir=args.ground_truth_dir,
            reports_dir=args.reports_dir,
            entry_ids=tuple(args.entries),
            limit=args.limit,
            save_report=not args.no_save,
            continue_on_error=args.continue_on_error,
        )
    )
    for report_path in report_paths:
        print(f"REPORT: {report_path}")


if __name__ == "__main__":
    main()
