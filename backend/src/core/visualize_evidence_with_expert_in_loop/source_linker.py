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

        Loads the canonical item first to resolve the best run via
        current_best_run_evidence_id, then fetches that run item.
        Returns None if the canonical item or its best run doesn't exist.
        """
        # Step 1: load canonical item to get the best run pointer
        canonical_stmt = select(CanonicalEvidenceItem).where(
            CanonicalEvidenceItem.canonical_evidence_id == canonical_evidence_id,
        )
        canonical_result = await self._session.execute(canonical_stmt)
        canonical = canonical_result.scalar_one_or_none()

        if canonical is None or canonical.current_best_run_evidence_id is None:
            return None

        # Step 2: load the best run evidence item
        run_stmt = select(RunEvidenceItem).where(
            RunEvidenceItem.run_evidence_item_id == canonical.current_best_run_evidence_id,
        )
        run_result = await self._session.execute(run_stmt)
        item = run_result.scalar_one_or_none()

        if item is None:
            return None

        # Step 3: extract span from the run item
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
