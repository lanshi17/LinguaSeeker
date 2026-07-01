"""Integration test for full pipeline orchestrator."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.contracts import (
    PipelineGraphState,
    PipelineMode,
    SourceType,
    PhaseStatus,
    PipelineStatus,
    PhaseStatusDetail,
    Phase1Output,
    SkipPhase3Reason,
)
from src.agents.orchestrator import PipelineOrchestrator
from src.agents.concurrency import RetryablePhaseExecutor


@pytest.mark.asyncio
async def test_graph_compiles_and_routes():
    """Orchestrator graph compiles and has correct structure."""
    mock_adapters = {
        "phase_1": MagicMock(run=AsyncMock()),
        "phase_2": MagicMock(run=AsyncMock()),
        "phase_3": MagicMock(run=AsyncMock()),
    }
    mock_persistence = MagicMock(save=AsyncMock())
    retry_executor = RetryablePhaseExecutor(max_retries=0, backoff_base=0.01)

    orchestrator = PipelineOrchestrator(
        phase_adapters=mock_adapters,
        state_persistence=mock_persistence,
        retry_executor=retry_executor,
    )

    assert orchestrator._graph is not None

    initial_state = PipelineGraphState(
        processing_run_id="test-run",
        source_document_id="test-doc",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )

    assert initial_state.phase_1_status.status == PhaseStatus.PENDING
    assert initial_state.pipeline_status == PipelineStatus.PENDING


@pytest.mark.asyncio
async def test_upstream_validation_rejects_missing_prerequisites():
    """Orchestrator rejects phase-mode runs without completed upstream."""
    mock_adapters = {
        "phase_1": MagicMock(run=AsyncMock()),
        "phase_2": MagicMock(run=AsyncMock()),
        "phase_3": MagicMock(run=AsyncMock()),
    }
    mock_persistence = MagicMock(save=AsyncMock())
    retry_executor = RetryablePhaseExecutor(max_retries=0, backoff_base=0.01)

    orchestrator = PipelineOrchestrator(
        phase_adapters=mock_adapters,
        state_persistence=mock_persistence,
        retry_executor=retry_executor,
    )

    state = PipelineGraphState(
        processing_run_id="test-run",
        source_document_id="test-doc",
        mode=PipelineMode.PHASE,
        source_type=SourceType.LOCAL,
        target_phase=3,
    )

    result = await orchestrator.run(state)

    assert result.pipeline_status == PipelineStatus.FAILED
    assert "upstream" in result.error_message.lower()
    mock_adapters["phase_3"].run.assert_not_called()


@pytest.mark.asyncio
async def test_persistence_called_after_each_phase():
    """State is persisted to PostgreSQL after each phase completes."""
    state = PipelineGraphState(
        processing_run_id="test-run",
        source_document_id="test-doc",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )

    phase1_output = Phase1Output(
        pdf_path="/tmp/test.pdf",
        md_path="/tmp/test.md",
        metadata_path="/tmp/test.json",
        output_dir="/tmp/output",
    )

    state_after_1 = state.model_copy(deep=True)
    state_after_1.phase_1_status = PhaseStatusDetail(status=PhaseStatus.COMPLETED)
    state_after_1.phase_1_output = phase1_output

    state_after_2 = state_after_1.model_copy(deep=True)
    state_after_2.phase_2_status = PhaseStatusDetail(status=PhaseStatus.COMPLETED)

    state_after_3 = state_after_2.model_copy(deep=True)
    state_after_3.phase_3_status = PhaseStatusDetail(status=PhaseStatus.COMPLETED)

    mock_adapters = {
        "phase_1": MagicMock(run=AsyncMock(return_value=state_after_1)),
        "phase_2": MagicMock(run=AsyncMock(return_value=state_after_2)),
        "phase_3": MagicMock(run=AsyncMock(return_value=state_after_3)),
    }
    mock_persistence = MagicMock(save=AsyncMock())
    retry_executor = RetryablePhaseExecutor(max_retries=0, backoff_base=0.01)

    orchestrator = PipelineOrchestrator(
        phase_adapters=mock_adapters,
        state_persistence=mock_persistence,
        retry_executor=retry_executor,
    )

    await orchestrator.run(state)

    # save() called after each phase + final COMPLETED save
    assert mock_persistence.save.call_count >= 3


@pytest.mark.asyncio
async def test_skip_phase_3_reason_flows_through():
    """skip_phase_3_reason set by Phase 2 flows to Phase 3 adapter."""
    state = PipelineGraphState(
        processing_run_id="test-run",
        source_document_id="test-doc",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )

    phase1_output = Phase1Output(
        pdf_path="/tmp/test.pdf",
        md_path="/tmp/test.md",
        metadata_path="/tmp/test.json",
        output_dir="/tmp/output",
    )

    state_after_1 = state.model_copy(deep=True)
    state_after_1.phase_1_status = PhaseStatusDetail(status=PhaseStatus.COMPLETED)
    state_after_1.phase_1_output = phase1_output

    state_after_2 = state_after_1.model_copy(deep=True)
    state_after_2.phase_2_status = PhaseStatusDetail(status=PhaseStatus.COMPLETED)
    state_after_2.skip_phase_3_reason = SkipPhase3Reason.NOT_RELEVANT

    state_after_3 = state_after_2.model_copy(deep=True)
    state_after_3.phase_3_status = PhaseStatusDetail(
        status=PhaseStatus.SKIPPED,
        summary={"reason": "not_relevant"},
    )

    mock_adapters = {
        "phase_1": MagicMock(run=AsyncMock(return_value=state_after_1)),
        "phase_2": MagicMock(run=AsyncMock(return_value=state_after_2)),
        "phase_3": MagicMock(run=AsyncMock(return_value=state_after_3)),
    }
    mock_persistence = MagicMock(save=AsyncMock())
    retry_executor = RetryablePhaseExecutor(max_retries=0, backoff_base=0.01)

    orchestrator = PipelineOrchestrator(
        phase_adapters=mock_adapters,
        state_persistence=mock_persistence,
        retry_executor=retry_executor,
    )

    result = await orchestrator.run(state)

    assert result.skip_phase_3_reason == SkipPhase3Reason.NOT_RELEVANT
    assert result.phase_3_status.status == PhaseStatus.SKIPPED
