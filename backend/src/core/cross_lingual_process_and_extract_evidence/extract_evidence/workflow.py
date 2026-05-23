"""LangGraph workflow wiring for evidence extraction."""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph
from loguru import logger

from .contracts import (
    EvidenceExtractionState,
    EvidenceExtractionStatus,
    TrackDocument,
)
from .core import EvidenceChainBuilder
from .providers import LangChainEvidenceProvider
from .stages.catalog_extraction import CatalogExtractionStage
from .stages.evidence_map import EvidenceMapStage
from .stages.quality_validation import QualityGateStage
from .stages.source_grounding import SourceGroundingStage
from .stages.special_evidence import SpecialEvidenceStage


class EvidenceExtractionWorkflow:
    """LangGraph workflow for 5-stage evidence extraction."""

    def __init__(self, provider: LangChainEvidenceProvider):
        self._evidence_map = EvidenceMapStage(provider)
        self._catalog_extraction = CatalogExtractionStage(provider)
        self._special_evidence = SpecialEvidenceStage(provider)
        self._source_grounding = SourceGroundingStage()
        self._quality_validation = QualityGateStage()
        self._chain_builder = EvidenceChainBuilder()
        self._graph = self._build_graph()

    def _node_evidence_map(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        emap = self._evidence_map.run(state.document)
        state.evidence_map = emap
        if not emap.relevant:
            state.status = EvidenceExtractionStatus.NOT_RELEVANT
        return state

    def _node_catalog_extraction(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        items = self._catalog_extraction.run(state.document, state.evidence_map)
        state.evidence_items = items
        return state

    def _node_special_evidence(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        records = self._special_evidence.run(state.document, state.evidence_items)
        state.special_evidence = records
        return state

    def _node_source_grounding(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        grounded_items, grounded_special = self._source_grounding.run(
            state.document,
            state.evidence_items,
            state.special_evidence,
        )
        state.evidence_items = grounded_items
        state.special_evidence = grounded_special
        return state

    def _node_chain_building(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        state.evidence_chains = self._chain_builder.build(state.evidence_items, state.special_evidence)
        return state

    def _node_quality_validation(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        contradictions = state.evidence_map.contradictions if state.evidence_map else []
        report = self._quality_validation.run(
            state.evidence_items,
            contradictions,
            chains=state.evidence_chains,
            special_records=state.special_evidence,
            evidence_chain_count=len(state.evidence_chains),
        )
        state.quality_report = report
        return state

    def _node_not_relevant(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        logger.info("Document {} marked not relevant", state.document.document_id)
        return state

    def _build_graph(self) -> Any:
        graph = StateGraph(EvidenceExtractionState)

        graph.add_node("evidence_map", self._node_evidence_map)
        graph.add_node("catalog_extraction", self._node_catalog_extraction)
        graph.add_node("special_evidence", self._node_special_evidence)
        graph.add_node("source_grounding", self._node_source_grounding)
        graph.add_node("chain_building", self._node_chain_building)
        graph.add_node("quality_validation", self._node_quality_validation)
        graph.add_node("not_relevant", self._node_not_relevant)

        graph.set_entry_point("evidence_map")
        graph.add_conditional_edges(
            "evidence_map",
            lambda s: "not_relevant" if s.status == EvidenceExtractionStatus.NOT_RELEVANT else "catalog_extraction",
            {"not_relevant": "not_relevant", "catalog_extraction": "catalog_extraction"},
        )
        graph.add_edge("catalog_extraction", "source_grounding")
        graph.add_edge("source_grounding", "chain_building")
        graph.add_edge("chain_building", "special_evidence")
        graph.add_edge("special_evidence", "quality_validation")
        graph.add_edge("quality_validation", END)
        graph.add_edge("not_relevant", END)

        return graph.compile()

    async def run(self, document: TrackDocument) -> EvidenceExtractionState:
        import asyncio

        initial_state = EvidenceExtractionState(document=document)
        try:
            loop = asyncio.get_running_loop()
            final_state = await loop.run_in_executor(None, self._graph.invoke, initial_state)
        except RuntimeError:
            final_state = self._graph.invoke(initial_state)

        if isinstance(final_state, dict):
            final_state = EvidenceExtractionState(**final_state)

        return final_state
