"""Tests for pipeline state persistence layer."""
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.agents.contracts import (
    PipelineGraphState,
    PhaseStatus,
    PipelineMode,
    SourceType,
    PhaseStatusDetail,
    PhaseErrorDetail,
)
from src.agents.state_persistence import StatePersistenceService


@pytest.fixture
def sample_state() -> PipelineGraphState:
    state = PipelineGraphState(
        processing_run_id=str(uuid.uuid4()),
        source_document_id=str(uuid.uuid4()),
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )
    state.phase_1_status = PhaseStatusDetail(
        status=PhaseStatus.COMPLETED,
        started_at="2026-05-29T10:00:00",
    )
    state.phase_2_status = PhaseStatusDetail(
        status=PhaseStatus.RUNNING,
    )
    return state


@pytest.mark.asyncio
async def test_save_state(db_session: AsyncSession, sample_state: PipelineGraphState):
    """StatePersistenceService can save state to database."""
    service = StatePersistenceService(db_session)
    await service.save(sample_state)

    loaded = await service.load(sample_state.processing_run_id)
    assert loaded is not None
    assert loaded.processing_run_id == sample_state.processing_run_id
    assert loaded.phase_1_status.status == PhaseStatus.COMPLETED
    assert loaded.phase_2_status.status == PhaseStatus.RUNNING


@pytest.mark.asyncio
async def test_load_nonexistent_state(db_session: AsyncSession):
    """Loading nonexistent state returns None."""
    service = StatePersistenceService(db_session)
    loaded = await service.load(str(uuid.uuid4()))
    assert loaded is None


@pytest.mark.asyncio
async def test_save_state_idempotent(db_session: AsyncSession, sample_state: PipelineGraphState):
    """Saving state multiple times updates the record (checkpoint semantics)."""
    service = StatePersistenceService(db_session)
    await service.save(sample_state)

    sample_state.phase_2_status = PhaseStatusDetail(
        status=PhaseStatus.COMPLETED,
        duration_seconds=120.0,
    )
    await service.save(sample_state)

    loaded = await service.load(sample_state.processing_run_id)
    assert loaded.phase_2_status.status == PhaseStatus.COMPLETED
    assert loaded.phase_2_status.duration_seconds == 120.0


@pytest.mark.asyncio
async def test_save_preserves_structured_errors(
    db_session: AsyncSession, sample_state: PipelineGraphState
):
    """Structured error details survive round-trip through database."""
    sample_state.phase_1_status = PhaseStatusDetail(
        status=PhaseStatus.FAILED,
        error=PhaseErrorDetail(
            message="API timeout",
            retryable=True,
            attempt=2,
            max_retries=2,
        ),
    )

    service = StatePersistenceService(db_session)
    await service.save(sample_state)

    loaded = await service.load(sample_state.processing_run_id)
    assert loaded.phase_1_status.error is not None
    assert loaded.phase_1_status.error.retryable is True
    assert loaded.phase_1_status.error.attempt == 2
