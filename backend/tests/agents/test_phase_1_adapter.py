"""Tests for Phase 1 adapter (document acquisition)."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.contracts import (
    PipelineGraphState,
    PipelineMode,
    SourceType,
    AcquisitionOutput,
    PhaseStatus,
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


def _make_acquisition_result(success: bool = True, **kwargs):
    from src.core.ingest_and_digitize_data.document_acquisition.contracts import (
        DocumentAcquisitionResult,
        AcquisitionSource,
    )

    return DocumentAcquisitionResult(
        success=success,
        source=AcquisitionSource.LOCAL,
        **kwargs,
    )


def _stored_pdf(path: str = "/tmp/test.pdf"):
    from src.core.ingest_and_digitize_data.document_acquisition.local_upload.contracts import (
        LocalStoredFile,
    )

    return LocalStoredFile(
        file_path=path,
        sha256="abc123",
        original_filename="test.pdf",
        size=1024,
        content_type="application/pdf",
    )


@pytest.mark.asyncio
async def test_phase_1_adapter_success(sample_state: PipelineGraphState):
    """Phase 1 adapter successfully acquires the document PDF."""
    mock_acquisition = MagicMock()
    mock_acquisition.acquire = AsyncMock(
        return_value=_make_acquisition_result(stored_file=_stored_pdf())
    )

    adapter = Phase1Adapter(acquisition_service=mock_acquisition)

    result_state = await adapter.run(sample_state)

    assert result_state.phase_1_output is not None
    assert result_state.phase_1_output.pdf_path == "/tmp/test.pdf"
    assert isinstance(result_state.phase_1_output, AcquisitionOutput)
    assert result_state.phase_1_status.status == PhaseStatus.COMPLETED
    mock_acquisition.acquire.assert_awaited_once()


@pytest.mark.asyncio
async def test_phase_1_adapter_raises_permanent_on_acquisition_failure(
    sample_state: PipelineGraphState,
):
    """Phase 1 adapter raises PermanentPhaseError on acquisition failure."""
    mock_acquisition = MagicMock()
    mock_acquisition.acquire = AsyncMock(
        return_value=_make_acquisition_result(success=False, error="File not found")
    )

    adapter = Phase1Adapter(acquisition_service=mock_acquisition)

    with pytest.raises(PermanentPhaseError, match="File not found"):
        await adapter.run(sample_state)


@pytest.mark.asyncio
async def test_phase_1_adapter_raises_retryable_on_timeout(
    sample_state: PipelineGraphState,
):
    """Phase 1 adapter raises RetryablePhaseError on transient acquisition errors."""
    mock_acquisition = MagicMock()
    mock_acquisition.acquire = AsyncMock(side_effect=TimeoutError("acquisition timed out"))

    adapter = Phase1Adapter(acquisition_service=mock_acquisition)

    with pytest.raises(RetryablePhaseError, match="timed out"):
        await adapter.run(sample_state)


@pytest.mark.asyncio
async def test_phase_1_adapter_reads_upload_file_as_bytes(tmp_path):
    """Phase 1 adapter reads upload_file_path as bytes, not path string."""
    # Create a real temp file to be read by the adapter
    upload_file = tmp_path / "test.pdf"
    upload_file.write_bytes(b"%PDF-1.4 fake content")

    state = PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        upload_file_path=str(upload_file),
    )

    captured_request = {}

    async def capture_acquire(request):
        captured_request["content"] = request.content
        captured_request["filename"] = request.filename
        return _make_acquisition_result(
            stored_file=_stored_pdf("/tmp/stored.pdf"),
        )

    mock_acquisition = MagicMock()
    mock_acquisition.acquire = AsyncMock(side_effect=capture_acquire)

    adapter = Phase1Adapter(acquisition_service=mock_acquisition)

    result_state = await adapter.run(state)

    # Verify the adapter read file bytes, not the path string
    assert captured_request["content"] == b"%PDF-1.4 fake content"
    assert captured_request["filename"] == "test.pdf"
    assert isinstance(captured_request["content"], bytes)
    assert result_state.phase_1_output is not None
