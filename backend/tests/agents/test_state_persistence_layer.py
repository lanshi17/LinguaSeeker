"""Tests for pipeline state persistence layer."""
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.agents.contracts import (
    PipelineGraphState,
    PhaseStatus,
    PipelineMode,
    SourceType,
    PipelineStatus,
    PhaseStatusDetail,
    PhaseErrorDetail,
)
from src.agents.state_persistence import DirectStatePersistence, SessionBoundStatePersistence


def _make_session_factory(session: AsyncSession):
    """Wrap a single session as an async_sessionmaker-compatible factory."""

    @asynccontextmanager
    async def _factory():
        yield session

    return _factory


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
    """DirectStatePersistence can save state to database."""
    service = DirectStatePersistence(db_session)
    await service.save(sample_state)

    loaded = await service.load(sample_state.processing_run_id)
    assert loaded is not None
    assert loaded.processing_run_id == sample_state.processing_run_id
    assert loaded.phase_1_status.status == PhaseStatus.COMPLETED
    assert loaded.phase_2_status.status == PhaseStatus.RUNNING


@pytest.mark.asyncio
async def test_load_nonexistent_state(db_session: AsyncSession):
    """Loading nonexistent state returns None."""
    service = DirectStatePersistence(db_session)
    loaded = await service.load(str(uuid.uuid4()))
    assert loaded is None


@pytest.mark.asyncio
async def test_save_state_idempotent(db_session: AsyncSession, sample_state: PipelineGraphState):
    """Saving state multiple times updates the record (checkpoint semantics)."""
    service = DirectStatePersistence(db_session)
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

    service = DirectStatePersistence(db_session)
    await service.save(sample_state)

    loaded = await service.load(sample_state.processing_run_id)
    assert loaded.phase_1_status.error is not None
    assert loaded.phase_1_status.error.retryable is True
    assert loaded.phase_1_status.error.attempt == 2


@pytest.mark.asyncio
async def test_session_bound_save_uses_upsert():
    """SessionBoundStatePersistence.save() uses INSERT ON CONFLICT for writes.

    Note: save() now reads the existing state first for the state transition
    guard (one extra SELECT), but the write path still uses upsert for atomicity.
    """
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    # Transition guard reads existing state — return None (new run)
    mock_session.get = AsyncMock(return_value=None)

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    persistence = SessionBoundStatePersistence(mock_factory)

    state = PipelineGraphState(
        processing_run_id=str(uuid.uuid4()),
        source_document_id=str(uuid.uuid4()),
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        pipeline_status=PipelineStatus.RUNNING,
    )

    await persistence.save(state)

    # Verify execute was called (INSERT ... ON CONFLICT upsert)
    mock_session.execute.assert_awaited()
    # session.get is called for the state transition guard
    mock_session.get.assert_awaited()
    # session.add is NOT used — writes go through upsert
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_recover_orphaned_runs_ignores_fresh_heartbeat(db_session: AsyncSession):
    """Recovery must not fail runs with a recent heartbeat."""
    persistence = SessionBoundStatePersistence(_make_session_factory(db_session))

    state = PipelineGraphState(
        processing_run_id=str(uuid.uuid4()),
        source_document_id=str(uuid.uuid4()),
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        pipeline_status=PipelineStatus.RUNNING,
    )
    await persistence.save(
        state,
        owner_worker_id="worker-a",
        heartbeat_at=datetime.now(timezone.utc),
    )

    recovered = await persistence.recover_orphaned_runs(heartbeat_timeout_seconds=120)

    assert recovered == 0
    loaded = await persistence.load(state.processing_run_id)
    assert loaded is not None
    assert loaded.pipeline_status == PipelineStatus.RUNNING


@pytest.mark.asyncio
async def test_recover_orphaned_runs_fails_stale_heartbeat(db_session: AsyncSession):
    """Recovery must fail runs whose heartbeat is older than the timeout."""
    persistence = SessionBoundStatePersistence(_make_session_factory(db_session))

    state = PipelineGraphState(
        processing_run_id=str(uuid.uuid4()),
        source_document_id=str(uuid.uuid4()),
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        pipeline_status=PipelineStatus.RUNNING,
    )
    await persistence.save(
        state,
        owner_worker_id="worker-a",
        heartbeat_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )

    recovered = await persistence.recover_orphaned_runs(heartbeat_timeout_seconds=120)

    assert recovered == 1
    loaded = await persistence.load(state.processing_run_id)
    assert loaded is not None
    assert loaded.pipeline_status == PipelineStatus.FAILED
    assert loaded.error_message == "Pipeline heartbeat expired"
