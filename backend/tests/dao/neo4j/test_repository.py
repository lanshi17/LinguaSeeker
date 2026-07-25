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
