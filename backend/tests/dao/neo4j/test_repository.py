"""Tests for Neo4jRepository."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dao.neo4j.contracts import SubgraphContext
from src.dao.neo4j.repository import Neo4jRepository


@pytest.fixture
def mock_driver() -> MagicMock:
    driver = MagicMock()
    session_cm = AsyncMock()
    driver.session.return_value = session_cm
    session_cm.__aenter__.return_value = session_cm
    session_cm.__aexit__.return_value = None
    return driver


@pytest.fixture
def repository(mock_driver: MagicMock) -> Neo4jRepository:
    return Neo4jRepository(mock_driver)


@pytest.mark.asyncio
async def test_merge_node_invokes_execute_write(repository: Neo4jRepository, mock_driver: MagicMock) -> None:
    await repository.merge_node(
        node_id="gene:GLA",
        labels=("Gene",),
        properties={"display_name": "GLA"},
    )

    session_cm = mock_driver.session.return_value
    session_cm.execute_write.assert_called_once()
    call_args = session_cm.execute_write.call_args
    assert call_args is not None
    query = call_args.args[1]
    assert "MERGE" in query


@pytest.mark.asyncio
async def test_get_subgraph_returns_context(repository: Neo4jRepository, mock_driver: MagicMock) -> None:
    session_cm = mock_driver.session.return_value

    async def fake_run_query(tx: object, query: str, parameters: dict) -> list[dict]:
        if "n.node_id" in query:
            return [
                {
                    "node_id": "gene:GLA",
                    "labels": ["Gene"],
                    "props": {"display_name": "GLA"},
                },
            ]
        return [
            {
                "source_id": "gene:GLA",
                "rel_type": "ASSOCIATED_WITH",
                "target_id": "disease:fabry disease",
                "props": {},
            },
        ]

    session_cm.execute_read.side_effect = fake_run_query

    result = await repository.get_subgraph(["gene:GLA"], hops=2, limit=10)

    assert isinstance(result, SubgraphContext)
    assert len(result.nodes) == 1
    assert result.nodes[0].node_id == "gene:GLA"
    assert len(result.edges) == 1
    assert result.edges[0].rel_type == "ASSOCIATED_WITH"


@pytest.mark.asyncio
async def test_get_biomedical_subgraph_uses_bounded_apoc_traversal(
    repository: Neo4jRepository,
) -> None:
    repository.execute_read = AsyncMock(
        side_effect=[
            [
                {
                    "node_id": "gene:GLA",
                    "labels": ["Gene"],
                    "props": {"display_name": "GLA"},
                },
                {
                    "node_id": "disease:fabry-disease",
                    "labels": ["Disease"],
                    "props": {"display_name": "Fabry disease"},
                },
            ],
            [
                {
                    "source_id": "gene:GLA",
                    "rel_type": "ASSOCIATED_WITH",
                    "target_id": "disease:fabry-disease",
                    "props": {"source_db": "ClinGen"},
                },
            ],
        ]
    )

    result = await repository.get_biomedical_subgraph(
        ["gene:GLA", "gene:GLA", "disease:fabry-disease"],
        hops=2,
        limit=10,
    )

    assert isinstance(result, SubgraphContext)
    assert [node.node_id for node in result.nodes] == ["gene:GLA", "disease:fabry-disease"]
    assert [(edge.source_id, edge.target_id) for edge in result.edges] == [
        ("gene:GLA", "disease:fabry-disease"),
    ]

    node_call, edge_call = repository.execute_read.await_args_list
    node_query = node_call.args[0]
    assert "apoc.path.subgraphAll" in node_query
    assert "MATCH (seed:Node)" in node_query
    assert "bfs: true" in node_query
    assert "uniqueness: 'NODE_GLOBAL'" in node_query
    assert "filterStartNode: true" in node_query
    assert "labelFilter: $label_filter" in node_query
    assert "ORDER BY n.node_id" in node_query
    assert node_call.kwargs == {
        "seed_ids": ["gene:GLA", "disease:fabry-disease"],
        "hops": 2,
        "limit": 10,
        "per_seed_limit": 5,
        "label_filter": "+Gene|+Disease|+Variant|+Phenotype",
    }
    assert "MATCH (a)-[r]->(b)" in edge_call.args[0]
    assert "ORDER BY source_id, target_id, rel_type" in edge_call.args[0]
    assert "LIMIT $edge_limit" in edge_call.args[0]
    assert edge_call.kwargs == {
        "node_ids": ["gene:GLA", "disease:fabry-disease"],
        "edge_limit": 40,
    }


@pytest.mark.asyncio
async def test_get_biomedical_subgraph_skips_query_without_seeds(repository: Neo4jRepository) -> None:
    repository.execute_read = AsyncMock()

    result = await repository.get_biomedical_subgraph([])

    assert result == SubgraphContext()
    repository.execute_read.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_read_uses_configured_database(mock_driver: MagicMock) -> None:
    repository = Neo4jRepository(mock_driver, database="neo4j")

    await repository.execute_read("RETURN 1")

    mock_driver.session.assert_called_once_with(database="neo4j")
