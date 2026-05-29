"""Tests for source linker service."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.source_linker import (
    SourceLinker,
)


@pytest.mark.asyncio
class TestSourceLinker:
    """SourceLinker retrieves source spans for evidence traceability."""

    async def test_get_single_track_span(self, db_session: AsyncSession) -> None:
        """Retrieves source span for one track."""
        evidence_id = await self._create_test_evidence_with_span(db_session)

        linker = SourceLinker(db_session)
        span = await linker.get_track_span(
            canonical_evidence_id=evidence_id,
            track="original",
        )

        assert span is not None
        assert span.track == "original"
        assert span.highlight_start == 100
        assert span.highlight_end == 150
        assert "Fabry disease" in span.block_text

    async def test_get_bilingual_span(self, db_session: AsyncSession) -> None:
        """Retrieves both original and translated spans."""
        evidence_id = await self._create_test_evidence_with_span(db_session)

        linker = SourceLinker(db_session)
        bilingual = await linker.get_bilingual_span(
            canonical_evidence_id=evidence_id
        )

        assert bilingual.canonical_evidence_id == evidence_id
        assert bilingual.original_track is not None
        assert bilingual.translated_track is not None
        assert bilingual.original_track.track == "original"
        assert bilingual.translated_track.track == "translated"

    async def test_missing_track_returns_none(self, db_session: AsyncSession) -> None:
        """Missing track returns None in TrackSpan."""
        evidence_id = await self._create_test_evidence_with_span(
            db_session, include_translated=False
        )

        linker = SourceLinker(db_session)
        bilingual = await linker.get_bilingual_span(
            canonical_evidence_id=evidence_id
        )

        assert bilingual.original_track is not None
        assert bilingual.translated_track is None

    async def test_no_spans_returns_empty_bilingual(self, db_session: AsyncSession) -> None:
        """Evidence with no run items returns empty bilingual span."""
        from src.dao.postgresql.models import CanonicalEvidenceItem, SourceDocument

        doc = SourceDocument(source_document_id=uuid.uuid4(), raw_metadata={})
        db_session.add(doc)
        await db_session.flush()

        evidence = CanonicalEvidenceItem(
            canonical_evidence_id=uuid.uuid4(),
            source_document_id=doc.source_document_id,
            field_id="A.test.1",
            position_hash="abc",
            text_hash="def",
            entity_scope_hash="ghi",
            current_best_status="found",
            review_status="provisional",
            active_payload={},
        )
        db_session.add(evidence)
        await db_session.flush()

        linker = SourceLinker(db_session)
        bilingual = await linker.get_bilingual_span(
            canonical_evidence_id=evidence.canonical_evidence_id
        )

        assert bilingual.original_track is None
        assert bilingual.translated_track is None

    async def _create_test_evidence_with_span(
        self,
        session: AsyncSession,
        *,
        include_translated: bool = True,
    ) -> uuid.UUID:
        """Helper: create evidence with run items and source spans."""
        from src.dao.postgresql.models import (
            CanonicalEvidenceItem,
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

        evidence = CanonicalEvidenceItem(
            canonical_evidence_id=uuid.uuid4(),
            source_document_id=doc.source_document_id,
            field_id="A.test.1",
            position_hash="abc123",
            text_hash="def456",
            entity_scope_hash="ghi789",
            current_best_status="found",
            review_status="provisional",
            active_payload={"gene": "GLA"},
        )
        session.add(evidence)
        await session.flush()

        original_item = RunEvidenceItem(
            run_evidence_item_id=uuid.uuid4(),
            processing_run_id=run.processing_run_id,
            source_document_id=doc.source_document_id,
            canonical_evidence_id=evidence.canonical_evidence_id,
            track="original",
            field_id="A.test.1",
            status="found",
            value={"text": "Fabry disease"},
            position_hash="pos1",
            text_hash="txt1",
            entity_scope_hash="scope1",
            source_span={
                "page": 2,
                "block_index": 5,
                "start_offset": 100,
                "end_offset": 150,
                "text_snippet": "Patient diagnosed with Fabry disease at age 30.",
                "block_type": "text",
                "context_type": "text",
                "context_ref": "",
                "span_id": "",
                "bbox": [],
                "source_precision": "EXACT",
            },
        )
        session.add(original_item)

        if include_translated:
            translated_item = RunEvidenceItem(
                run_evidence_item_id=uuid.uuid4(),
                processing_run_id=run.processing_run_id,
                source_document_id=doc.source_document_id,
                canonical_evidence_id=evidence.canonical_evidence_id,
                track="translated",
                field_id="A.test.1",
                status="found",
                value={"text": "法布雷病"},
                position_hash="pos2",
                text_hash="txt2",
                entity_scope_hash="scope1",
                source_span={
                    "page": 2,
                    "block_index": 5,
                    "start_offset": 80,
                    "end_offset": 120,
                    "text_snippet": "患者30岁时被诊断为法布雷病。",
                    "block_type": "text",
                    "context_type": "text",
                    "context_ref": "",
                    "span_id": "",
                    "bbox": [],
                    "source_precision": "EXACT",
                },
            )
            session.add(translated_item)

        await session.flush()
        return evidence.canonical_evidence_id
