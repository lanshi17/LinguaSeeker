"""B4 baseline: single-agent chain-of-thought style extraction."""
from __future__ import annotations

from benchmark.layer3.baselines.llm_common import make_extractor
from benchmark.layer3.baselines.runner import BaselineEntry, BaselineEvidenceItem, run_baseline_cli

BASELINE_ID = "B4"
BASELINE_NAME = "Single-agent CoT LLM"


async def extract(entry: BaselineEntry, source_text: str) -> list[BaselineEvidenceItem]:
    extractor = make_extractor("single_agent_cot")
    return await extractor.extract(entry, source_text)


def main() -> None:
    run_baseline_cli(BASELINE_ID, BASELINE_NAME, extract)


if __name__ == "__main__":
    main()
