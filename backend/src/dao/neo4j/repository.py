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
        """Retrieve a multi-hop subgraph around the given seed nodes.

        Intended for the terminology baseline (gene/disease/phenotype), whose
        nodes carry a ``node_id``. Literature evidence nodes are super-high-degree
        (an ``EvidenceDoc`` binds hundreds of thousands of context entities), so
        they are reached via the bounded :meth:`get_evidence_bridge_subgraph`
        instead of generic multi-hop expansion, which would explode.
        """
        query = (
            "MATCH path = (seed)-[*1.." + str(hops) + "]-(connected) "
            "WHERE seed.node_id IN $seed_ids "
            "WITH DISTINCT nodes(path) AS ns "
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
        node_ids = [r["node_id"] for r in node_records if r["node_id"] is not None]
        rel_records = await self.execute_read(rel_query, node_ids=node_ids)

        nodes = [
            GraphNode(
                node_id=r["node_id"],
                labels=tuple(r["labels"]),
                properties=dict(r["props"]),
            )
            for r in node_records
            if r["node_id"] is not None
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

    async def get_evidence_bridge_subgraph(
        self,
        gene_names: list[str],
        variant_limit: int = 120,
    ) -> SubgraphContext:
        """Retrieve the gene→variant→disease triple bridged by evidence.

        Literature extraction links a gene (subject), a variant (target), and a
        disease (context) to the same ``Evidence`` node: the gene via a
        ``SUPPORTS`` edge and the variant/disease via ``MENTIONS`` edges (see
        ``EvidenceGraphBuilder``). There is no direct gene–variant or
        variant–disease edge.

        For readability the evidence nodes are **collapsed** here: rather than
        returning hundreds of intermediary ``Evidence`` nodes (a single gene can
        bind thousands), the method aggregates them into direct
        gene→variant, variant→disease, and gene→disease edges, each carrying an
        ``evidence_count`` property. The result is the compact triple itself
        instead of a hairball of evidence markers.

        Args:
            gene_names: Gene symbols to match (case-insensitive, name or
                display_name).
            variant_limit: Max distinct gene/variant/disease combinations to
                aggregate over.

        Returns:
            A subgraph of Gene/Variant/Disease nodes connected by aggregated
            ``HAS_REPORTED_VARIANT``/``ASSOCIATED_WITH`` edges. Node identifiers
            use ``coalesce(node_id, id)``.
        """
        if not gene_names:
            return SubgraphContext()

        query = (
            "MATCH (e:Evidence)-[:SUPPORTS]->(g:Gene) "
            "WHERE toLower(g.display_name) IN $names OR toLower(g.name) IN $names "
            "MATCH (e)-[:MENTIONS]->(v:Variant) "
            "OPTIONAL MATCH (e)-[:MENTIONS]->(d:Disease) "
            "WITH DISTINCT g, v, d, e LIMIT $variant_limit "
            "RETURN "
            "coalesce(g.node_id, g.id) AS g_id, labels(g) AS g_labels, properties(g) AS g_props, "
            "coalesce(v.node_id, v.id) AS v_id, labels(v) AS v_labels, properties(v) AS v_props, "
            "coalesce(d.node_id, d.id) AS d_id, labels(d) AS d_labels, properties(d) AS d_props"
        )
        lower_names = [n.lower() for n in gene_names]
        records = await self.execute_read(
            query, names=lower_names, variant_limit=variant_limit
        )

        nodes: dict[str, GraphNode] = {}
        # Aggregate evidence support per collapsed edge.
        edge_counts: dict[tuple[str, str, str], int] = {}

        def _add_node(prefix: str, rec: dict[str, Any]) -> str | None:
            node_id = rec.get(f"{prefix}_id")
            if node_id is None:
                return None
            if node_id not in nodes:
                nodes[node_id] = GraphNode(
                    node_id=node_id,
                    labels=tuple(rec.get(f"{prefix}_labels") or ()),
                    properties=dict(rec.get(f"{prefix}_props") or {}),
                )
            return node_id

        def _count_edge(src: str | None, dst: str | None, rel: str) -> None:
            if src is None or dst is None:
                return
            key = (src, dst, rel)
            edge_counts[key] = edge_counts.get(key, 0) + 1

        for rec in records:
            gid = _add_node("g", rec)
            vid = _add_node("v", rec)
            did = _add_node("d", rec)
            _count_edge(gid, vid, "HAS_REPORTED_VARIANT")
            _count_edge(vid, did, "ASSOCIATED_WITH")
            _count_edge(gid, did, "ASSOCIATED_WITH")

        edges = [
            GraphEdge(
                source_id=src,
                target_id=dst,
                rel_type=rel,
                properties={"evidence_count": count},
            )
            for (src, dst, rel), count in edge_counts.items()
        ]

        return SubgraphContext(nodes=list(nodes.values()), edges=edges)

    async def find_node_ids_by_name(
        self,
        label: str,
        names: list[str],
        limit: int = 50,
    ) -> list[str]:
        """Find terminology-baseline node IDs by name/alias match.

        Matches the terminology baseline (nodes with ``node_id`` + ``display_name``).
        Literature-extracted nodes are reached separately via
        :meth:`get_evidence_bridge_subgraph`, which keys on the gene name.

        Args:
            label: Neo4j node label to filter on (e.g. ``"Gene"``).
            names: Display names to search for (case-insensitive).
            limit: Maximum results.
        """
        if not names:
            return []
        query = (
            f"MATCH (n:{label}) "
            "WHERE toLower(n.display_name) IN $names "
            "OR ANY(a IN n.aliases WHERE toLower(a) IN $names) "
            "RETURN DISTINCT n.node_id AS node_id "
            "LIMIT $limit"
        )
        lower_names = [n.lower() for n in names]
        records = await self.execute_read(query, names=lower_names, limit=limit)
        return [r["node_id"] for r in records if r["node_id"] is not None]

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
