"""Public facade for GraphRAG graph construction and retrieval."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from src.core.graph_rag.contracts import LiteratureGraphBatch
from src.core.graph_rag.core.builder import EvidenceGraphBuilder
from src.core.graph_rag.core.context_formatter import ContextFormatter
from src.core.graph_rag.core.retrieval import SubgraphRetriever
from src.core.graph_rag.providers import Neo4jGraphProvider

if TYPE_CHECKING:
    from src.core.evidence_extraction.contracts import (
        DualEvidenceExtractionResult,
        EvidenceChain,
        ExtractionTarget,
        SpecialEvidenceRecord,
    )
    from src.core.standardize_entities_and_align_knowledge.contracts import (
        EntityMatch,
        StandardizationInput,
    )
    from src.dao.neo4j.repository import Neo4jRepository


class GraphRagService:
    """Service for building, querying, and writing the knowledge graph."""

    def __init__(self, repository: Neo4jRepository) -> None:
        self._repository = repository
        self._provider = Neo4jGraphProvider(repository)
        self._retriever = SubgraphRetriever(repository)
        self._formatter = ContextFormatter()
        self._builder = EvidenceGraphBuilder()

    async def retrieve_context_for_target(
        self,
        target: ExtractionTarget,
        hops: int = 2,
        mode: str = "full",
    ) -> str:
        """Retrieve a formatted graph context string for an extraction target."""
        subgraph = await self._retriever.retrieve_for_target(
            target=target,
            hops=hops,
            mode=mode,
        )
        return self._formatter.format(subgraph)

    async def write_standardization_graph(
        self,
        input_data: StandardizationInput,
        matches: tuple[EntityMatch, ...],
    ) -> dict[str, int]:
        """Write a standardization result as a literature evidence subgraph."""
        batch = self._builder.build_from_standardization(input_data, matches)
        summary = await self._provider.write_batch(batch)
        logger.info(
            "Wrote standardization graph for run {}: {} nodes, {} edges",
            input_data.processing_run_id,
            summary["nodes_written"],
            summary["edges_written"],
        )
        return summary

    async def write_evidence_chains_graph(
        self,
        source_document_id: str,
        processing_run_id: str,
        chains: list[EvidenceChain],
    ) -> dict[str, int]:
        """Write gene-disease-variant edges from evidence chains."""
        batch = self._builder.build_from_evidence_chains(
            source_document_id,
            processing_run_id,
            chains,
        )
        summary = await self._provider.write_batch(batch)
        logger.info(
            "Wrote evidence-chain graph for run {}: {} nodes, {} edges",
            processing_run_id,
            summary["nodes_written"],
            summary["edges_written"],
        )
        return summary

    async def write_special_evidence_graph(
        self,
        source_document_id: str,
        processing_run_id: str,
        records: list[SpecialEvidenceRecord],
    ) -> dict[str, int]:
        """Write special evidence (contradictions, authority) nodes."""
        batch = self._builder.build_from_special_evidence(
            source_document_id,
            processing_run_id,
            records,
        )
        summary = await self._provider.write_batch(batch)
        logger.info(
            "Wrote special-evidence graph for run {}: {} nodes, {} edges",
            processing_run_id,
            summary["nodes_written"],
            summary["edges_written"],
        )
        return summary

    async def write_dual_result_graph(
        self,
        input_data: StandardizationInput,
        matches: tuple[EntityMatch, ...],
        dual_result: DualEvidenceExtractionResult,
    ) -> dict[str, int]:
        """Write the complete graph for a dual-track extraction result.

        This combines standardized entities, evidence-chain relationships, and
        special evidence records into one coherent subgraph.
        """
        batch = LiteratureGraphBatch()

        std_batch = self._builder.build_from_standardization(input_data, matches)
        batch.nodes.extend(std_batch.nodes)
        batch.edges.extend(std_batch.edges)

        result = dual_result.reconciled_result or dual_result.original_result
        if result is not None:
            chain_batch = self._builder.build_from_evidence_chains(
                input_data.source_document_id,
                input_data.processing_run_id,
                result.evidence_chains,
            )
            batch.nodes.extend(chain_batch.nodes)
            batch.edges.extend(chain_batch.edges)

            special_records: list[SpecialEvidenceRecord] = []
            for record in result.special_evidence:
                special_records.append(record)
            special_batch = self._builder.build_from_special_evidence(
                input_data.source_document_id,
                input_data.processing_run_id,
                special_records,
            )
            batch.nodes.extend(special_batch.nodes)
            batch.edges.extend(special_batch.edges)

        summary = await self._provider.write_batch(batch)
        logger.info(
            "Wrote dual-result graph for run {}: {} nodes, {} edges",
            input_data.processing_run_id,
            summary["nodes_written"],
            summary["edges_written"],
        )
        return summary
