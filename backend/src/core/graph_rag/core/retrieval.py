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
        seed_ids = await self._find_seed_node_ids(target)
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

    async def _find_seed_node_ids(self, target: ExtractionTarget) -> list[str]:
        """Look up Neo4j node IDs by display name for the target entities."""
        seeds: list[str] = []

        if target.gene_symbol:
            gene_ids = await self._repository.find_node_ids_by_name(
                label="Gene",
                names=[target.gene_symbol, target.gene_symbol.upper()],
            )
            seeds.extend(gene_ids)

        if target.disease_name:
            disease_ids = await self._repository.find_node_ids_by_name(
                label="Disease",
                names=[target.disease_name, target.disease_name.casefold()],
            )
            seeds.extend(disease_ids)

        if target.variant_hgvs_p:
            variant_ids = await self._repository.find_node_ids_by_name(
                label="Variant",
                names=[target.variant_hgvs_p.strip()],
            )
            seeds.extend(variant_ids)

        return list(dict.fromkeys(seeds))  # deduplicate preserving order
