"""Session-bound state persistence using session-per-request pattern."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.agents.contracts import PipelineGraphState
from src.dao.postgresql.models import PipelineRunState


class SessionBoundPersistence:
    """StatePersistenceService that creates a fresh session per operation.

    Avoids holding session references across requests (C1 fix: session lifecycle).
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def save(self, state: PipelineGraphState) -> None:
        """Save or update pipeline state with a fresh session."""
        async with self._session_factory() as session:
            existing = await session.get(
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
                session.add(new_record)

            await session.commit()

    async def load(self, processing_run_id: str) -> Optional[PipelineGraphState]:
        """Load pipeline state with a fresh session."""
        async with self._session_factory() as session:
            record = await session.get(
                PipelineRunState, UUID(processing_run_id)
            )
            if record is None:
                return None

            return PipelineGraphState.model_validate(record.state_json)
