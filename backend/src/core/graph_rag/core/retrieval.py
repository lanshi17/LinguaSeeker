"""Subgraph retrieval for GraphRAG context augmentation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.graph_rag.contracts import GraphEntityType
from src.dao.neo4j.contracts import SubgraphContext

if TYPE_CHECKING:
    from src.core.evidence_extraction.contracts import ExtractionTarget
    from src.dao.neo4j.repository import Neo4jRepository


class SubgraphRetriever:
    """Retrieve relevant subgraphs from Neo4j for a given extraction target."""

    def __init__(self, repository: Neo4jRepository) -> None:
        self._repository = repository

    async def retrieve_for_target(
        self,
        target: ExtractionTarget,
        hops: int = 2,
        mode: str = "full",
        limit: int = 200,
    ) -> SubgraphContext:
        """Retrieve a subgraph centered on the gene-disease-variant target.

        Args:
            target: The gene-disease-variant hypothesis being extracted.
            hops: Number of relationship hops to expand from seed nodes.
            mode: "terminology_only" skips literature Evidence nodes;
                  "full" includes both terminology and literature evidence.
            limit: Maximum nodes to return.
        """
        seed_ids = self._seed_node_ids(target)
        if not seed_ids:
            return SubgraphContext()

        subgraph = await self._repository.get_subgraph(
            seed_node_ids=seed_ids,
            hops=hops,
            limit=limit,
        )

        if mode == "terminology_only":
            subgraph.nodes = [
                n for n in subgraph.nodes
                if GraphEntityType.EVIDENCE.value not in n.labels
                and GraphEntityType.DOCUMENT.value not in n.labels
                and GraphEntityType.PROCESSING_RUN.value not in n.labels
            ]
            allowed_ids = {n.node_id for n in subgraph.nodes}
            subgraph.edges = [
                e for e in subgraph.edges
                if e.source_id in allowed_ids and e.target_id in allowed_ids
            ]

        return subgraph

    @staticmethod
    def _seed_node_ids(target: ExtractionTarget) -> list[str]:
        seeds: list[str] = []
        if target.gene_symbol:
            seeds.append(f"gene:{target.gene_symbol.upper()}")
        if target.disease_name:
            seeds.append(f"disease:{target.disease_name.casefold()}")
        if target.variant_hgvs_p:
            seeds.append(f"variant:{target.variant_hgvs_p.strip()}")
        return seeds
