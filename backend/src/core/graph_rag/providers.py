"""Neo4j persistence provider for GraphRAG batches."""

from __future__ import annotations

from typing import Any

from src.core.graph_rag.contracts import (
    LiteratureGraphBatch,
    LiteratureGraphEdge,
    LiteratureGraphNode,
)
from src.dao.neo4j.repository import Neo4jRepository


class Neo4jGraphProvider:
    """Write LiteratureGraphBatch structures into Neo4j."""

    def __init__(self, repository: Neo4jRepository) -> None:
        self._repository = repository

    async def write_batch(
        self,
        batch: LiteratureGraphBatch,
        chunk_size: int = 500,
    ) -> dict[str, int]:
        """Persist a batch of nodes and edges in chunks.

        Returns:
            Summary dict with ``nodes_written`` and ``edges_written``.
        """
        nodes_written = 0
        edges_written = 0

        for chunk in self._chunks(batch.nodes, chunk_size):
            await self._write_nodes(chunk)
            nodes_written += len(chunk)

        for chunk in self._chunks(batch.edges, chunk_size):
            await self._write_edges(chunk)
            edges_written += len(chunk)

        return {"nodes_written": nodes_written, "edges_written": edges_written}

    async def _write_nodes(self, nodes: list[LiteratureGraphNode]) -> None:
        if not nodes:
            return
        query = (
            "UNWIND $nodes AS node "
            "MERGE (n:Node {node_id: node.node_id}) "
            "SET n += node.properties "
            "SET n.display_name = node.display_name "
            "WITH n, node "
            "CALL apoc.create.addLabels(n, [node.entity_type]) YIELD node AS labeled "
            "RETURN count(*)"
        )
        params = {
            "nodes": [
                {
                    "node_id": n.node_id,
                    "entity_type": n.entity_type.value,
                    "display_name": n.display_name,
                    "properties": self._sanitize_properties(n.properties),
                }
                for n in nodes
            ]
        }
        await self._repository.execute_write(query, **params)

    async def _write_edges(self, edges: list[LiteratureGraphEdge]) -> None:
        if not edges:
            return
        # Neo4j does not support parameterizing relationship types directly, so
        # we batch edges by relation type and use literal type names.
        by_type: dict[str, list[LiteratureGraphEdge]] = {}
        for edge in edges:
            by_type.setdefault(edge.relation_type.value, []).append(edge)

        for rel_type, typed_edges in by_type.items():
            safe_type = self._escape_relation_type(rel_type)
            type_query = (
                "UNWIND $edges AS edge "
                f"MATCH (a {{node_id: edge.source_id}}), (b {{node_id: edge.target_id}}) "
                f"MERGE (a)-[r:{safe_type}]->(b) "
                "SET r += edge.properties "
                "RETURN count(*)"
            )
            params = {
                "edges": [
                    {
                        "source_id": e.source_id,
                        "target_id": e.target_id,
                        "properties": self._sanitize_properties(e.properties),
                    }
                    for e in typed_edges
                ]
            }
            await self._repository.execute_write(type_query, **params)

    @staticmethod
    def _chunks(items: list[Any], size: int) -> list[list[Any]]:
        return [items[i : i + size] for i in range(0, len(items), size)]

    @staticmethod
    def _sanitize_properties(properties: dict[str, object]) -> dict[str, object]:
        """Remove nulls and make values JSON-safe for Neo4j properties."""
        result: dict[str, object] = {}
        for key, value in properties.items():
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                result[key] = [v for v in value if v is not None]
            elif isinstance(value, (int, float, str, bool, dict)):
                result[key] = value
            else:
                result[key] = str(value)
        return result

    @staticmethod
    def _escape_relation_type(rel_type: str) -> str:
        """Escape backticks in relationship type names."""
        return f"`{rel_type.replace('`', '``')}`"
