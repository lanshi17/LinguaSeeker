"""Tests for chat SSE streaming."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.chat_service import (
    ChatService,
)
from src.core.visualize_evidence_with_expert_in_loop.contracts import ChatAction


@pytest.mark.asyncio
class TestChatSSEEvidenceContext:
    async def test_stream_reply_format_with_evidence_context(self, db_session: AsyncSession) -> None:
        run_id, evidence_id = await self._create_test_run_with_evidence(db_session)

        async def mock_stream(*args, **kwargs):
            yield "The "
            yield "gene "
            yield "is GLA."

        provider = MagicMock()
        provider.stream = mock_stream
        service = ChatService(db_session, chat_provider=provider)
        session = await service.create_session(processing_run_id=run_id, user_id=None)

        events = []
        async for event in service.stream_reply(
            session_id=session.chat_session_id,
            user_message="What is the gene?",
            evidence_id=evidence_id,
        ):
            events.append(event)

        text_events = [e for e in events if e["type"] == "text"]
        assert len(text_events) == 3
        assert "".join(e["content"] for e in text_events) == "The gene is GLA."

        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1

    async def test_stream_reply_error_handling(self, db_session: AsyncSession) -> None:
        run_id, evidence_id = await self._create_test_run_with_evidence(db_session)

        async def mock_stream_error(*args, **kwargs):
            raise RuntimeError("LLM timeout")
            yield  # noqa: unreachable -- forces async-generator typing

        provider = MagicMock()
        provider.stream = mock_stream_error
        service = ChatService(db_session, chat_provider=provider)
        session = await service.create_session(processing_run_id=run_id, user_id=None)

        events = []
        async for event in service.stream_reply(
            session_id=session.chat_session_id,
            user_message="What is the gene?",
            evidence_id=evidence_id,
        ):
            events.append(event)

        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "timeout" in error_events[0]["message"].lower()

    async def test_stream_reply_persists_message(self, db_session: AsyncSession) -> None:
        run_id, evidence_id = await self._create_test_run_with_evidence(db_session)

        async def mock_stream(*args, **kwargs):
            yield "The gene is GLA."

        provider = MagicMock()
        provider.stream = mock_stream
        service = ChatService(db_session, chat_provider=provider)
        session = await service.create_session(processing_run_id=run_id, user_id=None)

        async for _ in service.stream_reply(
            session_id=session.chat_session_id,
            user_message="What is the gene?",
            evidence_id=evidence_id,
        ):
            pass

        messages = await service.list_messages(session_id=session.chat_session_id)
        assistant_msgs = [m for m in messages if m.role == "assistant"]
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0].content == "The gene is GLA."

    async def _create_test_run_with_evidence(self, session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
        from src.dao.postgresql.models import (
            CanonicalEvidenceItem,
            ProcessingRun,
            SourceDocument,
        )

        doc = SourceDocument(source_document_id=uuid.uuid4(), raw_metadata={})
        session.add(doc)
        await session.flush()

        run = ProcessingRun(
            processing_run_id=uuid.uuid4(),
            source_document_id=doc.source_document_id,
            run_status="completed",
        )
        session.add(run)
        await session.flush()

        evidence = CanonicalEvidenceItem(
            canonical_evidence_id=uuid.uuid4(),
            source_document_id=doc.source_document_id,
            field_id="A.gene_symbol",
            position_hash="ph",
            text_hash="th",
            entity_scope_hash="esh",
            current_best_status="found",
            active_payload={"value": "GLA", "group_id": "g1"},
            review_status="provisional",
            current_best_confidence=0.9,
        )
        session.add(evidence)
        await session.flush()

        return run.processing_run_id, evidence.canonical_evidence_id


@pytest.mark.asyncio
class TestChatRouterEnvelope:
    async def test_emits_text_then_done_when_action_is_null(
        self, db_session: AsyncSession
    ) -> None:
        provider = MagicMock()
        provider.route_intent = AsyncMock(
            return_value=("Could you share the PMID or PDF?", None)
        )
        service = ChatService(db_session, chat_provider=provider)
        session = await service.create_session(processing_run_id=None, user_id=None)

        events = []
        async for event in service.stream_reply(
            session_id=session.chat_session_id,
            user_message="I want to extract evidence",
            evidence_id=None,
        ):
            events.append(event)

        types = [e["type"] for e in events]
        assert types == ["text", "done"]
        assert events[0]["content"] == "Could you share the PMID or PDF?"

        provider.route_intent.assert_awaited_once()

    async def test_emits_action_event_when_slots_complete(
        self, db_session: AsyncSession
    ) -> None:
        provider = MagicMock()
        provider.route_intent = AsyncMock(
            return_value=(
                "Starting the pipeline now.",
                ChatAction(
                    intent="start-pipeline",
                    slots={"source_type": "online", "query": "PMID:34521984"},
                ),
            )
        )
        service = ChatService(db_session, chat_provider=provider)
        session = await service.create_session(processing_run_id=None, user_id=None)

        events = []
        async for event in service.stream_reply(
            session_id=session.chat_session_id,
            user_message="Run pipeline on PMID:34521984",
            evidence_id=None,
        ):
            events.append(event)

        types = [e["type"] for e in events]
        assert types == ["text", "action", "done"], events

        action_event = events[1]
        assert action_event["intent"] == "start-pipeline"
        assert action_event["slots"]["query"] == "PMID:34521984"

    async def test_persists_action_alongside_message(
        self, db_session: AsyncSession
    ) -> None:
        provider = MagicMock()
        provider.route_intent = AsyncMock(
            return_value=(
                "Opening the upload form.",
                ChatAction(intent="upload-pdf", slots={}),
            )
        )
        service = ChatService(db_session, chat_provider=provider)
        session = await service.create_session(processing_run_id=None, user_id=None)

        async for _ in service.stream_reply(
            session_id=session.chat_session_id,
            user_message="Upload a PDF",
            evidence_id=None,
        ):
            pass

        messages = await service.list_messages(session_id=session.chat_session_id)
        assistant_msgs = [m for m in messages if m.role == "assistant"]
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0].action is not None
        assert assistant_msgs[0].action.intent == "upload-pdf"
