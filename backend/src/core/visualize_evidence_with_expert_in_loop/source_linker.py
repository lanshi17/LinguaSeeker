"""Source linker for evidence traceability."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    BilingualSpan,
    TrackSpan,
)
from src.dao.models import RunEvidenceItem


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

        Returns None if no run item exists for the specified track.
        """
        stmt = (
            select(RunEvidenceItem)
            .where(
                RunEvidenceItem.canonical_evidence_id == canonical_evidence_id,
                RunEvidenceItem.track == track,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        item = result.scalar_one_or_none()

        if item is None:
            return None

        span_data = item.source_span or {}
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
