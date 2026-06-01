"""State persistence layer for pipeline orchestrator.

Two implementations:
- DirectStatePersistence: binds a single session (unit tests).
- SessionBoundStatePersistence: session-per-operation (production).
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.agents.contracts import PipelineGraphState
from src.dao.postgresql.models import PipelineRunState


class DirectStatePersistence:
    """Save/load PipelineGraphState with a fixed session.

    Intended for unit tests with short-lived sessions only.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, state: PipelineGraphState) -> None:
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
        record = await self._session.get(
            PipelineRunState, UUID(processing_run_id)
        )
        if record is None:
            return None
        return PipelineGraphState.model_validate(record.state_json)


class SessionBoundStatePersistence:
    """Save/load PipelineGraphState with session-per-operation.

    Creates a fresh session for each save()/load() call, avoiding
    stale-session bugs in long-lived contexts (production lifespan).
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def save(self, state: PipelineGraphState) -> None:
        async with self._session_factory() as session:
            state_json = state.model_dump(mode="json")
            stmt = (
                pg_insert(PipelineRunState)
                .values(
                    processing_run_id=UUID(state.processing_run_id),
                    source_document_id=UUID(state.source_document_id),
                    state_json=state_json,
                )
                .on_conflict_do_update(
                    index_elements=["processing_run_id"],
                    set_={"state_json": state_json},
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def load(self, processing_run_id: str) -> Optional[PipelineGraphState]:
        async with self._session_factory() as session:
            record = await session.get(
                PipelineRunState, UUID(processing_run_id)
            )
            if record is None:
                return None
            return PipelineGraphState.model_validate(record.state_json)
