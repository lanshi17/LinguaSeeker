"""Tests for Phase 1 adapter (acquisition + parsing)."""
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from src.agents.contracts import (
    PipelineGraphState,
    PhaseStatus,
    PipelineMode,
    SourceType,
    Phase1Output,
    RetryablePhaseError,
    PermanentPhaseError,
)
from src.agents.phase_1_adapter import Phase1Adapter


@pytest.fixture
def sample_state() -> PipelineGraphState:
    return PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )


@pytest.mark.asyncio
async def test_phase_1_adapter_success(sample_state: PipelineGraphState):
    """Phase 1 adapter successfully acquires and parses document."""
    from src.core.ingest_and_digitize_data.document_acquisition.contracts import (
        DocumentAcquisitionResult,
        AcquisitionSource,
    )
    from src.core.ingest_and_digitize_data.document_acquisition.local_upload.contracts import (
        LocalStoredFile,
    )
    from src.core.ingest_and_digitize_data.parse_document.contracts import (
        MinerULocalBatchSaveResult,
        MinerULocalBatchParseResult,
        MinerUBatchStatus,
        SavedFiles,
    )

    mock_acquisition = MagicMock()
    mock_acquisition.acquire = AsyncMock(
        return_value=DocumentAcquisitionResult(
            success=True,
            source=AcquisitionSource.LOCAL,
            stored_file=LocalStoredFile(
                file_path="/tmp/test.pdf",
                sha256="abc123",
                original_filename="test.pdf",
                size=1024,
                content_type="application/pdf",
            ),
        )
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
    )

    adapter = Phase1Adapter(
        acquisition_service=mock_acquisition,
        parse_service=mock_parse,
    )

    result_state = await adapter.run(sample_state)

    assert result_state.phase_1_output is not None
    assert result_state.phase_1_output.pdf_path == "/tmp/test.pdf"
    assert result_state.phase_1_output.md_path == "/tmp/test.md"
    assert isinstance(result_state.phase_1_output, Phase1Output)


@pytest.mark.asyncio
async def test_phase_1_adapter_raises_permanent_on_acquisition_failure(
    sample_state: PipelineGraphState,
):
    """Phase 1 adapter raises PermanentPhaseError on acquisition failure."""
    from src.core.ingest_and_digitize_data.document_acquisition.contracts import (
        DocumentAcquisitionResult,
        AcquisitionSource,
    )

    mock_acquisition = MagicMock()
    mock_acquisition.acquire = AsyncMock(
        return_value=DocumentAcquisitionResult(
            success=False,
            source=AcquisitionSource.LOCAL,
            error="File not found",
        )
    )

    mock_parse = MagicMock()

    adapter = Phase1Adapter(
        acquisition_service=mock_acquisition,
        parse_service=mock_parse,
    )

    with pytest.raises(PermanentPhaseError, match="File not found"):
        await adapter.run(sample_state)


@pytest.mark.asyncio
async def test_phase_1_adapter_raises_retryable_on_timeout(
    sample_state: PipelineGraphState,
):
    """Phase 1 adapter raises RetryablePhaseError on MinerU timeout."""
    from src.core.ingest_and_digitize_data.document_acquisition.contracts import (
        DocumentAcquisitionResult,
        AcquisitionSource,
    )
    from src.core.ingest_and_digitize_data.document_acquisition.local_upload.contracts import (
        LocalStoredFile,
    )
    from src.core.ingest_and_digitize_data.parse_document.exceptions import (
        MinerUTimeoutError,
    )

    mock_acquisition = MagicMock()
    mock_acquisition.acquire = AsyncMock(
        return_value=DocumentAcquisitionResult(
            success=True,
            source=AcquisitionSource.LOCAL,
            stored_file=LocalStoredFile(
                file_path="/tmp/test.pdf",
                sha256="abc123",
                original_filename="test.pdf",
                size=1024,
                content_type="application/pdf",
            ),
        )
    )

    mock_parse = MagicMock()
    mock_parse.parse_local_files_and_save = AsyncMock(
        side_effect=MinerUTimeoutError(total_timeout=120.0)
    )

    adapter = Phase1Adapter(
        acquisition_service=mock_acquisition,
        parse_service=mock_parse,
    )

    with pytest.raises(RetryablePhaseError, match="timed out"):
        await adapter.run(sample_state)
