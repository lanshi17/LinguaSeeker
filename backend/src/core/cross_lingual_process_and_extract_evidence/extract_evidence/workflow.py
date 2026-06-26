"""LangGraph workflow wiring for evidence extraction.

Name mapping:
- evidence_map.py now hosts the relevance_scan stage.
- quality_validation.py now hosts the quality_gate stage.
- chain_building is now chain_assembly.
"""
from __future__ import annotations

import asyncio
from typing import Any

from langgraph.graph import END, StateGraph
from loguru import logger
from .contracts import (
    EvidenceExtractionState,
    EvidenceExtractionStatus,
    EvidenceItem,
    Track,
    TrackDocument,
)
from .chunking import DEFAULT_INPUT_BUDGET_TOKENS
from .core import EvidenceChainBuilder, EvidenceItemNormalizer, TargetEntityGuard
from .normalization import AcmgEvidenceValueNormalizer
from .providers import LangChainEvidenceProvider
from .stages.evidence_map import RelevanceScanStage
from .stages.group_assignment import GroupAssignmentStage
from .stages.primary_broad_extraction import PrimaryBroadExtractionStage
from .stages.quality_validation import QualityGateStage
from .stages.role_routing import EvidenceRoleRouter
from .stages.review_validation import ReviewValidationStage
from .stages.source_grounding import SourceGroundingStage
from .target_span_recovery import TargetSpanFieldRecovery

class EvidenceExtractionWorkflow:
    """LangGraph workflow for block-aware evidence extraction."""

    def __init__(
        self,
        provider: LangChainEvidenceProvider,
        input_budget_tokens: int = DEFAULT_INPUT_BUDGET_TOKENS,
        field_profile: frozenset[str] | None = None,
    ):
        del field_profile
        self._relevance_scan = RelevanceScanStage(provider, input_budget_tokens=input_budget_tokens)
        self._primary_broad_extraction = PrimaryBroadExtractionStage(provider)
        self._group_assignment = GroupAssignmentStage()
        self._value_normalizer = AcmgEvidenceValueNormalizer()
        self._source_grounding = SourceGroundingStage()
        self._quality_gate = QualityGateStage()
        self._chain_builder = EvidenceChainBuilder()
        self._role_router = EvidenceRoleRouter()
        self._review_validation = ReviewValidationStage(provider)
        self._target_guard = TargetEntityGuard()
        self._target_span_recovery = TargetSpanFieldRecovery()
        self._item_normalizer = EvidenceItemNormalizer()
        self._graph = self._build_graph()
        self._async_graph = self._build_async_graph()

    def _node_relevance_scan(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        scan_result = self._relevance_scan.run(state.document)
        state.evidence_map = scan_result.evidence_map
        state.channel_classification = scan_result.channel_classification
        if not scan_result.evidence_map.relevant:
            state.status = EvidenceExtractionStatus.NOT_RELEVANT
        return state

    def _node_primary_broad_extraction(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        items = self._primary_broad_extraction.run(state.document)
        state.evidence_items = items
        return state


    def _node_language_metadata(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        """Stamp article_language metadata onto every emitted EvidenceItem.

        Resolves the document's article language from the ``TrackDocument``
        track + metadata (``source_language``), then propagates it to all
        evidence items. The translated track is always English; the original
        track carries ``metadata["source_language"]`` (which is ``"en"`` for
        English originals).
        """
        article_language = _resolve_article_language(state.document)
        state.evidence_items = [
            _stamp_language(item, state.document, article_language)
            for item in state.evidence_items
        ]
        if state.phenotype_evidence:
            state.phenotype_evidence = [
                _stamp_language(item, state.document, article_language)
                for item in state.phenotype_evidence
            ]
        return state

    async def _async_node_relevance_scan(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        scan_result = await self._relevance_scan.run_async(state.document)
        state.evidence_map = scan_result.evidence_map
        state.channel_classification = scan_result.channel_classification
        if not scan_result.evidence_map.relevant:
            state.status = EvidenceExtractionStatus.NOT_RELEVANT
        return state

    async def _async_node_primary_broad_extraction(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        items = await self._primary_broad_extraction.run_async(state.document)
        state.evidence_items = items
        return state

    async def _async_node_language_metadata(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        return self._node_language_metadata(state)

    def _node_group_assignment(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        grouped_items, grouped_special = self._group_assignment.run(
            state.document,
            state.evidence_items,
            state.special_evidence,
        )
        state.evidence_items = grouped_items
        state.special_evidence = grouped_special
        return state

    def _node_role_routing(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        primary, phenotype, discarded = self._role_router.route(
            state.evidence_items,
            extraction_target=state.document.extraction_target,
        )
        state.evidence_items = primary
        state.phenotype_evidence = phenotype
        state.discarded_evidence = discarded
        return state


    def _node_value_normalization(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        items, issues = self._value_normalizer.normalize(state.evidence_items)
        state.evidence_items = items
        state.normalization_issues = [*state.normalization_issues, *issues]
        return state

    def _node_review_validation(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        state.evidence_items = self._review_validation.run(state.document, state.evidence_items)
        return state

    async def _async_node_review_validation(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        state.evidence_items = await self._review_validation.run_async(state.document, state.evidence_items)
        return state

    def _node_target_guard(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        state.evidence_items = self._target_guard.apply(
            state.evidence_items,
            state.document.extraction_target,
        )
        return state

    def _node_target_span_recovery(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        state.evidence_items = self._target_span_recovery.recover(
            state.document,
            state.evidence_items,
        )
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

    def _node_catalog_backfill(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        """Expand sparse evidence_items to the full 166-row catalog per group.

        Runs AFTER quality_gate so the gate's metrics reflect real extracted
        items, not synthesized NOT_FOUND placeholders. Downstream alignment
        and reporting consume the backfilled matrix.

        Fields excluded by channel eligibility get status NOT_APPLICABLE.
        Fields excluded by target/source eligibility get status NOT_ATTEMPTED.
        Eligible fields absent from extraction get status NOT_FOUND.
        """
        state.evidence_items = self._item_normalizer.normalize_grouped(
            state.evidence_items,
            channel_excluded_field_ids=state.channel_excluded_field_ids,
            target_excluded_field_ids=state.target_excluded_field_ids,
        )
        return state

    def _node_not_relevant(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        logger.info("Document {} marked not relevant", state.document.document_id)
        return state

    def _build_graph(self) -> Any:
        graph = StateGraph(EvidenceExtractionState)

        graph.add_node("relevance_scan", self._node_relevance_scan)
        graph.add_node("primary_broad_extraction", self._node_primary_broad_extraction)
        graph.add_node("language_metadata", self._node_language_metadata)
        graph.add_node("group_assignment", self._node_group_assignment)
        graph.add_node("role_routing", self._node_role_routing)
        graph.add_node("review_validation", self._node_review_validation)
        graph.add_node("value_normalization", self._node_value_normalization)
        graph.add_node("target_guard", self._node_target_guard)
        graph.add_node("target_span_recovery", self._node_target_span_recovery)
        graph.add_node("source_grounding", self._node_source_grounding)
        graph.add_node("chain_assembly", self._node_chain_assembly)
        graph.add_node("quality_gate", self._node_quality_gate)
        graph.add_node("catalog_backfill", self._node_catalog_backfill)
        graph.add_node("not_relevant", self._node_not_relevant)

        graph.set_entry_point("relevance_scan")
        graph.add_conditional_edges(
            "relevance_scan",
            lambda s: "not_relevant" if s.status == EvidenceExtractionStatus.NOT_RELEVANT else "primary_broad_extraction",
            {"not_relevant": "not_relevant", "primary_broad_extraction": "primary_broad_extraction"},
        )
        graph.add_edge("primary_broad_extraction", "language_metadata")
        graph.add_edge("language_metadata", "group_assignment")
        graph.add_edge("group_assignment", "role_routing")
        graph.add_edge("role_routing", "review_validation")
        graph.add_edge("review_validation", "value_normalization")
        graph.add_edge("value_normalization", "target_guard")
        graph.add_edge("target_guard", "target_span_recovery")
        graph.add_edge("target_span_recovery", "source_grounding")
        graph.add_edge("source_grounding", "chain_assembly")
        graph.add_edge("chain_assembly", "quality_gate")
        graph.add_edge("quality_gate", "catalog_backfill")
        graph.add_edge("catalog_backfill", END)
        graph.add_edge("not_relevant", END)

        return graph.compile()

    def _build_async_graph(self) -> Any:
        """Build a graph variant with async LLM nodes for concurrent chunk execution."""
        graph = StateGraph(EvidenceExtractionState)

        graph.add_node("relevance_scan", self._async_node_relevance_scan)
        graph.add_node("primary_broad_extraction", self._async_node_primary_broad_extraction)
        graph.add_node("language_metadata", self._async_node_language_metadata)
        graph.add_node("group_assignment", self._node_group_assignment)
        graph.add_node("role_routing", self._node_role_routing)
        graph.add_node("review_validation", self._async_node_review_validation)
        graph.add_node("value_normalization", self._node_value_normalization)
        graph.add_node("target_guard", self._node_target_guard)
        graph.add_node("target_span_recovery", self._node_target_span_recovery)
        graph.add_node("source_grounding", self._node_source_grounding)
        graph.add_node("chain_assembly", self._node_chain_assembly)
        graph.add_node("quality_gate", self._node_quality_gate)
        graph.add_node("catalog_backfill", self._node_catalog_backfill)
        graph.add_node("not_relevant", self._node_not_relevant)

        graph.set_entry_point("relevance_scan")
        graph.add_conditional_edges(
            "relevance_scan",
            lambda s: "not_relevant" if s.status == EvidenceExtractionStatus.NOT_RELEVANT else "primary_broad_extraction",
            {"not_relevant": "not_relevant", "primary_broad_extraction": "primary_broad_extraction"},
        )
        graph.add_edge("primary_broad_extraction", "language_metadata")
        graph.add_edge("language_metadata", "group_assignment")
        graph.add_edge("group_assignment", "role_routing")
        graph.add_edge("role_routing", "review_validation")
        graph.add_edge("review_validation", "value_normalization")
        graph.add_edge("value_normalization", "target_guard")
        graph.add_edge("target_guard", "target_span_recovery")
        graph.add_edge("target_span_recovery", "source_grounding")
        graph.add_edge("source_grounding", "chain_assembly")
        graph.add_edge("chain_assembly", "quality_gate")
        graph.add_edge("quality_gate", "catalog_backfill")
        graph.add_edge("catalog_backfill", END)
        graph.add_edge("not_relevant", END)

        return graph.compile()


    async def run(self, document: TrackDocument) -> EvidenceExtractionState:
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


def _resolve_article_language(document: TrackDocument) -> str:
    """Resolve the article language code for a track document.

    The translated track is always English. The original track carries its
    source language in ``metadata["source_language"]`` (defaults to ``"en"``
    when unset, matching the English-only default of the pipeline).
    """
    if document.track == Track.TRANSLATED:
        return "en"
    source_language = str(document.metadata.get("source_language", "")).strip().lower()
    return source_language or "en"


def _stamp_language(
    item: EvidenceItem,
    document: TrackDocument,
    article_language: str,
) -> EvidenceItem:
    """Stamp article-language metadata onto an evidence item if not already set.

    Derives ``is_english`` / ``requires_translation`` / ``evidence_source_language``
    directly rather than relying on the contract validator, because
    ``model_copy`` does not re-run validators in Pydantic v2.
    """
    if item.article_language and item.is_english is not None:
        return item
    is_english = article_language in {"en", "eng", "english"}
    target = document.extraction_target
    target_gene = target.gene_symbol if target else item.target_gene
    target_disease = target.disease_name if target else item.target_disease
    target_variant = (target.variant_hgvs_p if target else "") or item.target_variant
    return item.model_copy(
        update={
            "article_language": article_language,
            "is_english": is_english,
            "requires_translation": not is_english,
            "evidence_source_language": article_language,
            "source_database": item.source_database or document.metadata.get("source_database", ""),
            "target_gene": target_gene,
            "target_disease": target_disease,
            "target_variant": target_variant,
        }
    )
