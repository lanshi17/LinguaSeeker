"""Phase 4 service factory — thin delegate between API and core services.

Phase 4 (evidence review, chat, audit, source linking) is interactive
request-response, not a LangGraph pipeline node.  This factory provides
the agents-layer boundary so API routes never import core services directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

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


class Phase4ServiceFactory:
    """Creates Phase 4 services with per-request sessions.

    Long-lived dependencies (cfg, providers) are injected at construction time.
    Short-lived dependencies (AsyncSession) are passed per-method-call.
    """

    def __init__(self, cfg: Settings):
        self._cfg = cfg
        self._delta_audit = DeltaAuditService()
        self._chat_provider = ChatLLMProvider()

    @property
    def chat_provider(self) -> ChatLLMProvider:
        return self._chat_provider

    def create_feedback_service(self, session: AsyncSession) -> FeedbackService:
        return FeedbackService(session)

    def create_chat_service(self, session: AsyncSession) -> ChatService:
        return ChatService(session=session, chat_provider=self._chat_provider)

    def create_source_linker(self, session: AsyncSession) -> SourceLinker:
        return SourceLinker(session)

    @property
    def delta_audit(self) -> DeltaAuditService:
        return self._delta_audit

    async def close(self) -> None:
        """Close long-lived resources (httpx client)."""
        await self._chat_provider.close()
