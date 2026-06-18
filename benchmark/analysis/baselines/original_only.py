"""B2 baseline: extract once from the original-language document only."""
from __future__ import annotations

from benchmark.analysis.baselines.llm_common import make_extractor
from benchmark.analysis.baselines.runner import BaselineEntry, BaselineEvidenceItem, run_baseline_cli

BASELINE_ID = "B2"
BASELINE_NAME = "Original-only single-pass LLM"


async def extract(entry: BaselineEntry, source_text: str) -> list[BaselineEvidenceItem]:
    extractor = make_extractor("original_only")
    return await extractor.extract(entry, source_text)


def main() -> None:
    run_baseline_cli(BASELINE_ID, BASELINE_NAME, extract)


if __name__ == "__main__":
    main()
