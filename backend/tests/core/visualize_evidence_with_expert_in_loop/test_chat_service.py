"""Tests for chat service."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.chat_service import (
    ChatService,
)


def test_detect_intent_uses_module_level_compiled_patterns():
    """Regex patterns should be compiled at module level, not per call."""
    import src.core.visualize_evidence_with_expert_in_loop.chat_service as mod
    assert hasattr(mod, "_QUESTION_PATTERNS")
    assert hasattr(mod, "_CORRECTION_PATTERNS")
    assert all(hasattr(p, "search") for p in mod._QUESTION_PATTERNS)


@pytest.mark.asyncio
class TestChatService:
    """ChatService manages sessions and messages."""

    async def test_create_session(self, db_session: AsyncSession) -> None:
        """Creates a chat session bound to a processing run."""
        run_id = await self._create_test_run(db_session)
        service = ChatService(db_session)

        session = await service.create_session(processing_run_id=run_id, user_id=None)

        assert session.processing_run_id == run_id
        assert session.message_count == 0

    async def test_create_standalone_session(self, db_session: AsyncSession) -> None:
        """Creates a chat session that is not bound to a pipeline run."""
        service = ChatService(db_session)

        session = await service.create_session(processing_run_id=None, user_id=None)

        assert session.processing_run_id is None
        assert session.message_count == 0

    async def test_append_message(self, db_session: AsyncSession) -> None:
        """Appends a message to a session."""
        run_id = await self._create_test_run(db_session)
        service = ChatService(db_session)
        session = await service.create_session(processing_run_id=run_id, user_id=None)

        msg = await service.append_message(
            session_id=session.chat_session_id,
            role="user",
            content="What is the gene?",
            evidence_id=None,
            entity_id=None,
        )

        assert msg.role == "user"
        assert msg.content == "What is the gene?"

    async def test_list_messages_ordered(self, db_session: AsyncSession) -> None:
        """Lists messages in chronological order."""
        run_id = await self._create_test_run(db_session)
        service = ChatService(db_session)
        session = await service.create_session(processing_run_id=run_id, user_id=None)

        await service.append_message(
            session_id=session.chat_session_id,
            role="user",
            content="Q1",
            evidence_id=None,
            entity_id=None,
        )
        await service.append_message(
            session_id=session.chat_session_id,
            role="assistant",
            content="A1",
            evidence_id=None,
            entity_id=None,
        )
        await service.append_message(
            session_id=session.chat_session_id,
            role="user",
            content="Q2",
            evidence_id=None,
            entity_id=None,
        )

        messages = await service.list_messages(session_id=session.chat_session_id)

        assert len(messages) == 3
        assert messages[0].role == "user"
        assert messages[0].content == "Q1"
        assert messages[1].role == "assistant"
        assert messages[2].content == "Q2"

    async def test_list_sessions_by_run(self, db_session: AsyncSession) -> None:
        """Lists all sessions for a processing run."""
        run_id = await self._create_test_run(db_session)
        service = ChatService(db_session)

        await service.create_session(processing_run_id=run_id, user_id=None)
        await service.create_session(processing_run_id=run_id, user_id=None)

        sessions = await service.list_sessions(processing_run_id=run_id)

        assert len(sessions) == 2

    async def test_list_messages_with_limit(self, db_session: AsyncSession) -> None:
        """Limits the number of returned messages."""
        run_id = await self._create_test_run(db_session)
        service = ChatService(db_session)
        session = await service.create_session(processing_run_id=run_id, user_id=None)

        for i in range(10):
            await service.append_message(
                session_id=session.chat_session_id,
                role="user",
                content=f"Message {i}",
                evidence_id=None,
                entity_id=None,
            )

        messages = await service.list_messages(
            session_id=session.chat_session_id, limit=5
        )

        assert len(messages) == 5

    async def test_generate_reply_without_evidence_uses_general_chat_prompt(
        self, db_session: AsyncSession
    ) -> None:
        """Standalone chat uses a general assistant prompt without evidence context."""
        provider = MagicMock()
        provider.generate = AsyncMock(return_value="I can help start a pipeline.")
        service = ChatService(db_session, reasoning_provider=provider)
        session = await service.create_session(processing_run_id=None, user_id=None)

        reply = await service.generate_reply(
            session_id=session.chat_session_id,
            user_message="What can you do?",
            evidence_id=None,
        )

        assert reply == "I can help start a pipeline."
        kwargs = provider.generate.await_args.kwargs
        assert "ACMG Lingua" in kwargs["system_prompt"]
        assert "pipeline" in kwargs["system_prompt"].lower()

    async def test_build_evidence_context_uses_current_best_run_id(
        self, db_session: AsyncSession
    ) -> None:
        """_build_evidence_context resolves canonical -> current_best_run_evidence_id -> entity + source."""
        from src.dao.postgresql.models import (
            CanonicalEvidenceItem,
            NormalizedEntity,
            EvidenceEntityBinding,
            RunEvidenceItem,
            SourceDocument,
            ProcessingRun,
        )

        # Seed prerequisite rows
        doc = SourceDocument(source_document_id=uuid.uuid4(), raw_metadata={})
        db_session.add(doc)
        await db_session.flush()

        run = ProcessingRun(
            processing_run_id=uuid.uuid4(),
            source_document_id=doc.source_document_id,
            run_status="completed",
        )
        db_session.add(run)
        await db_session.flush()

        run_item = RunEvidenceItem(
            run_evidence_item_id=uuid.uuid4(),
            processing_run_id=run.processing_run_id,
            source_document_id=doc.source_document_id,
            track="original",
            field_id="A.gene_symbol",
            status="found",
            value={"value": "BRCA1"},
            confidence=0.95,
            position_hash="h1",
            text_hash="h2",
            source_span={"text_snippet": "BRCA1 variant detected in exon 11"},
            entity_scope_hash="h3",
        )
        db_session.add(run_item)
        await db_session.flush()

        canonical = CanonicalEvidenceItem(
            canonical_evidence_id=uuid.uuid4(),
            source_document_id=doc.source_document_id,
            field_id="A.gene_symbol",
            position_hash="h1",
            text_hash="h2",
            entity_scope_hash="h3",
            current_best_run_evidence_id=run_item.run_evidence_item_id,
            current_best_status="found",
            current_best_confidence=0.95,
            active_payload={
                "gene": "BRCA1",
                "variant": "c.5266dupC",
                "phenotype": "Breast cancer",
                "disease": "Hereditary Breast and Ovarian Cancer",
                "classification": "Pathogenic",
                "evidence_strength": "Very Strong",
                "summary": "BRCA1 frameshift variant",
            },
        )
        db_session.add(canonical)
        await db_session.flush()

        entity = NormalizedEntity(
            entity_id=uuid.uuid4(),
            entity_type="gene",
            display_name="BRCA1 DNA repair associated",
            external_id="HGNC:1100",
            normalized_raw_text="BRCA1",
        )
        db_session.add(entity)
        await db_session.flush()

        binding = EvidenceEntityBinding(
            evidence_entity_binding_id=uuid.uuid4(),
            run_evidence_item_id=run_item.run_evidence_item_id,
            entity_id=entity.entity_id,
            entity_type="gene",
            role="subject",
            binding_rank=1,
            raw_entity_text="BRCA1",
        )
        db_session.add(binding)
        await db_session.flush()

        # Act
        service = ChatService(db_session)
        context = await service._build_evidence_context(
            canonical_evidence_id=canonical.canonical_evidence_id,
        )

        # Assert
        assert isinstance(context, str)
        assert "BRCA1" in context
        assert "BRCA1 variant detected" in context

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
