"""Tests for GraphRAG API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.v1.graph_rag import (
    get_knowledge_graph,
    router,
)
from src.dao.neo4j.contracts import GraphEdge, GraphNode, SubgraphContext


def test_query_route_is_registered() -> None:
    routes = [r.path for r in router.routes]
    assert "/query" in routes


def test_graph_route_is_registered() -> None:
    routes = [r.path for r in router.routes]
    assert "/graph" in routes


def test_graph_route_has_get_method() -> None:
    graph_route = next(r for r in router.routes if r.path == "/graph")
    assert "GET" in graph_route.methods


@pytest.mark.asyncio
async def test_get_knowledge_graph_serializes_only_nodes_with_visible_edges() -> None:
    repository = MagicMock()
    repository.find_node_ids_by_name = AsyncMock(return_value=["gene:EGFR"])
    repository.get_subgraph = AsyncMock(
        return_value=SubgraphContext(
            nodes=[
                GraphNode(node_id="gene:EGFR", labels=("Gene",)),
                GraphNode(node_id="disease:connected", labels=("Disease",)),
                GraphNode(node_id="variant:orphan", labels=("Variant",)),
                GraphNode(node_id="evidence:1", labels=("Evidence",)),
            ],
            edges=[
                GraphEdge(
                    source_id="gene:EGFR",
                    target_id="gene:EGFR",
                    rel_type="HAS_DOSAGE_SENSITIVITY",
                ),
                GraphEdge(
                    source_id="gene:EGFR",
                    target_id="disease:connected",
                    rel_type="ASSOCIATED_WITH",
                ),
                GraphEdge(
                    source_id="gene:EGFR",
                    target_id="evidence:1",
                    rel_type="SUPPORTS",
                ),
                GraphEdge(
                    source_id="evidence:1",
                    target_id="variant:orphan",
                    rel_type="MENTIONS",
                ),
            ],
        )
    )
    repository.get_evidence_bridge_subgraph = AsyncMock(return_value=SubgraphContext())

    response = await get_knowledge_graph(
        gene_symbol="EGFR",
        disease_name=None,
        variant_hgvs_p=None,
        phenotype=None,
        hops=2,
        mode="full",
        limit=200,
        repository=repository,
        account=MagicMock(),
    )

    returned_node_ids = {node.node_id for node in response.nodes}
    edge_node_ids = {node_id for edge in response.edges for node_id in (edge.source_id, edge.target_id)}
    assert returned_node_ids == {"gene:EGFR", "disease:connected"}
    assert returned_node_ids <= edge_node_ids
    assert any(edge.source_id == edge.target_id == "gene:EGFR" for edge in response.edges)


@pytest.mark.asyncio
async def test_get_knowledge_graph_returns_empty_graph_without_visible_edges() -> None:
    repository = MagicMock()
    repository.find_node_ids_by_name = AsyncMock(return_value=["gene:EGFR"])
    repository.get_subgraph = AsyncMock(
        return_value=SubgraphContext(
            nodes=[
                GraphNode(node_id="gene:EGFR", labels=("Gene",)),
                GraphNode(node_id="evidence:1", labels=("Evidence",)),
            ],
            edges=[
                GraphEdge(
                    source_id="gene:EGFR",
                    target_id="evidence:1",
                    rel_type="SUPPORTS",
                ),
            ],
        )
    )
    repository.get_evidence_bridge_subgraph = AsyncMock(return_value=SubgraphContext())

    response = await get_knowledge_graph(
        gene_symbol="EGFR",
        disease_name=None,
        variant_hgvs_p=None,
        phenotype=None,
        hops=2,
        mode="full",
        limit=200,
        repository=repository,
        account=MagicMock(),
    )

    assert response.nodes == []
    assert response.edges == []
