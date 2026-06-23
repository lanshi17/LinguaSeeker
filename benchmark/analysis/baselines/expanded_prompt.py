"""B7 baseline: expanded single-prompt LLM extraction (all field categories)."""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from benchmark.analysis.baselines.canonical_models import CANONICAL_GPT5_EXPANDED
from benchmark.analysis.baselines.llm_common import make_extractor
from benchmark.analysis.baselines.runner import (
    BaselineConfig,
    BaselineEntry,
    BaselineEvidenceItem,
    run_baseline_evaluation,
)
from benchmark.core import GROUND_TRUTH_DIR, REPORTS_DIR

BASELINE_ID = "B7"
BASELINE_NAME = "GPT-5 expanded single-prompt evidence extraction"


async def extract(entry: BaselineEntry, source_text: str) -> list[BaselineEvidenceItem]:
    extractor = make_extractor("expanded")
    return await extractor.extract(entry, source_text)


def build_config(
    *,
    ground_truth_dir: Path,
    reports_dir: Path,
    entry_ids: tuple[str, ...],
    limit: int | None,
    save_report: bool,
) -> BaselineConfig:
    """Build B7 config with expanded prompt model metadata."""
    return BaselineConfig(
        baseline_id=BASELINE_ID,
        baseline_name=BASELINE_NAME,
        ground_truth_dir=ground_truth_dir,
        reports_dir=reports_dir,
        entry_ids=entry_ids,
        limit=limit,
        save_report=save_report,
        metadata=CANONICAL_GPT5_EXPANDED.as_metadata(),
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=f"Run {BASELINE_ID}: {BASELINE_NAME}")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--entries", nargs="*", default=())
    parser.add_argument("--ground-truth-dir", type=Path, default=GROUND_TRUTH_DIR)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args(argv)

    report = asyncio.run(
        run_baseline_evaluation(
            build_config(
                ground_truth_dir=args.ground_truth_dir,
                reports_dir=args.reports_dir,
                entry_ids=tuple(args.entries),
                limit=args.limit,
                save_report=not args.no_save,
            ),
            extract,
        )
    )
    overall = report.aggregates["overall"]
    print(f"{BASELINE_ID} {BASELINE_NAME}: N={report.total_entries} overall={overall}")
    if report.report_path is not None:
        print(f"REPORT: {report.report_path}")


if __name__ == "__main__":
    main()
