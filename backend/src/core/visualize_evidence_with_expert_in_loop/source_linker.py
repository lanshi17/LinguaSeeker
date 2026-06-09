"""Source linker for evidence traceability."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    BilingualSpan,
    TrackSpan,
)
from src.dao.postgresql.models import CanonicalEvidenceItem, RunEvidenceItem


class SourceLinker:
    """Retrieve source spans for evidence traceability."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_track_span(
        self,
        *,
        canonical_evidence_id: UUID,
        track: str,
    ) -> TrackSpan | None:
        """Retrieve source span for one track (original or translated).

        Resolution strategy:
        1. Load canonical item to get identity fields and current_best_run_evidence_id.
        2. If the best run matches the requested track, use it directly.
        3. Otherwise, find a run item by identity tuple + track.
        """
        # Step 1: load canonical item
        canonical_stmt = select(CanonicalEvidenceItem).where(
            CanonicalEvidenceItem.canonical_evidence_id == canonical_evidence_id,
        )
        canonical_result = await self._session.execute(canonical_stmt)
        canonical = canonical_result.scalar_one_or_none()

        if canonical is None:
            return None

        # Step 2: try the best run first (fast path)
        item = None
        if canonical.current_best_run_evidence_id is not None:
            best_stmt = select(RunEvidenceItem).where(
                RunEvidenceItem.run_evidence_item_id == canonical.current_best_run_evidence_id,
            )
            best_result = await self._session.execute(best_stmt)
            best_item = best_result.scalar_one_or_none()
            if best_item is not None and best_item.track == track:
                item = best_item

        # Step 3: fallback — find by identity tuple + track
        if item is None:
            fallback_stmt = (
                select(RunEvidenceItem)
                .where(
                    RunEvidenceItem.source_document_id == canonical.source_document_id,
                    RunEvidenceItem.field_id == canonical.field_id,
                    RunEvidenceItem.position_hash == canonical.position_hash,
                    RunEvidenceItem.entity_scope_hash == canonical.entity_scope_hash,
                    RunEvidenceItem.track == track,
                )
                .limit(1)
            )
            fallback_result = await self._session.execute(fallback_stmt)
            item = fallback_result.scalar_one_or_none()

        if item is None:
            return None

        return self._build_track_span(track, item.source_span or {})

    @staticmethod
    def _build_track_span(track: str, span_data: dict) -> TrackSpan:
        """Build a TrackSpan from raw source_span JSONB data."""
        return TrackSpan(
            track=track,  # type: ignore[arg-type]
            source_span=span_data,
            block_text=span_data.get("text_snippet", ""),
            highlight_start=span_data.get("start_offset", 0),
            highlight_end=span_data.get("end_offset", 0),
            page=span_data.get("page"),
        )

    async def get_bilingual_span(
        self,
        *,
        canonical_evidence_id: UUID,
    ) -> BilingualSpan:
        """Retrieve both original and translated spans for bilingual traceability.

        Uses canonical_evidence_id as the natural cross-track anchor.
        """
        original = await self.get_track_span(
            canonical_evidence_id=canonical_evidence_id,
            track="original",
        )
        translated = await self.get_track_span(
            canonical_evidence_id=canonical_evidence_id,
            track="translated",
        )

        return BilingualSpan(
            canonical_evidence_id=canonical_evidence_id,
            original_track=original,
            translated_track=translated,
            alignment_confidence=1.0 if (original and translated) else None,
        )
