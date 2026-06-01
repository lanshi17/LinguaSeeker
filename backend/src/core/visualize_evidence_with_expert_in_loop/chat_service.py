"""Chat service for evidence review conversations."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    ChatMessageResponse,
    ChatSessionResponse,
)
from src.dao.postgresql.models import (
    CanonicalEvidenceItem,
    ChatMessage,
    ChatSession,
    EvidenceEntityBinding,
    NormalizedEntity,
    RunEvidenceItem,
)

if TYPE_CHECKING:
    from src.core.visualize_evidence_with_expert_in_loop.providers import (
        ReasoningLLMProvider,
    )


class ChatService:
    """Manage chat sessions and messages for evidence review."""

    def __init__(
        self,
        session: AsyncSession,
        reasoning_provider: ReasoningLLMProvider | None = None,
    ):
        self._session = session
        self._reasoning_provider = reasoning_provider

    async def create_session(
        self,
        *,
        processing_run_id: UUID,
        user_id: UUID | None = None,
    ) -> ChatSessionResponse:
        """Create a new chat session bound to a processing run."""
        session = ChatSession(
            processing_run_id=processing_run_id,
            user_id=user_id,
        )
        self._session.add(session)
        await self._session.flush()

        return ChatSessionResponse(
            chat_session_id=session.chat_session_id,
            processing_run_id=session.processing_run_id,
            user_id=session.user_id,
            created_at=session.created_at,
            message_count=0,
        )

    async def append_message(
        self,
        *,
        session_id: UUID,
        role: str,
        content: str,
        evidence_id: UUID | None = None,
        entity_id: UUID | None = None,
    ) -> ChatMessageResponse:
        """Append a message to a chat session."""
        message = ChatMessage(
            chat_session_id=session_id,
            role=role,
            content=content,
            evidence_id=evidence_id,
            entity_id=entity_id,
        )
        self._session.add(message)
        await self._session.flush()

        return ChatMessageResponse(
            message_id=message.message_id,
            chat_session_id=message.chat_session_id,
            role=message.role,  # type: ignore[arg-type]
            content=message.content,
            evidence_id=message.evidence_id,
            entity_id=message.entity_id,
            created_at=message.created_at,
        )

    async def list_messages(
        self,
        *,
        session_id: UUID,
        limit: int = 100,
    ) -> list[ChatMessageResponse]:
        """List messages in a session, ordered chronologically."""
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.chat_session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        messages = result.scalars().all()

        return [
            ChatMessageResponse(
                message_id=msg.message_id,
                chat_session_id=msg.chat_session_id,
                role=msg.role,  # type: ignore[arg-type]
                content=msg.content,
                evidence_id=msg.evidence_id,
                entity_id=msg.entity_id,
                created_at=msg.created_at,
            )
            for msg in messages
        ]

    async def list_sessions(
        self,
        *,
        processing_run_id: UUID,
    ) -> list[ChatSessionResponse]:
        """List all chat sessions for a processing run."""
        count_subq = (
            select(
                ChatMessage.chat_session_id,
                func.count().label("msg_count"),
            )
            .group_by(ChatMessage.chat_session_id)
            .subquery()
        )

        stmt = (
            select(ChatSession, func.coalesce(count_subq.c.msg_count, 0))
            .outerjoin(
                count_subq,
                ChatSession.chat_session_id == count_subq.c.chat_session_id,
            )
            .where(ChatSession.processing_run_id == processing_run_id)
            .order_by(ChatSession.created_at.desc())
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        return [
            ChatSessionResponse(
                chat_session_id=session.chat_session_id,
                processing_run_id=session.processing_run_id,
                user_id=session.user_id,
                created_at=session.created_at,
                message_count=msg_count,
            )
            for session, msg_count in rows
        ]

    async def _build_evidence_context(
        self,
        *,
        canonical_evidence_id: UUID,
    ) -> str:
        """Build evidence context block for LLM (~4000 tokens).

        Includes:
        - Current evidence card (active_payload)
        - Associated entities (via bindings)
        - Source span snippet
        """
        stmt = select(CanonicalEvidenceItem).where(
            CanonicalEvidenceItem.canonical_evidence_id == canonical_evidence_id
        )
        result = await self._session.execute(stmt)
        evidence = result.scalar_one()

        payload = evidence.active_payload
        context_parts = [
            "**Evidence Card**",
            f"Gene: {payload.get('gene', 'N/A')}",
            f"Variant: {payload.get('variant', 'N/A')}",
            f"Phenotype: {payload.get('phenotype', 'N/A')}",
            f"Disease: {payload.get('disease', 'N/A')}",
            f"Classification: {payload.get('classification', 'N/A')}",
            f"Evidence Strength: {payload.get('evidence_strength', 'N/A')}",
            f"Summary: {payload.get('summary', 'N/A')}",
        ]

        stmt = (
            select(NormalizedEntity)
            .join(
                EvidenceEntityBinding,
                EvidenceEntityBinding.entity_id == NormalizedEntity.entity_id,
            )
            .where(
                EvidenceEntityBinding.run_evidence_item_id.in_(
                    select(RunEvidenceItem.run_evidence_item_id).where(
                        RunEvidenceItem.canonical_evidence_id == canonical_evidence_id
                    )
                )
            )
        )
        result = await self._session.execute(stmt)
        entities = result.scalars().all()

        if entities:
            context_parts.append("\n**Associated Entities**")
            for entity in entities[:5]:
                context_parts.append(
                    f"- {entity.entity_type}: {entity.display_name} ({entity.external_id})"
                )

        stmt = (
            select(RunEvidenceItem)
            .where(
                RunEvidenceItem.canonical_evidence_id == canonical_evidence_id,
                RunEvidenceItem.track == "original",
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        run_item = result.scalar_one_or_none()

        if run_item and run_item.source_span:
            snippet = run_item.source_span.get("text_snippet", "")[:300]
            if snippet:
                context_parts.append(f"\n**Source Text**\n{snippet}")

        return "\n".join(context_parts)

    def _detect_intent(self, message: str) -> str:
        """Detect user intent: question, correction, or note.

        Priority: question > correction > note.
        Ambiguous messages (e.g. "change X to Y?") default to question
        as the less destructive intent.

        Returns:
            "question" | "correction" | "note"
        """
        msg_lower = message.lower()

        # Check question patterns first to avoid false positives on
        # messages like "What should I change?" which contain "change"
        question_patterns = [
            r"\?",
            r"\bwhat\b",
            r"\bwhy\b",
            r"\bhow\b",
            r"\bwhich\b",
            r"\b什么\b",
            r"\b为什么\b",
            r"\b如何\b",
        ]
        if any(re.search(p, msg_lower) for p in question_patterns):
            return "question"

        correction_patterns = [
            r"\bchange\b.*\bto\b",
            r"\bupdate\b.*\bto\b",
            r"\bcorrect\b.*\bto\b",
            r"\b修改\b.*\b为\b",
            r"\b改为\b",
        ]
        if any(re.search(p, msg_lower) for p in correction_patterns):
            return "correction"

        return "note"

    async def generate_reply(
        self,
        *,
        session_id: UUID,
        user_message: str,
        evidence_id: UUID | None = None,
    ) -> str | None:
        """Generate AI reply based on intent and evidence context.

        Returns:
            Reply text for questions/corrections, None for notes.
        """
        intent = self._detect_intent(user_message)

        if intent == "note":
            return None

        if intent == "correction" and evidence_id:
            return f"Correction applied to evidence {evidence_id}."

        context = ""
        if evidence_id:
            context = await self._build_evidence_context(
                canonical_evidence_id=evidence_id
            )

        system_prompt = (
            "You are a clinical genetics assistant. Answer questions about "
            "evidence cards using the provided context. Be precise and cite "
            "specific fields from the evidence card."
        )

        provider = self._reasoning_provider
        if provider is None:
            from src.core.visualize_evidence_with_expert_in_loop.providers import (
                ReasoningLLMProvider,
            )
            provider = ReasoningLLMProvider()

        reply = await provider.generate(
            system_prompt=system_prompt,
            user_message=user_message,
            context=context,
        )

        return reply

    async def stream_reply(
        self,
        *,
        session_id: UUID,
        user_message: str,
        evidence_id: UUID | None = None,
    ):
        """Stream AI reply as SSE events.

        Yields:
            {"type": "text", "content": "..."} for each chunk
            {"type": "done"} on completion
            {"type": "error", "message": "..."} on failure
        """
        intent = self._detect_intent(user_message)

        if intent == "note":
            return

        if intent == "correction":
            yield {
                "type": "text",
                "content": f"Correction applied to evidence {evidence_id}.",
            }
            yield {"type": "done"}
            return

        context = ""
        if evidence_id:
            context = await self._build_evidence_context(
                canonical_evidence_id=evidence_id
            )

        system_prompt = (
            "You are a clinical genetics assistant. Answer questions about "
            "evidence cards using the provided context. Be precise and cite "
            "specific fields from the evidence card."
        )

        provider = self._reasoning_provider
        if provider is None:
            from src.core.visualize_evidence_with_expert_in_loop.providers import (
                ReasoningLLMProvider,
            )
            provider = ReasoningLLMProvider()

        buffered: list[str] = []
        try:
            async for chunk in provider.stream(
                system_prompt=system_prompt,
                user_message=user_message,
                context=context,
            ):
                buffered.append(chunk)
                yield {"type": "text", "content": chunk}
            yield {"type": "done"}
        except Exception as e:
            yield {"type": "error", "message": str(e)}
            return

        # Persist complete streamed reply so it appears in message history
        complete_reply = "".join(buffered)
        if complete_reply:
            await self.append_message(
                session_id=session_id,
                role="assistant",
                content=complete_reply,
                evidence_id=evidence_id,
            )
