"""Public facade for one-track evidence extraction."""
from __future__ import annotations

import asyncio
from typing import Any

from .config_context import EvidenceExtractionConfigContext
from .contracts import (
    EvidenceExtractionResult,
    TrackDocument,
)
from .providers import LangChainEvidenceProvider
from .workflow import EvidenceExtractionWorkflow


class EvidenceExtractionService:
    """Public facade for one-track evidence extraction.

    Usage::

        from src.core.config import get_config
        from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import (
            EvidenceExtractionService,
        )

        cfg = get_config()
        service = EvidenceExtractionService(cfg=cfg)
        result = await service.run(document)
    """

    def __init__(self, cfg: Any):
        self._ctx = EvidenceExtractionConfigContext.from_config(cfg)
        self._provider = LangChainEvidenceProvider(self._ctx)
        self._workflow = EvidenceExtractionWorkflow(provider=self._provider)

    async def run(self, document: TrackDocument) -> EvidenceExtractionResult:
        state = await self._workflow.run(document)
        return EvidenceExtractionResult(
            status=state.status,
            document_id=document.document_id,
            track=document.track,
            evidence_map=state.evidence_map,
            evidence_items=state.evidence_items,
            evidence_chains=state.evidence_chains,
            special_evidence=state.special_evidence,
            quality_report=state.quality_report,
        )

    def run_sync(self, document: TrackDocument) -> EvidenceExtractionResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run(document))
        raise RuntimeError(
            "run_sync() cannot be called from within a running event loop. "
            "Use run() instead."
        )
