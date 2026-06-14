"""B3 baseline: keyword snippet retrieval plus single LLM extraction."""
from __future__ import annotations

from benchmark.layer3.baselines.llm_common import make_extractor
from benchmark.layer3.baselines.runner import BaselineEntry, BaselineEvidenceItem, run_baseline_cli

BASELINE_ID = "B3"
BASELINE_NAME = "Keyword RAG plus LLM"


async def extract(entry: BaselineEntry, source_text: str) -> list[BaselineEvidenceItem]:
    extractor = make_extractor("rag")
    return await extractor.extract(entry, source_text)


def main() -> None:
    run_baseline_cli(BASELINE_ID, BASELINE_NAME, extract)


if __name__ == "__main__":
    main()
