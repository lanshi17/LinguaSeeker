"""GraphRAG context retrieval stage for evidence extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from src.core.evidence_extraction.contracts import EvidenceExtractionState
    from src.core.graph_rag.api import GraphRagService


@dataclass(frozen=True)
class GraphContextConfig:
    """Configuration for graph context retrieval."""

    enabled: bool = False
    hops: int = 2
    mode: str = "full"


class GraphContextRetrievalStage:
    """Retrieve graph context for the current extraction target."""

    def __init__(self, service: GraphRagService | None, config: GraphContextConfig) -> None:
        self._service = service
        self._config = config

    async def run_async(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        """Populate ``state.graph_context`` if enabled and service is available."""
        if not self._config.enabled or self._service is None:
            state.graph_context = ""
            return state

        target = state.document.extraction_target
        if target is None:
            state.graph_context = ""
            return state

        try:
            context = await self._service.retrieve_context_for_target(
                target=target,
                hops=self._config.hops,
                mode=self._config.mode,
            )
            state.graph_context = context
            logger.debug(
                "Graph context retrieved for {} (hops={}, mode={}): {} chars",
                target.scope_key,
                self._config.hops,
                self._config.mode,
                len(context),
            )
        except Exception as exc:
            logger.warning("Graph context retrieval failed for {}: {}", target.scope_key, exc)
            state.graph_context = ""
        return state

    def run(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        """Synchronous wrapper (retrieval is async, so this runs it in the loop)."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            return loop.run_until_complete(self.run_async(state))
        except RuntimeError:
            return asyncio.run(self.run_async(state))
