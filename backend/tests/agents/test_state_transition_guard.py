"""Tests for pipeline state transition guards.

Validates that InvalidStateTransitionError is raised for illegal status
pipeline/phase transitions, and that legal transitions pass through.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.agents.contracts import (
    InvalidStateTransitionError,
    PhaseErrorDetail,
    PhaseStatus,
    PhaseStatusDetail,
    PipelineGraphState,
    PipelineMode,
    PipelineStatus,
    SourceType,
    validate_all_phase_transitions,
    validate_phase_status_transition,
    validate_pipeline_status_transition,
)
from src.agents.state_persistence import (
    DirectStatePersistence,
    SessionBoundStatePersistence,
)
from src.dao.postgresql.models import PipelineRunState


# ── Pure validation function tests (no DB) ────────────────────────────────────────


class TestPipelineStatusTransitionValidation:
    """Unit tests for validate_pipeline_status_transition()."""

    @pytest.mark.parametrize(
        "from_status, to_status",
        [
            # Normal forward flow
            (PipelineStatus.PENDING, PipelineStatus.RUNNING),
            (PipelineStatus.PENDING, PipelineStatus.FAILED),
            (PipelineStatus.RUNNING, PipelineStatus.COMPLETED),
            (PipelineStatus.RUNNING, PipelineStatus.FAILED),
            # Phase rerun: terminal → PENDING
            (PipelineStatus.FAILED, PipelineStatus.PENDING),
            (PipelineStatus.COMPLETED, PipelineStatus.PENDING),
            # Identity (metadata-only saves)
            (PipelineStatus.PENDING, PipelineStatus.PENDING),
            (PipelineStatus.RUNNING, PipelineStatus.RUNNING),
            (PipelineStatus.FAILED, PipelineStatus.FAILED),
            (PipelineStatus.COMPLETED, PipelineStatus.COMPLETED),
        ],
    )
    def test_valid_transitions(self, from_status, to_status):
        """Valid transitions must not raise."""
        validate_pipeline_status_transition(from_status, to_status)

    @pytest.mark.parametrize(
        "from_status, to_status",
        [
            # Skipping states
            (PipelineStatus.PENDING, PipelineStatus.COMPLETED),
            # Reversing flow
            (PipelineStatus.RUNNING, PipelineStatus.PENDING),
            (PipelineStatus.COMPLETED, PipelineStatus.RUNNING),
            (PipelineStatus.FAILED, PipelineStatus.RUNNING),
            # Terminal to terminal
            (PipelineStatus.COMPLETED, PipelineStatus.FAILED),
        ],
    )
    def test_invalid_transitions(self, from_status, to_status):
        """Invalid transitions must raise InvalidStateTransitionError."""
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            validate_pipeline_status_transition(from_status, to_status)
        assert from_status.value in str(exc_info.value)
        assert to_status.value in str(exc_info.value)

    def test_invalid_transition_includes_context(self):
        """Context string appears in the error message."""
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            validate_pipeline_status_transition(
                PipelineStatus.COMPLETED,
                PipelineStatus.RUNNING,
                context="run=abc123",
            )
        assert "run=abc123" in str(exc_info.value)
        assert exc_info.value.from_status == "completed"
        assert exc_info.value.to_status == "running"


class TestPhaseStatusTransitionValidation:
    """Unit tests for validate_phase_status_transition()."""

    @pytest.mark.parametrize(
        "from_status, to_status",
        [
            # Normal forward flow
            (PhaseStatus.PENDING, PhaseStatus.RUNNING),
            (PhaseStatus.PENDING, PhaseStatus.SKIPPED),
            (PhaseStatus.PENDING, PhaseStatus.FAILED),
            (PhaseStatus.RUNNING, PhaseStatus.COMPLETED),
            (PhaseStatus.RUNNING, PhaseStatus.FAILED),
            # Phase rerun: terminal → PENDING
            (PhaseStatus.COMPLETED, PhaseStatus.PENDING),
            (PhaseStatus.FAILED, PhaseStatus.PENDING),
            (PhaseStatus.SKIPPED, PhaseStatus.PENDING),
            # Identity (metadata-only saves)
            (PhaseStatus.PENDING, PhaseStatus.PENDING),
            (PhaseStatus.RUNNING, PhaseStatus.RUNNING),
            (PhaseStatus.COMPLETED, PhaseStatus.COMPLETED),
            (PhaseStatus.FAILED, PhaseStatus.FAILED),
            (PhaseStatus.SKIPPED, PhaseStatus.SKIPPED),
        ],
    )
    def test_valid_transitions(self, from_status, to_status):
        """Valid phase transitions must not raise."""
        validate_phase_status_transition(from_status, to_status)

    @pytest.mark.parametrize(
        "from_status, to_status",
        [
            # Reversing
            (PhaseStatus.RUNNING, PhaseStatus.PENDING),
            (PhaseStatus.COMPLETED, PhaseStatus.RUNNING),
            (PhaseStatus.FAILED, PhaseStatus.RUNNING),
            (PhaseStatus.SKIPPED, PhaseStatus.RUNNING),
            # Terminal to terminal
            (PhaseStatus.COMPLETED, PhaseStatus.FAILED),
            (PhaseStatus.FAILED, PhaseStatus.COMPLETED),
            (PhaseStatus.SKIPPED, PhaseStatus.COMPLETED),
            (PhaseStatus.SKIPPED, PhaseStatus.FAILED),
            (PhaseStatus.COMPLETED, PhaseStatus.SKIPPED),
            (PhaseStatus.FAILED, PhaseStatus.SKIPPED),
            # Jump over
            (PhaseStatus.PENDING, PhaseStatus.COMPLETED),
        ],
    )
    def test_invalid_transitions(self, from_status, to_status):
        """Invalid phase transitions must raise."""
        with pytest.raises(InvalidStateTransitionError):
            validate_phase_status_transition(from_status, to_status)


class TestValidateAllPhaseTransitions:
    """Unit tests for validate_all_phase_transitions()."""

    def _make_state(self, phase_statuses: dict[int, PhaseStatus]) -> PipelineGraphState:
        state = PipelineGraphState(
            processing_run_id=str(uuid.uuid4()),
            source_document_id=str(uuid.uuid4()),
            mode=PipelineMode.FULL,
            source_type=SourceType.LOCAL,
        )
        for phase_num, status in phase_statuses.items():
            setattr(
                state,
                f"phase_{phase_num}_status",
                PhaseStatusDetail(status=status),
            )
        return state

    def test_all_identity(self):
        """No phase status changes → no error."""
        old = self._make_state({1: PhaseStatus.RUNNING, 2: PhaseStatus.PENDING, 3: PhaseStatus.PENDING})
        new = self._make_state({1: PhaseStatus.RUNNING, 2: PhaseStatus.PENDING, 3: PhaseStatus.PENDING})
        validate_all_phase_transitions(old, new)  # Should not raise

    def test_valid_single_phase_change(self):
        """One phase transitions forward, others unchanged → OK."""
        old = self._make_state({1: PhaseStatus.RUNNING, 2: PhaseStatus.PENDING, 3: PhaseStatus.PENDING})
        new = self._make_state({1: PhaseStatus.COMPLETED, 2: PhaseStatus.PENDING, 3: PhaseStatus.PENDING})
        validate_all_phase_transitions(old, new)  # Should not raise

    def test_valid_two_phases_advance(self):
        """Multiple phases advancing in sequence → OK."""
        old = self._make_state({1: PhaseStatus.RUNNING, 2: PhaseStatus.PENDING, 3: PhaseStatus.PENDING})
        new = self._make_state({1: PhaseStatus.COMPLETED, 2: PhaseStatus.RUNNING, 3: PhaseStatus.PENDING})
        validate_all_phase_transitions(old, new)  # Should not raise

    def test_invalid_phase_1_reversal(self):
        """Any phase with invalid transition → raises."""
        old = self._make_state({1: PhaseStatus.COMPLETED, 2: PhaseStatus.PENDING, 3: PhaseStatus.PENDING})
        new = self._make_state({1: PhaseStatus.RUNNING, 2: PhaseStatus.PENDING, 3: PhaseStatus.PENDING})
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            validate_all_phase_transitions(old, new)
        assert "phase_1" in str(exc_info.value)

    def test_invalid_phase_3_jump(self):
        """Phase 3 jumping from PENDING to COMPLETED → raises."""
        old = self._make_state({1: PhaseStatus.COMPLETED, 2: PhaseStatus.COMPLETED, 3: PhaseStatus.PENDING})
        new = self._make_state({1: PhaseStatus.COMPLETED, 2: PhaseStatus.COMPLETED, 3: PhaseStatus.COMPLETED})
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            validate_all_phase_transitions(old, new)
        assert "phase_3" in str(exc_info.value)


# ── Persistence layer integration tests (with DB session) ────────────────────


class TestDirectStatePersistenceTransitionGuard:
    """State transition guard integration tests with DirectStatePersistence."""

    def _make_state(
        self,
        pipeline_status: PipelineStatus = PipelineStatus.PENDING,
        phase_1: PhaseStatus = PhaseStatus.PENDING,
        phase_2: PhaseStatus = PhaseStatus.PENDING,
        phase_3: PhaseStatus = PhaseStatus.PENDING,
    ) -> PipelineGraphState:
        state = PipelineGraphState(
            processing_run_id=str(uuid.uuid4()),
            source_document_id=str(uuid.uuid4()),
            mode=PipelineMode.FULL,
            source_type=SourceType.LOCAL,
            pipeline_status=pipeline_status,
        )
        state.phase_1_status = PhaseStatusDetail(status=phase_1)
        state.phase_2_status = PhaseStatusDetail(status=phase_2)
        state.phase_3_status = PhaseStatusDetail(status=phase_3)
        return state

    @pytest.mark.asyncio
    async def test_initial_save_always_allowed(self, db_session: AsyncSession):
        """First save (no existing state) is always allowed."""
        persistence = DirectStatePersistence(db_session)
        state = self._make_state(pipeline_status=PipelineStatus.PENDING)
        await persistence.save(state)  # Should not raise

        loaded = await persistence.load(state.processing_run_id)
        assert loaded is not None
        assert loaded.pipeline_status == PipelineStatus.PENDING

    @pytest.mark.asyncio
    async def test_valid_pipeline_transition_succeeds(self, db_session: AsyncSession):
        """Valid PENDING → RUNNING transition succeeds."""
        persistence = DirectStatePersistence(db_session)
        state = self._make_state(pipeline_status=PipelineStatus.PENDING)
        await persistence.save(state)

        state.pipeline_status = PipelineStatus.RUNNING
        await persistence.save(state)  # Should not raise

        loaded = await persistence.load(state.processing_run_id)
        assert loaded.pipeline_status == PipelineStatus.RUNNING

    @pytest.mark.asyncio
    async def test_invalid_pipeline_transition_raises(self, db_session: AsyncSession):
        """Invalid COMPLETED → RUNNING transition raises."""
        persistence = DirectStatePersistence(db_session)
        state = self._make_state(pipeline_status=PipelineStatus.COMPLETED)
        await persistence.save(state)

        state.pipeline_status = PipelineStatus.RUNNING
        with pytest.raises(InvalidStateTransitionError):
            await persistence.save(state)

        # DB state should remain unchanged (transaction rolled back
        loaded = await persistence.load(state.processing_run_id)
        assert loaded.pipeline_status == PipelineStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_valid_phase_transition_succeeds(self, db_session: AsyncSession):
        """Valid phase PENDING → RUNNING → COMPLETED succeeds."""
        persistence = DirectStatePersistence(db_session)
        state = self._make_state(
            pipeline_status=PipelineStatus.RUNNING,
            phase_1=PhaseStatus.PENDING,
        )
        await persistence.save(state)

        state.phase_1_status = PhaseStatusDetail(status=PhaseStatus.RUNNING)
        await persistence.save(state)

        state.phase_1_status = PhaseStatusDetail(status=PhaseStatus.COMPLETED)
        await persistence.save(state)

        loaded = await persistence.load(state.processing_run_id)
        assert loaded.phase_1_status.status == PhaseStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_invalid_phase_transition_raises(self, db_session: AsyncSession):
        """Invalid phase COMPLETED → RUNNING raises."""
        persistence = DirectStatePersistence(db_session)
        state = self._make_state(
            pipeline_status=PipelineStatus.RUNNING,
            phase_1=PhaseStatus.COMPLETED,
        )
        await persistence.save(state)

        state.phase_1_status = PhaseStatusDetail(status=PhaseStatus.RUNNING)
        with pytest.raises(InvalidStateTransitionError):
            await persistence.save(state)

    @pytest.mark.asyncio
    async def test_metadata_only_save_identity_no_status_change_succeeds(
        self, db_session: AsyncSession
    ):
        """Saving with same status (metadata update) succeeds."""
        persistence = DirectStatePersistence(db_session)
        state = self._make_state(pipeline_status=PipelineStatus.RUNNING)
        await persistence.save(state)

        # Change only non-status fields
        state.started_at = datetime.now(timezone.utc).isoformat()
        state.error_message = None  # Still same status
        await persistence.save(state)  # Should not raise

    @pytest.mark.asyncio
    async def test_phase_rerun_from_failed_succeeds(self, db_session: AsyncSession):
        """Phase rerun: FAILED → PENDING is allowed."""
        persistence = DirectStatePersistence(db_session)
        state = self._make_state(
            pipeline_status=PipelineStatus.FAILED,
            phase_1=PhaseStatus.FAILED,
            phase_2=PhaseStatus.COMPLETED,
        )
        state.error_message = "something broke"
        state.error_phase = 1
        await persistence.save(state)

        # Phase rerun: reset pipeline and target phase to PENDING
        state.pipeline_status = PipelineStatus.PENDING
        state.phase_1_status = PhaseStatusDetail(status=PhaseStatus.PENDING)
        state.error_message = None
        state.error_phase = None
        await persistence.save(state)  # Should not raise

        loaded = await persistence.load(state.processing_run_id)
        assert loaded.pipeline_status == PipelineStatus.PENDING
        assert loaded.phase_1_status.status == PhaseStatus.PENDING

    @pytest.mark.asyncio
    async def test_full_lifecycle_succeeds(self, db_session: AsyncSession):
        """Full normal lifecycle PENDING → RUNNING → COMPLETED."""
        persistence = DirectStatePersistence(db_session)
        state = self._make_state(pipeline_status=PipelineStatus.PENDING)
        await persistence.save(state)

        state.pipeline_status = PipelineStatus.RUNNING
        state.phase_1_status = PhaseStatusDetail(status=PhaseStatus.RUNNING)
        await persistence.save(state)

        state.phase_1_status = PhaseStatusDetail(status=PhaseStatus.COMPLETED)
        state.phase_2_status = PhaseStatusDetail(status=PhaseStatus.RUNNING)
        await persistence.save(state)

        state.phase_2_status = PhaseStatusDetail(status=PhaseStatus.COMPLETED)
        state.phase_3_status = PhaseStatusDetail(status=PhaseStatus.RUNNING)
        await persistence.save(state)

        state.phase_3_status = PhaseStatusDetail(status=PhaseStatus.COMPLETED)
        state.pipeline_status = PipelineStatus.COMPLETED
        await persistence.save(state)

        loaded = await persistence.load(state.processing_run_id)
        assert loaded.pipeline_status == PipelineStatus.COMPLETED
        assert loaded.phase_1_status.status == PhaseStatus.COMPLETED


# ── SessionBoundStatePersistence guard tests (mocked) ─────────────────────


def _make_session_factory(session: AsyncSession):
    """Wrap a single session as an async_sessionmaker-compatible factory."""

    @asynccontextmanager
    async def _factory():
        yield session

    return _factory


class TestSessionBoundTransitionGuard:
    """Transition guard tests for SessionBoundStatePersistence."""

    def _make_state(
        self,
        pipeline_status: PipelineStatus = PipelineStatus.PENDING,
    ) -> PipelineGraphState:
        return PipelineGraphState(
            processing_run_id=str(uuid.uuid4()),
            source_document_id=str(uuid.uuid4()),
            mode=PipelineMode.FULL,
            source_type=SourceType.LOCAL,
            pipeline_status=pipeline_status,
        )

    @pytest.mark.asyncio
    async def test_invalid_transition_raises_with_session_bound(
        self, db_session: AsyncSession
    ):
        """SessionBoundStatePersistence enforces transition guards."""
        persistence = SessionBoundStatePersistence(_make_session_factory(db_session))

        # Start in COMPLETED
        state = self._make_state(pipeline_status=PipelineStatus.COMPLETED)
        await persistence.save(state)

        # Try to go COMPLETED → RUNNING (invalid)
        state.pipeline_status = PipelineStatus.RUNNING
        with pytest.raises(InvalidStateTransitionError):
            await persistence.save(state)

    @pytest.mark.asyncio
    async def test_valid_transition_succeeds_with_session_bound(
        self, db_session: AsyncSession
    ):
        """SessionBoundStatePersistence allows valid transitions."""
        persistence = SessionBoundStatePersistence(_make_session_factory(db_session))

        state = self._make_state(pipeline_status=PipelineStatus.PENDING)
        await persistence.save(state)

        state.pipeline_status = PipelineStatus.RUNNING
        await persistence.save(state)  # Should not raise

        loaded = await persistence.load(state.processing_run_id)
        assert loaded.pipeline_status == PipelineStatus.RUNNING

    @pytest.mark.asyncio
    async def test_recover_orphaned_runs_uses_valid_transition(
        self, db_session: AsyncSession
    ):
        """recover_orphaned_runs produces valid PENDING/RUNNING → FAILED transition."""
        from datetime import timedelta

        persistence = SessionBoundStatePersistence(_make_session_factory(db_session))

        state = self._make_state(pipeline_status=PipelineStatus.RUNNING)
        await persistence.save(
            state,
            owner_worker_id="worker-x",
            heartbeat_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )

        # This should succeed — RUNNING → FAILED is a valid transition
        count = await persistence.recover_orphaned_runs(heartbeat_timeout_seconds=60)
        assert count == 1

        loaded = await persistence.load(state.processing_run_id)
        assert loaded.pipeline_status == PipelineStatus.FAILED
