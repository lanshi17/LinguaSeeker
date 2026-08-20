"""LangGraph workflow wiring for evidence extraction.

Name mapping:
- evidence_map.py now hosts the relevance_scan stage.
- quality_validation.py now hosts the quality_gate stage.
- chain_building is now chain_assembly.
"""

from __future__ import annotations

import asyncio
from typing import Any
from typing import Literal

from langgraph.graph import END, StateGraph
from loguru import logger
from .contracts import (
    EvidenceExtractionState,
    EvidenceExtractionStatus,
    EvidenceItem,
    Track,
    TrackDocument,
)
from .infrastructure.chunking import DEFAULT_INPUT_BUDGET_TOKENS
from .core.evidence_chain import EvidenceChainBuilder
from .core.normalization import EvidenceItemNormalizer
from .core.quality import TargetEntityGuard
from .domain.normalization import AcmgEvidenceValueNormalizer
from .providers import LangChainEvidenceProvider
from .stages.catalog_extraction import CatalogExtractionStage
from .stages.clinical_context import ClinicalContextStage
from .stages.evidence_map import RelevanceScanStage
from .stages.group_assignment import GroupAssignmentStage
from .stages.primary_broad_extraction import PrimaryBroadExtractionStage
from .stages.quality_validation import QualityGateStage
from .stages.role_routing import EvidenceRoleRouter
from .stages.review_validation import (
    DEFAULT_REVIEW_REJECT_POLICY,
    ReviewRejectPolicy,
    ReviewValidationStage,
    resolve_review_reject_policy,
)
from .stages.source_grounding import SourceGroundingStage
from .stages.graph_context_retrieval import GraphContextConfig, GraphContextRetrievalStage
from .stages.special_evidence import SpecialEvidenceStage
from .postprocess.target_span_recovery import TargetSpanFieldRecovery


ExtractionWorkflowMode = Literal["catalog", "broad"]

# Backward-compatibility aliases for callers that still use old mode names.
_MODE_ALIASES: dict[str, ExtractionWorkflowMode] = {
    "legacy": "catalog",
    "b8": "broad",
}

# Canonical business default for the extraction workflow mode.
# ``"broad"`` is the production primary-broad-extraction + review-validation
# path.  ``"catalog"`` remains available as an explicit rollback / historical
# baseline via ``extraction_mode="catalog"``.
DEFAULT_EXTRACTION_WORKFLOW_MODE: ExtractionWorkflowMode = "broad"


def resolve_extraction_mode(raw: str) -> ExtractionWorkflowMode:
    """Resolve a raw mode string to a canonical mode, applying aliases."""
    canonical = _MODE_ALIASES.get(raw, raw)
    if canonical not in ("catalog", "broad"):
        raise ValueError(f"Unknown extraction_mode {raw!r}")
    return canonical  # type: ignore[return-value]


class EvidenceExtractionWorkflow:
    """LangGraph workflow for block-aware evidence extraction."""

    def __init__(
        self,
        provider: LangChainEvidenceProvider,
        input_budget_tokens: int = DEFAULT_INPUT_BUDGET_TOKENS,
        field_profile: frozenset[str] | None = None,
        extraction_mode: str = DEFAULT_EXTRACTION_WORKFLOW_MODE,
        enable_review_validation: bool = True,
        enable_target_guard: bool = True,
        enable_source_grounding: bool = True,
        review_reject_policy: str = DEFAULT_REVIEW_REJECT_POLICY,
        graph_rag_service: Any | None = None,
        graph_rag_config: GraphContextConfig | None = None,
    ):
        self._extraction_mode = resolve_extraction_mode(extraction_mode)
        self._enable_review_validation = enable_review_validation
        self._enable_target_guard = enable_target_guard
        self._enable_source_grounding = enable_source_grounding
        self._review_reject_policy: ReviewRejectPolicy = resolve_review_reject_policy(review_reject_policy)
        self._relevance_scan = RelevanceScanStage(provider, input_budget_tokens=input_budget_tokens)
        self._graph_context_retrieval = GraphContextRetrievalStage(
            service=graph_rag_service,
            config=graph_rag_config or GraphContextConfig(),
        )
        self._catalog_extraction = CatalogExtractionStage(
            provider,
            input_budget_tokens=input_budget_tokens,
            field_profile=field_profile,
        )
        self._special_evidence = SpecialEvidenceStage(provider, input_budget_tokens=input_budget_tokens)
        self._clinical_context = ClinicalContextStage(provider, input_budget_tokens=input_budget_tokens)
        self._primary_broad_extraction = PrimaryBroadExtractionStage(provider)
        self._group_assignment = GroupAssignmentStage()
        self._value_normalizer = AcmgEvidenceValueNormalizer()
        self._source_grounding = SourceGroundingStage()
        self._quality_gate = QualityGateStage()
        self._chain_builder = EvidenceChainBuilder()
        self._role_router = EvidenceRoleRouter()
        self._review_validation = ReviewValidationStage(
            provider,
            review_reject_policy=self._review_reject_policy,
        )
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

    def _node_graph_context_retrieval(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        return self._graph_context_retrieval.run(state)

    def _node_primary_broad_extraction(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        items = self._primary_broad_extraction.run(state.document, graph_context=state.graph_context)
        state.evidence_items = items
        return state

    def _node_catalog_extraction(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        items = self._catalog_extraction.run(
            state.document,
            state.evidence_map,
            state.channel_classification,
            graph_context=state.graph_context,
        )
        state.evidence_items = items
        decision = self._catalog_extraction.last_eligibility_decision
        if decision is not None:
            state.channel_excluded_field_ids = decision.channel_rejected_field_ids
            state.target_excluded_field_ids = decision.excluded_field_ids - decision.channel_rejected_field_ids
        return state

    def _node_special_evidence(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        records = self._special_evidence.run(state.document, state.evidence_items)
        state.special_evidence = records
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
            _stamp_language(item, state.document, article_language) for item in state.evidence_items
        ]
        if state.phenotype_evidence:
            state.phenotype_evidence = [
                _stamp_language(item, state.document, article_language) for item in state.phenotype_evidence
            ]
        return state

    async def _async_node_relevance_scan(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        scan_result = await self._relevance_scan.run_async(state.document)
        state.evidence_map = scan_result.evidence_map
        state.channel_classification = scan_result.channel_classification
        if not scan_result.evidence_map.relevant:
            state.status = EvidenceExtractionStatus.NOT_RELEVANT
        return state

    async def _async_node_graph_context_retrieval(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        return await self._graph_context_retrieval.run_async(state)

    async def _async_node_primary_broad_extraction(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        items = await self._primary_broad_extraction.run_async(state.document, graph_context=state.graph_context)
        state.evidence_items = items
        return state

    async def _async_node_catalog_extraction(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        items = await self._catalog_extraction.run_async(
            state.document,
            state.evidence_map,
            state.channel_classification,
            graph_context=state.graph_context,
        )
        state.evidence_items = items
        decision = self._catalog_extraction.last_eligibility_decision
        if decision is not None:
            state.channel_excluded_field_ids = decision.channel_rejected_field_ids
            state.target_excluded_field_ids = decision.excluded_field_ids - decision.channel_rejected_field_ids
        return state

    async def _async_node_special_evidence(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        records = await self._special_evidence.run_async(state.document, state.evidence_items)
        state.special_evidence = records
        return state

    def _node_clinical_context(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        new_items = self._clinical_context.run(
            state.document,
            state.evidence_items,
            state.evidence_map,
        )
        if new_items:
            logger.info("clinical_context: adding {} supplementary items", len(new_items))
            state.evidence_items.extend(new_items)
        return state

    async def _async_node_clinical_context(self, state: EvidenceExtractionState) -> EvidenceExtractionState:
        new_items = await self._clinical_context.run_async(
            state.document,
            state.evidence_items,
            state.evidence_map,
        )
        if new_items:
            logger.info("clinical_context: adding {} supplementary items", len(new_items))
            state.evidence_items.extend(new_items)
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
        recovered = self._target_span_recovery.recover(
            state.document,
            state.evidence_items,
        )
        items, issues = self._value_normalizer.normalize(recovered)
        state.evidence_items = items
        state.normalization_issues = [*state.normalization_issues, *issues]
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

        Research scope note: the backfill expands to all 166 catalog rows for
        downstream matrix completeness, but *extraction* only targets fields
        that the source document can directly support (see README research
        boundary).  K.* fields are cross-paper GDV curation and are always
        NOT_APPLICABLE in single-document extraction.  Evaluation metrics
        should count against eligible/source-supported fields, not the full
        166-field catalog.
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

    def _node_functions(self, *, async_mode: bool) -> dict[str, Any]:
        """Return the node-name → callable mapping for sync or async mode."""
        return {
            "relevance_scan": self._async_node_relevance_scan if async_mode else self._node_relevance_scan,
            "graph_context_retrieval": self._async_node_graph_context_retrieval if async_mode else self._node_graph_context_retrieval,
            "catalog_extraction": self._async_node_catalog_extraction if async_mode else self._node_catalog_extraction,
            "special_evidence": self._async_node_special_evidence if async_mode else self._node_special_evidence,
            "clinical_context": self._async_node_clinical_context if async_mode else self._node_clinical_context,
            "primary_broad_extraction": self._async_node_primary_broad_extraction
            if async_mode
            else self._node_primary_broad_extraction,
            "language_metadata": self._async_node_language_metadata if async_mode else self._node_language_metadata,
            "group_assignment": self._node_group_assignment,
            "role_routing": self._node_role_routing,
            "review_validation": self._async_node_review_validation if async_mode else self._node_review_validation,
            "value_normalization": self._node_value_normalization,
            "target_guard": self._node_target_guard,
            "target_span_recovery": self._node_target_span_recovery,
            "source_grounding": self._node_source_grounding,
            "chain_assembly": self._node_chain_assembly,
            "quality_gate": self._node_quality_gate,
            "catalog_backfill": self._node_catalog_backfill,
            "not_relevant": self._node_not_relevant,
        }

    def _build_graph_with(self, nodes: dict[str, Any]) -> Any:
        """Build a LangGraph state machine from a node-name → callable mapping.

        Topology is defined once; sync vs async is determined by *nodes*.
        """
        graph = StateGraph(EvidenceExtractionState)
        for name, fn in nodes.items():
            graph.add_node(name, fn)

        graph.set_entry_point("relevance_scan")
        next_extraction_node = self._first_extraction_node()
        graph.add_conditional_edges(
            "relevance_scan",
            lambda s: "not_relevant" if s.status == EvidenceExtractionStatus.NOT_RELEVANT else "graph_context_retrieval",
            {"not_relevant": "not_relevant", "graph_context_retrieval": "graph_context_retrieval"},
        )
        graph.add_edge("graph_context_retrieval", next_extraction_node)
        if self._extraction_mode == "broad":
            graph.add_edge("primary_broad_extraction", "language_metadata")
        else:
            graph.add_edge("catalog_extraction", "special_evidence")
            graph.add_edge("special_evidence", "clinical_context")
            graph.add_edge("clinical_context", "language_metadata")
        graph.add_edge("language_metadata", "group_assignment")
        graph.add_edge("group_assignment", "role_routing")
        if self._extraction_mode == "broad" and self._enable_review_validation:
            graph.add_edge("role_routing", "review_validation")
            graph.add_edge("review_validation", "value_normalization")
        else:
            graph.add_edge("role_routing", "value_normalization")
        if self._enable_target_guard:
            graph.add_edge("value_normalization", "target_guard")
            graph.add_edge("target_guard", "target_span_recovery")
        else:
            graph.add_edge("value_normalization", "target_span_recovery")
        if self._enable_source_grounding:
            graph.add_edge("target_span_recovery", "source_grounding")
            graph.add_edge("source_grounding", "chain_assembly")
        else:
            graph.add_edge("target_span_recovery", "chain_assembly")
        graph.add_edge("chain_assembly", "quality_gate")
        graph.add_edge("quality_gate", "catalog_backfill")
        graph.add_edge("catalog_backfill", END)
        graph.add_edge("not_relevant", END)
        return graph.compile()

    def _build_graph(self) -> Any:
        return self._build_graph_with(self._node_functions(async_mode=False))

    def _build_async_graph(self) -> Any:
        """Build a graph variant with async LLM nodes for concurrent chunk execution."""
        return self._build_graph_with(self._node_functions(async_mode=True))

    def _first_extraction_node(self) -> str:
        if self._extraction_mode == "broad":
            return "primary_broad_extraction"
        return "catalog_extraction"

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
    target_variant = (target.primary_variant if target else "") or item.target_variant
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
