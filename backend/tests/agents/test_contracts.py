"""Tests for pipeline orchestrator contracts."""

from src.agents.contracts import (
    PipelineGraphState,
    PhaseStatus,
    PipelineMode,
    SourceType,
    PipelineStatus,
    AcquisitionOutput,
    ParseOutput,
    TranslationExtractionOutput,
    StandardizationOutput,
    PhaseErrorDetail,
    PhaseStatusDetail,
    PhaseError,
    RetryablePhaseError,
    PermanentPhaseError,
    SkipPhase4Reason,
)


def test_pipeline_graph_state_creation():
    """State can be created with minimal fields."""
    state = PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )
    assert state.processing_run_id == "run-123"
    assert state.source_document_id == "doc-456"
    assert state.phase_1_status.status == PhaseStatus.PENDING
    assert state.phase_2_status.status == PhaseStatus.PENDING
    assert state.phase_3_status.status == PhaseStatus.PENDING
    assert state.phase_4_status.status == PhaseStatus.PENDING
    assert state.error_message is None
    assert state.pipeline_status == PipelineStatus.PENDING


def test_pipeline_graph_state_with_structured_error():
    """State can record structured error details per phase."""
    state = PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )
    state.phase_1_status = PhaseStatusDetail(
        status=PhaseStatus.FAILED,
        error=PhaseErrorDetail(
            message="Acquisition failed: PDF download timeout",
            retryable=True,
            attempt=2,
            max_retries=2,
        ),
    )
    assert state.phase_1_status.status == PhaseStatus.FAILED
    assert state.phase_1_status.error.retryable is True
    assert state.phase_1_status.error.attempt == 2


def test_pipeline_graph_state_serialization():
    """State serializes to dict for LangGraph persistence."""
    state = PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )
    data = state.model_dump()
    assert data["processing_run_id"] == "run-123"
    assert data["phase_1_status"]["status"] == "pending"


def test_phase_status_enum():
    """PhaseStatus enum has expected values."""
    assert PhaseStatus.PENDING == "pending"
    assert PhaseStatus.RUNNING == "running"
    assert PhaseStatus.COMPLETED == "completed"
    assert PhaseStatus.SKIPPED == "skipped"
    assert PhaseStatus.FAILED == "failed"


def test_pipeline_status_enum():
    """PipelineStatus enum has expected values."""
    assert PipelineStatus.PENDING == "pending"
    assert PipelineStatus.RUNNING == "running"
    assert PipelineStatus.COMPLETED == "completed"
    assert PipelineStatus.FAILED == "failed"


def test_skip_phase_4_reason_enum():
    """SkipPhase4Reason enum captures all skip conditions."""
    assert SkipPhase4Reason.NOT_RELEVANT == "not_relevant"
    assert SkipPhase4Reason.NO_ENTITIES == "no_entities"
    assert SkipPhase4Reason.NO_CANDIDATES == "no_candidates"


def test_phase1_output_typed():
    """AcquisitionOutput (Phase 1) is a typed model, not a bare dict."""
    output = AcquisitionOutput(pdf_path="/tmp/test.pdf")
    assert output.pdf_path == "/tmp/test.pdf"


def test_phase2_output_typed():
    """ParseOutput (Phase 2) is a typed model, not a bare dict."""
    output = ParseOutput(
        md_path="/tmp/test.md",
        metadata_path="/tmp/test.json",
        output_dir="/tmp/phase_2",
        images_dir="/tmp/images",
    )
    assert output.metadata_path == "/tmp/test.json"


def test_phase3_output_typed():
    """TranslationExtractionOutput (Phase 3) is a typed model, not a bare dict."""
    output = TranslationExtractionOutput(
        output_dir="/tmp/phase_3",
        original_json_path="/tmp/original.json",
        translated_json_path="/tmp/translated.json",
        extraction_result_path="/tmp/extraction.json",
        source_language="zh",
    )
    assert output.source_language == "zh"


def test_phase4_output_typed():
    """StandardizationOutput (Phase 4) is a typed model, not a bare dict."""
    output = StandardizationOutput(
        match_count=10,
        standardized_count=8,
        ambiguous_count=1,
        unmapped_count=1,
    )
    assert output.match_count == 10


def test_retryable_phase_error():
    """RetryablePhaseError is an Exception with retry metadata."""
    err = RetryablePhaseError("API timeout", phase=1, attempt=1)
    assert isinstance(err, Exception)
    assert isinstance(err, PhaseError)
    assert isinstance(err, RetryablePhaseError)
    assert err.phase == 1
    assert err.attempt == 1
    assert str(err) == "API timeout"


def test_permanent_phase_error():
    """PermanentPhaseError is an Exception with phase metadata."""
    err = PermanentPhaseError("Configuration error", phase=2)
    assert isinstance(err, Exception)
    assert isinstance(err, PhaseError)
    assert isinstance(err, PermanentPhaseError)
    assert err.phase == 2
    assert str(err) == "Configuration error"


def test_phase_status_detail():
    """PhaseStatusDetail tracks timing and errors per phase."""
    detail = PhaseStatusDetail(
        status=PhaseStatus.COMPLETED,
        started_at="2026-05-29T10:00:00",
        completed_at="2026-05-29T10:05:00",
        duration_seconds=300.0,
    )
    assert detail.status == PhaseStatus.COMPLETED
    assert detail.duration_seconds == 300.0
    assert detail.error is None


def test_pipeline_graph_state_carries_extraction_target() -> None:
    from src.core.evidence_extraction.contracts import (
        ExtractionTarget,
    )

    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")
    state = PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        extraction_target=target,
    )

    assert state.extraction_target == target
    assert state.model_dump()["extraction_target"]["gene_symbol"] == "ABCA3"
