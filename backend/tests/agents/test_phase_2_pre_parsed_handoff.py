"""Test the pre-parsed markdown handoff across Phase 1 and Phase 2.

With pre-parsed markdown set on the state:
- Phase1Adapter (acquisition) is SKIPPED and produces no PDF path.
- Phase2Adapter (parsing) writes the canonical output.md + metadata.json
  without invoking MinerU.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.contracts import PhaseStatus, PipelineGraphState, PipelineMode, SourceType
from src.agents.phase_1_adapter import Phase1Adapter
from src.agents.phase_2_adapter import Phase2Adapter

MARKDOWN = "# Title\n\nMECP2 c.473C>T pathogenic variant in proband."


@pytest.fixture
def state() -> PipelineGraphState:
    return PipelineGraphState(
        processing_run_id="run-pre-parsed",
        source_document_id="doc-pre",
        mode=PipelineMode.FULL,
        source_type=SourceType.ONLINE,
        query="MECP2 Rett",
        pre_parsed_markdown=MARKDOWN,
    )


@pytest.mark.asyncio
async def test_phase_1_skipped_with_pre_parsed_markdown(state):
    """Phase1Adapter marks acquisition SKIPPED and sets an empty pdf_path."""
    mock_acquisition = MagicMock()
    mock_acquisition.acquire = AsyncMock()

    adapter = Phase1Adapter(acquisition_service=mock_acquisition)

    result = await adapter.run(state)

    mock_acquisition.acquire.assert_not_called()
    assert result.phase_1_status.status == PhaseStatus.SKIPPED
    assert result.phase_1_status.summary == {"reason": "pre_parsed_markdown"}
    assert result.phase_1_output is not None
    assert result.phase_1_output.pdf_path == ""


@pytest.mark.asyncio
async def test_phase_2_writes_pre_parsed_markdown_without_mineru(state):
    """Phase2Adapter consumes the markdown directly, skipping MinerU."""
    mock_parse = MagicMock()
    mock_parse.parse_local_files_and_save = AsyncMock()

    adapter = Phase2Adapter(parse_service=mock_parse)

    result = await adapter.run(state)

    mock_parse.parse_local_files_and_save.assert_not_called()
    assert result.phase_2_status.status == PhaseStatus.COMPLETED
    assert result.phase_2_output is not None
    assert result.phase_2_output.md_path.endswith("output.md")

    written = Path(result.phase_2_output.md_path).read_text(encoding="utf-8")
    assert "MECP2 c.473C>T" in written

    # Title is extracted from the first "# " heading into metadata.json
    meta = json.loads(Path(result.phase_2_output.metadata_path).read_text(encoding="utf-8"))
    assert meta["title"] == "Title"
