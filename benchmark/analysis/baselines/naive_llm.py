"""B0 baseline: naive single-prompt LLM extraction."""
from __future__ import annotations

from benchmark.analysis.baselines.llm_common import make_extractor
from benchmark.analysis.baselines.runner import BaselineEntry, BaselineEvidenceItem, run_baseline_cli

BASELINE_ID = "B0"
BASELINE_NAME = "Naive single-prompt LLM"


async def extract(entry: BaselineEntry, source_text: str) -> list[BaselineEvidenceItem]:
    extractor = make_extractor("naive")
    return await extractor.extract(entry, source_text)


def main() -> None:
    run_baseline_cli(BASELINE_ID, BASELINE_NAME, extract)


if __name__ == "__main__":
    main()
