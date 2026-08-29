"""Phase 5 service factory — thin delegate between API and core services.

Phase 5 (evidence review, chat, audit, source linking) is interactive
request-response, not a LangGraph pipeline node.  This factory provides
the agents-layer boundary so API routes never import core services directly.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.visualize_evidence_with_expert_in_loop.chat_service import ChatService
from src.core.visualize_evidence_with_expert_in_loop.delta_audit_service import (
    DeltaAuditService,
)
from src.core.visualize_evidence_with_expert_in_loop.feedback_service import (
    FeedbackService,
)
from src.core.visualize_evidence_with_expert_in_loop.providers import (
    ChatLLMProvider,
)
from src.core.visualize_evidence_with_expert_in_loop.source_linker import SourceLinker

if TYPE_CHECKING:
    from src.core.config import Settings


class Phase5ServiceFactory:
    """Creates Phase 5 services with per-request sessions.

    Long-lived dependencies (cfg, providers) are injected at construction time.
    Short-lived dependencies (AsyncSession) are passed per-method-call.
    """

    def __init__(
        self,
        cfg: Settings,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ):
        self._cfg = cfg
        self._session_factory = session_factory
        self._delta_audit = DeltaAuditService()
        self._chat_provider = ChatLLMProvider()

    @property
    def chat_provider(self) -> ChatLLMProvider:
        return self._chat_provider

    def create_feedback_service(self, session: AsyncSession) -> FeedbackService:
        return FeedbackService(session)

    def create_chat_service(self, session: AsyncSession) -> ChatService:
        return ChatService(session=session, chat_provider=self._chat_provider)

    def schedule_session_title_generation(
        self,
        *,
        session_id: UUID,
        user_message: str,
    ) -> None:
        """Generate a chat title in a separate DB session without blocking chat."""
        if self._session_factory is None:
            logger.warning("Chat session title generation skipped: session factory is not configured")
            return

        task = asyncio.create_task(
            self._generate_session_title_in_background(
                session_id=session_id,
                user_message=user_message,
            )
        )
        task.add_done_callback(self._log_background_title_failure)

    async def _generate_session_title_in_background(
        self,
        *,
        session_id: UUID,
        user_message: str,
    ) -> None:
        """Generate and persist a chat title after the message transaction commits."""
        if self._session_factory is None:
            return

        async with self._session_factory() as session:
            service = self.create_chat_service(session)
            await service.generate_session_title(
                session_id=session_id,
                user_message=user_message,
            )
            await session.commit()

    @staticmethod
    def _log_background_title_failure(task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            logger.debug("Chat session title generation task was cancelled")
        except Exception as exc:
            logger.warning("Chat session title generation background task failed: {}", exc)

    def create_source_linker(self, session: AsyncSession) -> SourceLinker:
        return SourceLinker(session)

    @property
    def delta_audit(self) -> DeltaAuditService:
        return self._delta_audit

    async def close(self) -> None:
        """Close long-lived resources (httpx client)."""
        await self._chat_provider.close()
