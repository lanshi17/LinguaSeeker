"""Test that Phase1Adapter consumes pre_parsed_markdown from acquisition output."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.contracts import PipelineGraphState, PipelineMode, SourceType
from src.agents.phase_1_adapter import Phase1Adapter


@pytest.mark.asyncio
async def test_phase_1_uses_pre_parsed_markdown_from_acquisition(tmp_path):
    """When acquisition returns a download with pre_parsed_markdown,
    Phase1Adapter writes it directly and DOES NOT call parse_local_files_and_save.
    """
    from src.core.ingest_and_digitize_data.document_acquisition.contracts import (
        AcquisitionSource,
        DocumentAcquisitionResult,
        DocumentDownloadEntry,
    )

    # Send Phase 1 output to the temp dir so we don't write into repo data/.
    state = PipelineGraphState(
        processing_run_id="run-pre-parsed",
        source_document_id="doc-pre",
        mode=PipelineMode.FULL,
        source_type=SourceType.ONLINE,
        query="MECP2 Rett",
    )

    pdf_path = str(tmp_path / "downloaded.pdf")
    markdown = "# Title\n\nMECP2 c.473C>T pathogenic variant in proband."

    mock_acquisition = MagicMock()
    mock_acquisition.acquire = AsyncMock(
        return_value=DocumentAcquisitionResult(
            success=True,
            source=AcquisitionSource.ONLINE,
            downloads=[
                DocumentDownloadEntry(
                    file_path=pdf_path,
                    pdf_url="https://x/y.pdf",
                    pre_parsed_markdown=markdown,
                ),
            ],
        )
    )

    mock_parse = MagicMock()
    # Should NOT be called when pre_parsed_markdown is present.
    mock_parse.parse_local_files_and_save = AsyncMock()

    adapter = Phase1Adapter(
        acquisition_service=mock_acquisition,
        parse_service=mock_parse,
    )

    result = await adapter.run(state)

    mock_parse.parse_local_files_and_save.assert_not_called()
    assert result.phase_1_output is not None
    assert result.phase_1_output.pdf_path == pdf_path
    # _build_from_pre_parsed writes to data/pipeline/<run>/phase_1/output.md
    assert result.phase_1_output.md_path.endswith("output.md")
    # Read what was written and confirm it contains our markdown.
    from pathlib import Path
    import json as _json

    written = Path(result.phase_1_output.md_path).read_text(encoding="utf-8")
    assert "MECP2 c.473C>T" in written

    # Title is extracted from the first "# " heading into metadata.json
    meta = _json.loads(Path(result.phase_1_output.metadata_path).read_text(encoding="utf-8"))
    assert meta["title"] == "Title"
