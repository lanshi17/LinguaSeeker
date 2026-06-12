"""Tests for chat SSE streaming."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.chat_service import (
    ChatService,
)


@pytest.mark.asyncio
class TestChatSSE:
    """ChatService SSE streaming."""

    async def test_stream_reply_format(self, db_session: AsyncSession) -> None:
        """SSE stream yields properly formatted events."""
        run_id = await self._create_test_run(db_session)

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
            evidence_id=None,
        ):
            events.append(event)

        text_events = [e for e in events if e["type"] == "text"]
        assert len(text_events) == 3
        assert text_events[0]["content"] == "The "
        assert text_events[1]["content"] == "gene "
        assert text_events[2]["content"] == "is GLA."

        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1

    async def test_stream_reply_error_handling(self, db_session: AsyncSession) -> None:
        """SSE stream yields error event on failure."""
        run_id = await self._create_test_run(db_session)

        async def mock_stream_error(*args, **kwargs):
            raise RuntimeError("LLM timeout")
            yield  # noqa: unreachable  # makes it a generator

        provider = MagicMock()
        provider.stream = mock_stream_error
        service = ChatService(db_session, chat_provider=provider)
        session = await service.create_session(processing_run_id=run_id, user_id=None)

        events = []
        async for event in service.stream_reply(
            session_id=session.chat_session_id,
            user_message="What is the gene?",
            evidence_id=None,
        ):
            events.append(event)

        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "timeout" in error_events[0]["message"].lower()

    async def test_stream_reply_note_returns_empty(self, db_session: AsyncSession) -> None:
        """Note intent yields no events."""
        run_id = await self._create_test_run(db_session)
        service = ChatService(db_session)
        session = await service.create_session(processing_run_id=run_id, user_id=None)

        events = []
        async for event in service.stream_reply(
            session_id=session.chat_session_id,
            user_message="Need to verify this later",
            evidence_id=None,
        ):
            events.append(event)

        assert events == []

    async def test_stream_reply_persists_message(self, db_session: AsyncSession) -> None:
        """Streamed AI reply is persisted so it appears in message history."""
        run_id = await self._create_test_run(db_session)

        async def mock_stream(*args, **kwargs):
            yield "The gene is GLA."

        provider = MagicMock()
        provider.stream = mock_stream
        service = ChatService(db_session, chat_provider=provider)
        session = await service.create_session(processing_run_id=run_id, user_id=None)

        async for _ in service.stream_reply(
            session_id=session.chat_session_id,
            user_message="What is the gene?",
            evidence_id=None,
        ):
            pass

        messages = await service.list_messages(session_id=session.chat_session_id)
        assistant_msgs = [m for m in messages if m.role == "assistant"]
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0].content == "The gene is GLA."

    async def test_stream_reply_error_no_persistence(self, db_session: AsyncSession) -> None:
        """Errored stream does not persist partial reply."""
        run_id = await self._create_test_run(db_session)

        async def mock_stream_error(*args, **kwargs):
            raise RuntimeError("LLM timeout")
            yield  # noqa: unreachable  # makes it a generator

        provider = MagicMock()
        provider.stream = mock_stream_error
        service = ChatService(db_session, chat_provider=provider)
        session = await service.create_session(processing_run_id=run_id, user_id=None)

        async for _ in service.stream_reply(
            session_id=session.chat_session_id,
            user_message="What is the gene?",
            evidence_id=None,
        ):
            pass

        messages = await service.list_messages(session_id=session.chat_session_id)
        assistant_msgs = [m for m in messages if m.role == "assistant"]
        assert len(assistant_msgs) == 0

    async def _create_test_run(self, session: AsyncSession) -> uuid.UUID:
        """Helper: create a test processing run."""
        from src.dao.postgresql.models import ProcessingRun, SourceDocument

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
        return run.processing_run_id
