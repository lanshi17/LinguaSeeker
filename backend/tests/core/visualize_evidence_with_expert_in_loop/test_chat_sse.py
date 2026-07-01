"""Tests for chat SSE streaming."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.chat_service import (
    ChatService,
)
from src.core.visualize_evidence_with_expert_in_loop.contracts import ChatAction
from src.core.visualize_evidence_with_expert_in_loop.providers import (
    _parse_delimited,
    _try_parse_action,
)


class TestParseDelimited:
    def test_text_only_returns_reply_and_none_action(self) -> None:
        reply, action = _parse_delimited("Hello, how can I help?")
        assert reply == "Hello, how can I help?"
        assert action is None

    def test_delimiter_with_action_json(self) -> None:
        raw = (
            "Found 3 results.\n"
            '<<<ACTION>>>\n{"intent": "search-evidence", "slots": {"gene": "GLA"}}'
        )
        reply, action = _parse_delimited(raw)
        assert reply == "Found 3 results."
        assert action is not None
        assert action.intent == "search-evidence"
        assert action.slots["gene"] == "GLA"

    def test_delimiter_without_action_json(self) -> None:
        reply, action = _parse_delimited("Some text<<<ACTION>>>")
        assert reply == "Some text"
        assert action is None

    def test_empty_string(self) -> None:
        reply, action = _parse_delimited("")
        assert reply == ""
        assert action is None


class TestTryParseAction:
    def test_valid_action_json(self) -> None:
        raw = '{"intent": "search-evidence", "slots": {"gene": "GLA"}}'
        action = _try_parse_action(raw)
        assert action is not None
        assert action.intent == "search-evidence"

    def test_invalid_json_returns_none(self) -> None:
        assert _try_parse_action("not json") is None

    def test_non_dict_json_returns_none(self) -> None:
        assert _try_parse_action('"just a string"') is None

    def test_empty_string_returns_none(self) -> None:
        assert _try_parse_action("") is None

    def test_invalid_action_fields_returns_none(self) -> None:
        assert _try_parse_action('{"foo": "bar"}') is None


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
            if False:  # pragma: no cover
                yield  # forces async-generator typing
            raise RuntimeError("LLM timeout")

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
        async def mock_stream(*args, **kwargs):
            yield ("Could you share the PMID or PDF?", None)

        provider = MagicMock()
        provider.route_intent_stream = mock_stream
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

    async def test_emits_action_event_when_slots_complete(
        self, db_session: AsyncSession
    ) -> None:
        async def mock_stream(*args, **kwargs):
            yield (
                "Starting the pipeline now.",
                ChatAction(
                    intent="start-pipeline",
                    slots={"source_type": "online", "query": "PMID:34521984"},
                ),
            )

        provider = MagicMock()
        provider.route_intent_stream = mock_stream
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
        async def mock_stream(*args, **kwargs):
            yield (
                "Opening the upload form.",
                ChatAction(intent="upload-pdf", slots={}),
            )

        provider = MagicMock()
        provider.route_intent_stream = mock_stream
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

    async def test_increments_text_chunks_before_action(
        self, db_session: AsyncSession
    ) -> None:
        """Text chunks are forwarded as SSE events before the final tuple."""

        async def mock_stream(*args, **kwargs):
            yield "Sure, "
            yield "I can "
            yield "help with that."
            yield (
                "",
                ChatAction(
                    intent="search-evidence",
                    slots={"gene": "GLA"},
                ),
            )

        provider = MagicMock()
        provider.route_intent_stream = mock_stream
        service = ChatService(db_session, chat_provider=provider)
        session = await service.create_session(processing_run_id=None, user_id=None)

        events = []
        async for event in service.stream_reply(
            session_id=session.chat_session_id,
            user_message="Search for GLA",
            evidence_id=None,
        ):
            events.append(event)

        text_events = [e for e in events if e["type"] == "text"]
        assert len(text_events) == 3
        assert "".join(e["content"] for e in text_events) == "Sure, I can help with that."

        types = [e["type"] for e in events]
        assert types == ["text", "text", "text", "action", "done"]

    async def test_increments_text_then_action_persists_full_reply(
        self, db_session: AsyncSession
    ) -> None:
        """The persisted message contains the full accumulated reply text."""

        async def mock_stream(*args, **kwargs):
            yield "Searching for "
            yield "BRCA1 evidence."
            yield (
                "",
                ChatAction(intent="search-evidence", slots={"gene": "BRCA1"}),
            )

        provider = MagicMock()
        provider.route_intent_stream = mock_stream
        service = ChatService(db_session, chat_provider=provider)
        session = await service.create_session(processing_run_id=None, user_id=None)

        async for _ in service.stream_reply(
            session_id=session.chat_session_id,
            user_message="Find BRCA1 evidence",
            evidence_id=None,
        ):
            pass

        messages = await service.list_messages(session_id=session.chat_session_id)
        assistant_msgs = [m for m in messages if m.role == "assistant"]
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0].content == "Searching for BRCA1 evidence."
        assert assistant_msgs[0].action is not None
        assert assistant_msgs[0].action.intent == "search-evidence"
