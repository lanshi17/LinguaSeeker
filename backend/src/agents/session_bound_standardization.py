"""Session-bound wrapper for EntityStandardizationService.

EntityStandardizationService requires a session in its constructor.
This wrapper creates a fresh session per call to run_dual_result(),
avoiding the closed-session problem (C1 fix).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if TYPE_CHECKING:
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
        DualEvidenceExtractionResult,
    )
    from src.core.standardize_entities_and_align_knowledge.contracts import (
        StandardizationResult,
    )


class SessionBoundStandardizationService:
    """Wrapper that provides session-per-request for EntityStandardizationService."""

    def __init__(self, cfg, session_factory: async_sessionmaker[AsyncSession]):
        self._cfg = cfg
        self._session_factory = session_factory

    async def run_dual_result(
        self,
        result: DualEvidenceExtractionResult,
        *,
        source_document_id: str,
        processing_run_id: str,
    ) -> StandardizationResult:
        """Run standardization with a fresh session."""
        from src.core.standardize_entities_and_align_knowledge.api import (
            EntityStandardizationService,
        )

        async with self._session_factory() as session:
            service = EntityStandardizationService(cfg=self._cfg, session=session)
            return await service.run_dual_result(
                result,
                source_document_id=source_document_id,
                processing_run_id=processing_run_id,
            )
