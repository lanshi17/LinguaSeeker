"""LangGraph workflow wiring for evidence extraction.

Name mapping:
- evidence_map.py now hosts the relevance_scan stage.
- quality_validation.py now hosts the quality_gate stage.
- chain_building is now chain_assembly.
"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph
from loguru import logger

from .contracts import (
    EvidenceExtractionState,
    EvidenceExtractionStatus,
    TrackDocument,
)
from .chunking import DEFAULT_INPUT_BUDGET_TOKENS
from .core import EvidenceChainBuilder
from .providers import LangChainEvidenceProvider
from .stages.catalog_extraction import CatalogExtractionStage
from .stages.evidence_map import RelevanceScanStage
from .stages.group_assignment import GroupAssignmentStage
from .stages.quality_validation import QualityGateStage
from .stages.source_grounding import SourceGroundingStage
from .stages.special_evidence import SpecialEvidenceStage


class EvidenceExtractionWorkflow:
    """LangGraph workflow for block-aware evidence extraction."""

    def __init__(
        self,
        provider: LangChainEvidenceProvider,
        input_budget_tokens: int = DEFAULT_INPUT_BUDGET_TOKENS,
    ):
        self._relevance_scan = RelevanceScanStage(provider, input_budget_tokens=input_budget_tokens)
        self._catalog_extraction = CatalogExtractionStage(provider, input_budget_tokens=input_budget_tokens)
        self._special_evidence = SpecialEvidenceStage(provider, input_budget_tokens=input_budget_tokens)
        self._group_assignment = GroupAssignmentStage()
        self._source_grounding = SourceGroundingStage()
        self._quality_gate = QualityGateStage()
        self._chain_builder = EvidenceChainBuilder()
        self._graph = self._build_graph()
        self._async_graph = self._build_async_graph()

    def _node_relevance_scan(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        emap = self._relevance_scan.run(state.document)
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

    async def _async_node_relevance_scan(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        emap = await self._relevance_scan.run_async(state.document)
        state.evidence_map = emap
        if not emap.relevant:
            state.status = EvidenceExtractionStatus.NOT_RELEVANT
        return state

    async def _async_node_catalog_extraction(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        items = await self._catalog_extraction.run_async(state.document, state.evidence_map)
        state.evidence_items = items
        return state

    async def _async_node_special_evidence(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        records = await self._special_evidence.run_async(state.document, state.evidence_items)
        state.special_evidence = records
        return state

    def _node_group_assignment(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        grouped_items, grouped_special = self._group_assignment.run(
            state.document,
            state.evidence_items,
            state.special_evidence,
        )
        state.evidence_items = grouped_items
        state.special_evidence = grouped_special
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

    def _node_chain_assembly(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        state.evidence_chains = self._chain_builder.build(state.evidence_items, state.special_evidence)
        return state

    def _node_quality_gate(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        contradictions = state.evidence_map.contradictions if state.evidence_map else []
        report = self._quality_gate.run(
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

        graph.add_node("relevance_scan", self._node_relevance_scan)
        graph.add_node("catalog_extraction", self._node_catalog_extraction)
        graph.add_node("special_evidence", self._node_special_evidence)
        graph.add_node("group_assignment", self._node_group_assignment)
        graph.add_node("source_grounding", self._node_source_grounding)
        graph.add_node("chain_assembly", self._node_chain_assembly)
        graph.add_node("quality_gate", self._node_quality_gate)
        graph.add_node("not_relevant", self._node_not_relevant)

        graph.set_entry_point("relevance_scan")
        graph.add_conditional_edges(
            "relevance_scan",
            lambda s: "not_relevant" if s.status == EvidenceExtractionStatus.NOT_RELEVANT else "catalog_extraction",
            {"not_relevant": "not_relevant", "catalog_extraction": "catalog_extraction"},
        )
        graph.add_edge("catalog_extraction", "special_evidence")
        graph.add_edge("special_evidence", "group_assignment")
        graph.add_edge("group_assignment", "source_grounding")
        graph.add_edge("source_grounding", "chain_assembly")
        graph.add_edge("chain_assembly", "quality_gate")
        graph.add_edge("quality_gate", END)
        graph.add_edge("not_relevant", END)

        return graph.compile()

    def _build_async_graph(self) -> Any:
        """Build a graph variant with async LLM nodes for concurrent chunk execution."""
        graph = StateGraph(EvidenceExtractionState)

        graph.add_node("relevance_scan", self._async_node_relevance_scan)
        graph.add_node("catalog_extraction", self._async_node_catalog_extraction)
        graph.add_node("special_evidence", self._async_node_special_evidence)
        graph.add_node("group_assignment", self._node_group_assignment)
        graph.add_node("source_grounding", self._node_source_grounding)
        graph.add_node("chain_assembly", self._node_chain_assembly)
        graph.add_node("quality_gate", self._node_quality_gate)
        graph.add_node("not_relevant", self._node_not_relevant)

        graph.set_entry_point("relevance_scan")
        graph.add_conditional_edges(
            "relevance_scan",
            lambda s: "not_relevant" if s.status == EvidenceExtractionStatus.NOT_RELEVANT else "catalog_extraction",
            {"not_relevant": "not_relevant", "catalog_extraction": "catalog_extraction"},
        )
        graph.add_edge("catalog_extraction", "special_evidence")
        graph.add_edge("special_evidence", "group_assignment")
        graph.add_edge("group_assignment", "source_grounding")
        graph.add_edge("source_grounding", "chain_assembly")
        graph.add_edge("chain_assembly", "quality_gate")
        graph.add_edge("quality_gate", END)
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

    async def run_async(self, document: TrackDocument) -> EvidenceExtractionState:
        """Async execution — uses async graph with concurrent chunk LLM calls."""
        initial_state = EvidenceExtractionState(document=document)
        final_state = await self._async_graph.ainvoke(initial_state)
        if isinstance(final_state, dict):
            final_state = EvidenceExtractionState(**final_state)
        return final_state
