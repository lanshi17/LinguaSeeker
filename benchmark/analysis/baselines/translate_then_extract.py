"""B1 baseline: translate the document to English, then extract once."""
from __future__ import annotations

from benchmark.analysis.baselines.llm_common import make_extractor
from benchmark.analysis.baselines.runner import BaselineEntry, BaselineEvidenceItem, run_baseline_cli

BASELINE_ID = "B1"
BASELINE_NAME = "Translate-then-extract"


async def extract(entry: BaselineEntry, source_text: str) -> list[BaselineEvidenceItem]:
    extractor = make_extractor("translate_then_extract")
    return await extractor.extract(entry, source_text)


def main() -> None:
    run_baseline_cli(BASELINE_ID, BASELINE_NAME, extract)


if __name__ == "__main__":
    main()
