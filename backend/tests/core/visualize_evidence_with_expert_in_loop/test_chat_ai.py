"""Tests for chat AI reply generation."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.chat_service import (
    ChatService,
)


@pytest.mark.asyncio
class TestChatAI:
    """ChatService AI reply generation."""

    async def test_build_evidence_context(self, db_session: AsyncSession) -> None:
        """Builds context block from evidence card + entities + source span."""
        evidence_id = await self._create_evidence_with_bindings(db_session)
        service = ChatService(db_session)

        context = await service._build_evidence_context(
            canonical_evidence_id=evidence_id
        )

        assert "GLA" in context
        assert "Fabry disease" in context
        assert "Patient diagnosed with Fabry disease" in context

    async def test_build_evidence_context_missing_evidence_returns_empty(
        self, db_session: AsyncSession
    ) -> None:
        """Missing evidence IDs should not raise NoResultFound."""
        service = ChatService(db_session)

        context = await service._build_evidence_context(
            canonical_evidence_id=uuid.uuid4()
        )

        assert context == ""

    async def test_detect_intent_question(self, db_session: AsyncSession) -> None:
        """Pure question triggers AI reply."""
        service = ChatService(db_session)
        intent = service._detect_intent("What is the gene symbol?")
        assert intent == "question"

    async def test_detect_intent_action_request(self, db_session: AsyncSession) -> None:
        """Standalone action requests should not produce silent empty replies."""
        service = ChatService(db_session)
        intent = service._detect_intent("我想做文献的证据提取")
        assert intent == "question"

    async def test_detect_intent_greeting(self, db_session: AsyncSession) -> None:
        """Standalone greetings should receive assistant guidance."""
        service = ChatService(db_session)
        intent = service._detect_intent("hi")
        assert intent == "question"

    async def test_detect_intent_correction(self, db_session: AsyncSession) -> None:
        """Correction instruction triggers structured operation."""
        service = ChatService(db_session)
        intent = service._detect_intent("Change phenotype to Fabry 病")
        assert intent == "correction"

    async def test_detect_intent_note(self, db_session: AsyncSession) -> None:
        """Note does not trigger AI reply."""
        service = ChatService(db_session)
        intent = service._detect_intent("Need to verify this later")
        assert intent == "note"

    async def test_generate_reply_question(self, db_session: AsyncSession) -> None:
        """AI generates reply for questions."""
        evidence_id = await self._create_evidence_with_bindings(db_session)
        run_id = await self._create_test_run(db_session)
        provider = MagicMock()
        provider.generate = AsyncMock(return_value="The gene is GLA.")
        service = ChatService(db_session, chat_provider=provider)
        session = await service.create_session(processing_run_id=run_id, user_id=None)

        reply = await service.generate_reply(
            session_id=session.chat_session_id,
            user_message="What is the gene?",
            evidence_id=evidence_id,
        )

        assert reply is not None
        assert "GLA" in reply
        provider.generate.assert_awaited_once()
        kwargs = provider.generate.await_args.kwargs
        assert "Evidence Card" in kwargs["context"]
        assert "GLA" in kwargs["context"]

    async def test_generate_reply_note(self, db_session: AsyncSession) -> None:
        """Note does not generate AI reply."""
        run_id = await self._create_test_run(db_session)
        service = ChatService(db_session)
        session = await service.create_session(processing_run_id=run_id, user_id=None)

        reply = await service.generate_reply(
            session_id=session.chat_session_id,
            user_message="Need to verify this later",
            evidence_id=None,
        )

        assert reply is None

    async def _create_evidence_with_bindings(self, session: AsyncSession) -> uuid.UUID:
        """Helper: create evidence with entity bindings."""
        from src.dao.postgresql.models import (
            CanonicalEvidenceItem,
            EvidenceEntityBinding,
            NormalizedEntity,
            ProcessingRun,
            RunEvidenceItem,
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

        run_item = RunEvidenceItem(
            run_evidence_item_id=uuid.uuid4(),
            processing_run_id=run.processing_run_id,
            source_document_id=doc.source_document_id,
            track="original",
            field_id="A.test.1",
            status="found",
            value={},
            confidence=0.95,
            position_hash="pos1",
            text_hash="txt1",
            entity_scope_hash="scope1",
            source_span={
                "text_snippet": "Patient diagnosed with Fabry disease at age 30.",
                "start_offset": 0,
                "end_offset": 50,
                "page": 1,
            },
        )
        session.add(run_item)
        await session.flush()

        evidence = CanonicalEvidenceItem(
            canonical_evidence_id=uuid.uuid4(),
            source_document_id=doc.source_document_id,
            field_id="A.test.1",
            position_hash="abc",
            text_hash="def",
            entity_scope_hash="ghi",
            current_best_run_evidence_id=run_item.run_evidence_item_id,
            current_best_status="found",
            review_status="provisional",
            active_payload={
                "gene": "GLA",
                "phenotype": "Fabry disease",
                "summary": "Loss of function variant",
            },
        )
        session.add(evidence)
        await session.flush()

        entity = NormalizedEntity(
            entity_id=uuid.uuid4(),
            entity_type="gene",
            external_id="HGNC:4488",
            normalized_raw_text="GLA",
            display_name="GLA",
            standardization_status="standardized",
        )
        session.add(entity)
        await session.flush()

        binding = EvidenceEntityBinding(
            evidence_entity_binding_id=uuid.uuid4(),
            run_evidence_item_id=run_item.run_evidence_item_id,
            entity_id=entity.entity_id,
            entity_type="gene",
            role="subject",
        )
        session.add(binding)
        await session.flush()

        return evidence.canonical_evidence_id

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
