"""Tests for GraphRagQaEngine."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.graph_rag.core.qa_engine import GraphRagQaEngine, QaEngineConfig
from src.dao.neo4j.contracts import GraphEdge, GraphNode, SubgraphContext


@pytest.fixture
def mock_repository() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def engine(mock_repository: AsyncMock) -> GraphRagQaEngine:
    with patch.object(GraphRagQaEngine, "_build_provider", return_value=MagicMock()):
        return GraphRagQaEngine(
            repository=mock_repository,
            config=QaEngineConfig(enabled=True),
        )


@pytest.mark.asyncio
async def test_query_returns_empty_when_disabled(mock_repository: AsyncMock) -> None:
    with patch.object(GraphRagQaEngine, "_build_provider", return_value=MagicMock()):
        engine = GraphRagQaEngine(
            repository=mock_repository,
            config=QaEngineConfig(enabled=False),
        )
    result = await engine.query("What is GLA?")
    assert "No relevant" in result.answer
    assert result.subgraph.nodes == []


@pytest.mark.asyncio
async def test_query_generates_answer_from_subgraph(engine: GraphRagQaEngine, mock_repository: AsyncMock) -> None:
    mock_repository.get_subgraph.return_value = SubgraphContext(
        nodes=[
            GraphNode(node_id="gene:GLA", labels=("Gene",), properties={"display_name": "GLA"}),
            GraphNode(
                node_id="evidence:1",
                labels=("Evidence",),
                properties={"source_document_id": "doc-1", "pmid": "12345", "quote": "foo"},
            ),
        ],
        edges=[
            GraphEdge(source_id="gene:GLA", target_id="evidence:1", rel_type="SUPPORTS", properties={}),
        ],
    )
    mock_repository.find_node_ids_by_name.return_value = ["gene:GLA"]

    fake_entities = MagicMock()
    fake_entities.gene_symbols = ["GLA"]
    fake_entities.disease_names = []
    fake_entities.variants = []
    fake_entities.phenotypes = []

    fake_answer = MagicMock()
    fake_answer.answer = "GLA is associated with Fabry disease."
    fake_answer.source_evidence_ids = ["evidence:1"]

    with patch.object(engine, "_extract_entities", return_value=fake_entities):
        with patch.object(engine, "_generate_answer", return_value=fake_answer):
            result = await engine.query("What is GLA?")

    assert result.answer == "GLA is associated with Fabry disease."
    assert result.source_evidence_ids == ["evidence:1"]
    assert len(result.citations) == 1
    assert result.citations[0].pmid == "12345"
