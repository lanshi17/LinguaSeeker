"""Neo4j repository abstraction.

Wraps ``neo4j.AsyncDriver`` with typed, domain-oriented read/write helpers.
All low-level Cypher execution stays here so business code depends on
``GraphNode``/``GraphEdge`` contracts rather than Neo4j Records.
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncDriver

from src.dao.neo4j.contracts import GraphEdge, GraphNode, SubgraphContext


class Neo4jRepository:
    """Async repository for Neo4j graph operations."""

    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    async def close(self) -> None:
        """Close the underlying driver."""
        await self._driver.close()

    async def execute_write(self, query: str, **parameters: Any) -> list[dict[str, Any]]:
        """Run a write query and return serialized records."""
        async with self._driver.session() as session:
            result = await session.execute_write(self._run_query, query, parameters)
            return result

    async def execute_read(self, query: str, **parameters: Any) -> list[dict[str, Any]]:
        """Run a read query and return serialized records."""
        async with self._driver.session() as session:
            result = await session.execute_read(self._run_query, query, parameters)
            return result

    @staticmethod
    async def _run_query(tx: Any, query: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        result = await tx.run(query, parameters)
        records = await result.data()
        return records

    async def merge_node(
        self,
        node_id: str,
        labels: tuple[str, ...],
        properties: dict[str, object] | None = None,
    ) -> None:
        """Merge a node by its ``node_id`` property."""
        props = dict(properties or {})
        props["node_id"] = node_id
        label_str = ":".join(labels)
        param_name = "props"
        query = f"MERGE (n:{label_str} {{node_id: $node_id}}) SET n = ${param_name}"
        await self.execute_write(query, node_id=node_id, props=props)

    async def merge_edge(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        properties: dict[str, object] | None = None,
    ) -> None:
        """Merge a relationship between two existing nodes."""
        props = dict(properties or {})
        query = (
            "MATCH (a {node_id: $source_id}), (b {node_id: $target_id}) "
            f"MERGE (a)-[r:{rel_type}]->(b) SET r = $props"
        )
        await self.execute_write(
            query,
            source_id=source_id,
            target_id=target_id,
            props=props,
        )

    async def get_subgraph(
        self,
        seed_node_ids: list[str],
        hops: int = 2,
        limit: int = 200,
    ) -> SubgraphContext:
        """Retrieve a multi-hop subgraph around the given seed nodes."""
        query = (
            "MATCH path = (seed)-[*1.." + str(hops) + "]-(connected) "
            "WHERE seed.node_id IN $seed_ids "
            "WITH DISTINCT nodes(path) AS ns, relationships(path) AS rels "
            "UNWIND ns AS n "
            "RETURN DISTINCT n.node_id AS node_id, labels(n) AS labels, properties(n) AS props "
            "LIMIT $limit"
        )
        node_records = await self.execute_read(query, seed_ids=seed_node_ids, limit=limit)

        rel_query = (
            "MATCH (a)-[r]-(b) "
            "WHERE a.node_id IN $node_ids AND b.node_id IN $node_ids "
            "RETURN DISTINCT a.node_id AS source_id, type(r) AS rel_type, "
            "b.node_id AS target_id, properties(r) AS props"
        )
        node_ids = [r["node_id"] for r in node_records]
        rel_records = await self.execute_read(rel_query, node_ids=node_ids)

        nodes = [
            GraphNode(
                node_id=r["node_id"],
                labels=tuple(r["labels"]),
                properties=dict(r["props"]),
            )
            for r in node_records
        ]
        edges = [
            GraphEdge(
                source_id=r["source_id"],
                target_id=r["target_id"],
                rel_type=r["rel_type"],
                properties=dict(r["props"]),
            )
            for r in rel_records
        ]
        return SubgraphContext(nodes=nodes, edges=edges)

    async def find_nodes(
        self,
        labels: tuple[str, ...] | None = None,
        property_filter: dict[str, object] | None = None,
        limit: int = 100,
    ) -> list[GraphNode]:
        """Find nodes by label and/or property equality."""
        conditions: list[str] = []
        params: dict[str, Any] = {}
        if property_filter:
            for idx, (key, value) in enumerate(property_filter.items()):
                param_key = f"p_{idx}"
                conditions.append(f"n.{key} = ${param_key}")
                params[param_key] = value

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        label_clause = ":".join(labels) if labels else ""
        query = f"MATCH (n:{label_clause}) {where_clause} RETURN n.node_id AS node_id, labels(n) AS labels, properties(n) AS props LIMIT $limit"
        params["limit"] = limit
        records = await self.execute_read(query, **params)
        return [
            GraphNode(
                node_id=r["node_id"],
                labels=tuple(r["labels"]),
                properties=dict(r["props"]),
            )
            for r in records
        ]
