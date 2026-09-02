"""Tests for Phase 2 adapter (document parsing)."""

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from src.agents.contracts import (
    PipelineGraphState,
    PipelineMode,
    SourceType,
    ParseOutput,
    PhaseStatus,
    AcquisitionOutput,
    PermanentPhaseError,
    RetryablePhaseError,
)
from src.agents.phase_2_adapter import Phase2Adapter


@pytest.fixture
def sample_state(tmp_path) -> PipelineGraphState:
    return PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        phase_1_output=AcquisitionOutput(pdf_path=str(tmp_path / "test.pdf")),
    )


def _make_parse_result():
    from src.core.ingest_and_digitize_data.parse_document.contracts import (
        MinerULocalBatchSaveResult,
        MinerULocalBatchParseResult,
        MinerUBatchStatus,
        SavedFiles,
    )

    return MinerULocalBatchSaveResult(
        batch_id="batch-1",
        parse_result=MinerULocalBatchParseResult(
            batch_id="batch-1",
            status=MinerUBatchStatus(batch_id="batch-1"),
            results={},
        ),
        saved_files={
            "test.pdf": SavedFiles(
                md_path=Path("/tmp/test.md"),
                metadata_path=Path("/tmp/test.json"),
                output_dir=Path("/tmp/output"),
                created_at=datetime.now(),
                images_dir=Path("/tmp/images"),
            )
        },
    )


@pytest.mark.asyncio
async def test_phase_2_adapter_success(sample_state: PipelineGraphState):
    """Phase 2 adapter parses the Phase 1 PDF and writes the phase_2 output dir."""
    mock_parse = MagicMock()
    mock_parse.parse_local_files_and_save = AsyncMock(return_value=_make_parse_result())

    adapter = Phase2Adapter(parse_service=mock_parse)

    result_state = await adapter.run(sample_state)

    assert result_state.phase_2_output is not None
    assert isinstance(result_state.phase_2_output, ParseOutput)
    assert result_state.phase_2_output.md_path == "/tmp/test.md"
    assert result_state.phase_2_output.metadata_path == "/tmp/test.json"
    assert result_state.phase_2_output.images_dir == "/tmp/images"
    assert result_state.phase_2_status.status == PhaseStatus.COMPLETED

    mock_parse.parse_local_files_and_save.assert_awaited_once()
    kwargs = mock_parse.parse_local_files_and_save.call_args.kwargs
    assert kwargs["file_paths"] == [sample_state.phase_1_output.pdf_path]
    assert kwargs["output_dir"].endswith(f"data/pipeline/{sample_state.processing_run_id}/phase_2")


@pytest.mark.asyncio
async def test_phase_2_adapter_raises_permanent_without_phase_1_output(sample_state: PipelineGraphState):
    """Phase 2 adapter raises PermanentPhaseError when Phase 1 produced no PDF."""
    state = sample_state.model_copy(update={"phase_1_output": AcquisitionOutput(pdf_path="")})

    mock_parse = MagicMock()
    adapter = Phase2Adapter(parse_service=mock_parse)

    with pytest.raises(PermanentPhaseError, match="Phase 1 output"):
        await adapter.run(state)
    mock_parse.parse_local_files_and_save.assert_not_called()


@pytest.mark.asyncio
async def test_phase_2_adapter_raises_permanent_when_no_saved_files(sample_state: PipelineGraphState):
    """Phase 2 adapter raises PermanentPhaseError when parsing produced no output."""
    from src.core.ingest_and_digitize_data.parse_document.contracts import (
        MinerULocalBatchSaveResult,
        MinerULocalBatchParseResult,
        MinerUBatchStatus,
    )

    mock_parse = MagicMock()
    mock_parse.parse_local_files_and_save = AsyncMock(
        return_value=MinerULocalBatchSaveResult(
            batch_id="batch-1",
            parse_result=MinerULocalBatchParseResult(
                batch_id="batch-1",
                status=MinerUBatchStatus(batch_id="batch-1"),
                results={},
            ),
            saved_files={},
        )
    )

    adapter = Phase2Adapter(parse_service=mock_parse)

    with pytest.raises(PermanentPhaseError, match="no output files"):
        await adapter.run(sample_state)


@pytest.mark.asyncio
async def test_phase_2_adapter_raises_retryable_on_mineru_timeout(sample_state: PipelineGraphState):
    """Phase 2 adapter raises RetryablePhaseError on MinerU timeout."""
    from src.core.ingest_and_digitize_data.parse_document.exceptions import (
        MinerUTimeoutError,
    )

    mock_parse = MagicMock()
    mock_parse.parse_local_files_and_save = AsyncMock(
        side_effect=MinerUTimeoutError(total_timeout=120.0)
    )

    adapter = Phase2Adapter(parse_service=mock_parse)

    with pytest.raises(RetryablePhaseError, match="timed out"):
        await adapter.run(sample_state)


@pytest.mark.asyncio
async def test_phase_2_adapter_writes_pre_parsed_markdown(tmp_path):
    """Phase 2 adapter writes pre-parsed markdown as output.md + metadata.json."""
    markdown = "# Rett Syndrome Study\n\nMECP2 c.473C>T pathogenic variant in proband."
    state = PipelineGraphState(
        processing_run_id="run-pre-parsed",
        source_document_id="doc-pre",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        pre_parsed_markdown=markdown,
    )

    mock_parse = MagicMock()
    mock_parse.parse_local_files_and_save = AsyncMock()

    adapter = Phase2Adapter(parse_service=mock_parse)

    result = await adapter.run(state)

    # MinerU is bypassed entirely for pre-parsed markdown
    mock_parse.parse_local_files_and_save.assert_not_called()

    assert result.phase_2_output is not None
    assert result.phase_2_output.md_path.endswith("output.md")
    assert result.phase_2_status.status == PhaseStatus.COMPLETED

    written = Path(result.phase_2_output.md_path).read_text(encoding="utf-8")
    assert "MECP2 c.473C>T" in written

    meta = json.loads(Path(result.phase_2_output.metadata_path).read_text(encoding="utf-8"))
    assert meta["title"] == "Rett Syndrome Study"
    assert meta["pages"][0]["markdown"] == markdown
