"""GraphRAG Q&A engine: entity extraction, subgraph retrieval, and answer generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger
from pydantic import BaseModel, Field

from src.core.evidence_extraction.config_context import EvidenceExtractionConfigContext
from src.core.evidence_extraction.providers import EvidenceModelTier, LangChainEvidenceProvider
from src.core.graph_rag.contracts import (
    CitationResponse,
    GraphEdgeResponse,
    GraphNodeResponse,
    GraphRagQueryResponse,
    GraphSubgraphResponse,
)
from src.core.graph_rag.core.retrieval import SubgraphRetriever
from src.dao.neo4j.contracts import SubgraphContext

if TYPE_CHECKING:
    from src.core.config import Settings
    from src.dao.neo4j.repository import Neo4jRepository


class _ExtractedEntities(BaseModel):
    """Entities recognized from a natural-language question."""

    gene_symbols: list[str] = Field(default_factory=list)
    disease_names: list[str] = Field(default_factory=list)
    variants: list[str] = Field(default_factory=list)
    phenotypes: list[str] = Field(default_factory=list)


class _GeneratedAnswer(BaseModel):
    """Structured answer from the reasoning LLM."""

    answer: str = Field(..., description="Natural-language answer in the same language as the question")
    source_evidence_ids: list[str] = Field(
        default_factory=list,
        description="node_ids of Evidence nodes used in the answer",
    )


@dataclass(frozen=True)
class QaEngineConfig:
    """Configuration for the GraphRAG Q&A engine."""

    enabled: bool = True
    default_hops: int = 2
    default_mode: str = "full"
    max_context_nodes: int = 100
    max_context_edges: int = 150


class GraphRagQaEngine:
    """Answer natural-language questions using the Neo4j knowledge graph."""

    def __init__(
        self,
        repository: Neo4jRepository,
        config: QaEngineConfig | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._repository = repository
        self._config = config or QaEngineConfig()
        self._retriever = SubgraphRetriever(repository)
        self._provider = self._build_provider(settings)

    def _build_provider(self, settings: Settings | None = None) -> LangChainEvidenceProvider:
        """Build a LangChainEvidenceProvider from app settings or env config."""
        if settings is not None:
            ctx = EvidenceExtractionConfigContext.from_config(settings)
        else:
            from src.core.config import get_config

            ctx = EvidenceExtractionConfigContext.from_config(get_config())
        return LangChainEvidenceProvider(ctx)

    async def query(self, question: str, hops: int | None = None, mode: str | None = None) -> GraphRagQueryResponse:
        """Answer a natural-language question using the knowledge graph."""
        if not self._config.enabled:
            return self._empty_response(question)

        entities = await self._extract_entities(question)
        seed_ids = await self._find_seed_ids(entities)
        if not seed_ids:
            logger.info("No seed entities found in question: {}", question)
            return self._empty_response(question)

        subgraph = await self._retriever._repository.get_subgraph(
            seed_node_ids=seed_ids,
            hops=hops or self._config.default_hops,
            limit=self._config.max_context_nodes,
        )

        if mode == "terminology_only":
            subgraph = self._filter_terminology_only(subgraph)

        if not subgraph.nodes:
            return self._empty_response(question)

        answer_result = await self._generate_answer(question, subgraph)
        return GraphRagQueryResponse(
            question=question,
            answer=answer_result.answer,
            subgraph=_serialize_subgraph(subgraph),
            source_evidence_ids=answer_result.source_evidence_ids,
            citations=_build_citations(subgraph, answer_result.source_evidence_ids),
        )

    async def _extract_entities(self, question: str) -> _ExtractedEntities:
        """Use the fast LLM to extract biomedical entities from the question."""
        prompt = (
            "Extract biomedical entities from the following question. "
            "Return JSON with keys: gene_symbols, disease_names, variants, phenotypes. "
            "Each value is a list of strings. Use HGNC gene symbols, disease names, "
            "HGVS protein/cDNA variant notations, and HPO-like phenotype terms when present.\n\n"
            f"Question: {question}\n\n"
            "Return only JSON."
        )
        try:
            return await self._provider.ainvoke_structured(
                prompt=prompt,
                output_schema=_ExtractedEntities,
                tier=EvidenceModelTier.FAST,
                stage="graph_rag_entity_extraction",
            )
        except Exception as exc:
            logger.warning("Entity extraction failed for GraphRAG query: {}", exc)
            return _ExtractedEntities()

    async def _find_seed_ids(self, entities: _ExtractedEntities) -> list[str]:
        """Look up Neo4j node IDs by display name for the extracted entities."""
        seeds: list[str] = []

        if entities.gene_symbols:
            for gene in entities.gene_symbols:
                ids = await self._repository.find_node_ids_by_name(
                    label="Gene", names=[gene, gene.upper()],
                )
                seeds.extend(ids)

        if entities.disease_names:
            for disease in entities.disease_names:
                ids = await self._repository.find_node_ids_by_name(
                    label="Disease", names=[disease, disease.casefold()],
                )
                seeds.extend(ids)

        if entities.variants:
            for variant in entities.variants:
                ids = await self._repository.find_node_ids_by_name(
                    label="Variant", names=[variant.strip()],
                )
                seeds.extend(ids)

        if entities.phenotypes:
            for phenotype in entities.phenotypes:
                ids = await self._repository.find_node_ids_by_name(
                    label="Phenotype", names=[phenotype, phenotype.casefold()],
                )
                seeds.extend(ids)

        return list(dict.fromkeys(seeds))  # deduplicate preserving order

    async def _generate_answer(self, question: str, subgraph: SubgraphContext) -> _GeneratedAnswer:
        """Use the reasoning LLM to generate an answer with citations."""
        context_text = _subgraph_to_context_text(subgraph)
        prompt = (
            "You are a biomedical evidence assistant. Answer the user's question using "
            "only the provided knowledge graph context. Cite specific evidence node IDs "
            "in your reasoning. If the context does not contain enough information, say so.\n\n"
            f"Question: {question}\n\n"
            f"Knowledge graph context:\n{context_text}\n\n"
            "Return JSON with keys: answer (string), source_evidence_ids (list of strings)."
        )
        try:
            return await self._provider.ainvoke_structured(
                prompt=prompt,
                output_schema=_GeneratedAnswer,
                tier=EvidenceModelTier.STRONG,
                stage="graph_rag_answer_generation",
            )
        except Exception as exc:
            logger.warning("Answer generation failed for GraphRAG query: {}", exc)
            return _GeneratedAnswer(
                answer="Unable to generate an answer from the knowledge graph.",
                source_evidence_ids=[],
            )

    @staticmethod
    def _filter_terminology_only(subgraph: SubgraphContext) -> SubgraphContext:
        """Remove literature-only nodes from the subgraph."""
        from src.core.graph_rag.contracts import GraphEntityType

        allowed_labels = {
            GraphEntityType.GENE.value,
            GraphEntityType.VARIANT.value,
            GraphEntityType.DISEASE.value,
            GraphEntityType.PHENOTYPE.value,
        }
        filtered_nodes = [n for n in subgraph.nodes if any(label in allowed_labels for label in n.labels)]
        allowed_ids = {n.node_id for n in filtered_nodes}
        filtered_edges = [
            e for e in subgraph.edges if e.source_id in allowed_ids and e.target_id in allowed_ids
        ]
        return SubgraphContext(nodes=filtered_nodes, edges=filtered_edges)

    def _empty_response(self, question: str) -> GraphRagQueryResponse:
        return GraphRagQueryResponse(
            question=question,
            answer="No relevant knowledge graph context was found for this question.",
            subgraph=GraphSubgraphResponse(),
            source_evidence_ids=[],
            citations=[],
        )


def _serialize_subgraph(subgraph: SubgraphContext) -> GraphSubgraphResponse:
    """Convert a Neo4j subgraph to the API response model."""
    nodes = [
        GraphNodeResponse(
            node_id=n.node_id,
            labels=list(n.labels),
            display_name=str(n.properties.get("display_name", n.node_id)),
            properties=n.properties,
        )
        for n in subgraph.nodes
    ]
    edges = [
        GraphEdgeResponse(
            source_id=e.source_id,
            target_id=e.target_id,
            rel_type=e.rel_type,
            properties=e.properties,
        )
        for e in subgraph.edges
    ]
    return GraphSubgraphResponse(nodes=nodes, edges=edges)


def _build_citations(subgraph: SubgraphContext, evidence_ids: list[str]) -> list[CitationResponse]:
    """Build citation records from evidence nodes referenced in the answer."""
    citations: list[CitationResponse] = []
    evidence_nodes = [n for n in subgraph.nodes if "Evidence" in n.labels]
    for evidence_id in evidence_ids:
        node = next((n for n in evidence_nodes if n.node_id == evidence_id), None)
        if node is None:
            continue
        props = node.properties
        citations.append(
            CitationResponse(
                evidence_node_id=evidence_id,
                document_id=str(props.get("source_document_id", "")) or None,
                pmid=str(props.get("pmid", "")) or None,
                quote=str(props.get("quote", "")) or None,
            )
        )
    return citations


def _subgraph_to_context_text(subgraph: SubgraphContext) -> str:
    """Format a subgraph as concise LLM-readable text."""
    if not subgraph.nodes:
        return ""
    lines: list[str] = []
    lines.append("### Entities")
    for node in subgraph.nodes:
        display = node.properties.get("display_name", node.node_id)
        external_id = node.properties.get("external_id", "")
        id_part = f" ({external_id})" if external_id else ""
        lines.append(f"- [{':'.join(node.labels)}] {display}{id_part} [id={node.node_id}]")
    if subgraph.edges:
        lines.append("\n### Relationships")
        for edge in subgraph.edges:
            source_name = _display_name_for(subgraph, edge.source_id)
            target_name = _display_name_for(subgraph, edge.target_id)
            lines.append(f"- {source_name} --[{edge.rel_type}]--> {target_name}")
    return "\n".join(lines)


def _display_name_for(subgraph: SubgraphContext, node_id: str) -> str:
    for node in subgraph.nodes:
        if node.node_id == node_id:
            return str(node.properties.get("display_name", node.node_id))
    return node_id
