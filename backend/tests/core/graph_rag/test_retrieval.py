"""Tests for SubgraphRetriever."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.core.evidence_extraction.contracts import ExtractionTarget
from src.core.graph_rag.core.retrieval import SubgraphRetriever
from src.dao.neo4j.contracts import GraphEdge, GraphNode, SubgraphContext


@pytest.fixture
def mock_repository() -> AsyncMock:
    return AsyncMock()


@pytest.mark.asyncio
async def test_retrieve_for_target_returns_empty_subgraph(mock_repository: AsyncMock) -> None:
    mock_repository.get_subgraph.return_value = SubgraphContext(nodes=[], edges=[])
    retriever = SubgraphRetriever(mock_repository)
    target = ExtractionTarget(gene_symbol="GLA", disease_name="Fabry disease")
    result = await retriever.retrieve_for_target(target)
    assert result.nodes == []
    assert result.edges == []


@pytest.mark.asyncio
async def test_retrieve_for_target_filters_terminology_only(mock_repository: AsyncMock) -> None:
    mock_repository.get_subgraph.return_value = SubgraphContext(
        nodes=[
            GraphNode(node_id="gene:GLA", labels=("Gene",), properties={}),
            GraphNode(node_id="evidence:1", labels=("Evidence",), properties={}),
        ],
        edges=[
            GraphEdge(source_id="gene:GLA", target_id="evidence:1", rel_type="SUPPORTS", properties={}),
        ],
    )
    retriever = SubgraphRetriever(mock_repository)
    target = ExtractionTarget(gene_symbol="GLA", disease_name="Fabry disease")
    result = await retriever.retrieve_for_target(target, mode="terminology_only")

    assert len(result.nodes) == 1
    assert result.nodes[0].node_id == "gene:GLA"
    assert result.edges == []
