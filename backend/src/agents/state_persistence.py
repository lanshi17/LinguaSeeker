"""State persistence layer for pipeline orchestrator."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.contracts import PipelineGraphState
from src.dao.models import PipelineRunState


class StatePersistenceService:
    """Save and load PipelineGraphState to/from PostgreSQL.

    Called after each phase completes for crash recovery.

    WARNING: This class holds a single session reference. In production, use
    SessionBoundPersistence (state_persistence_factory.py) instead, which
    creates a fresh session per operation to avoid stale-session bugs.
    This class is intended for unit tests with short-lived sessions only.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, state: PipelineGraphState) -> None:
        """Save or update pipeline state to database (checkpoint)."""
        existing = await self._session.get(
            PipelineRunState, UUID(state.processing_run_id)
        )

        state_json = state.model_dump(mode="json")

        if existing:
            existing.state_json = state_json
        else:
            new_record = PipelineRunState(
                processing_run_id=UUID(state.processing_run_id),
                source_document_id=UUID(state.source_document_id),
                state_json=state_json,
            )
            self._session.add(new_record)

        await self._session.commit()

    async def load(self, processing_run_id: str) -> Optional[PipelineGraphState]:
        """Load pipeline state from database for crash recovery."""
        record = await self._session.get(
            PipelineRunState, UUID(processing_run_id)
        )
        if record is None:
            return None

        return PipelineGraphState.model_validate(record.state_json)
