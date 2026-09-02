"""Neo4j repository abstraction.

Wraps ``neo4j.AsyncDriver`` with typed, domain-oriented read/write helpers.
All low-level Cypher execution stays here so business code depends on
``GraphNode``/``GraphEdge`` contracts rather than Neo4j Records.
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncDriver

from src.dao.neo4j.contracts import GraphEdge, GraphNode, SubgraphContext


_BIOMEDICAL_LABEL_FILTER = "+Gene|+Disease|+Variant|+Phenotype"


class Neo4jRepository:
    """Async repository for Neo4j graph operations."""

    def __init__(self, driver: AsyncDriver, database: str | None = None) -> None:
        self._driver = driver
        self._database = database

    async def close(self) -> None:
        """Close the underlying driver."""
        await self._driver.close()

    async def ensure_indexes(self) -> None:
        """Create read-path indexes and backfill lowercase display-name copies.

        Idempotent: safe to call on every startup or via the
        ``ensure_neo4j_indexes`` script. ``CREATE INDEX IF NOT EXISTS`` is a
        schema operation run outside a transaction; the backfill only touches
        nodes still missing ``display_name_lower`` so it is a no-op once every
        node has been migrated.

        These indexes back the hot read paths:
        - ``node_id``: :meth:`get_biomedical_subgraph` / :meth:`get_subgraph`
          seed lookups (``seed.node_id IN $seed_ids``).
        - ``display_name_lower``: :meth:`find_node_ids_by_name` and
          :meth:`get_evidence_bridge_subgraph` name matching, which previously
          forced full label scans via ``toLower()`` on every request.
        """
        async with self._driver.session(database=self._database) as session:
            for stmt in (
                "CREATE INDEX node_id_idx IF NOT EXISTS FOR (n:Node) ON (n.node_id)",
                "CREATE INDEX gene_display_lower_idx IF NOT EXISTS FOR (n:Gene) ON (n.display_name_lower)",
                "CREATE INDEX disease_display_lower_idx IF NOT EXISTS FOR (n:Disease) ON (n.display_name_lower)",
                "CREATE INDEX variant_display_lower_idx IF NOT EXISTS FOR (n:Variant) ON (n.display_name_lower)",
                "CREATE INDEX phenotype_display_lower_idx IF NOT EXISTS FOR (n:Phenotype) ON (n.display_name_lower)",
            ):
                result = await session.run(stmt)
                await result.consume()
            backfill = await session.run(
                "MATCH (n) "
                "WHERE n.display_name IS NOT NULL AND n.display_name_lower IS NULL "
                "SET n.display_name_lower = toLower(n.display_name)"
            )
            await backfill.consume()

    async def execute_write(self, query: str, **parameters: Any) -> list[dict[str, Any]]:
        """Run a write query and return serialized records."""
        async with self._driver.session(database=self._database) as session:
            result = await session.execute_write(self._run_query, query, parameters)
            return result

    async def execute_read(self, query: str, **parameters: Any) -> list[dict[str, Any]]:
        """Run a read query and return serialized records."""
        async with self._driver.session(database=self._database) as session:
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

    async def get_biomedical_subgraph(
        self,
        seed_node_ids: list[str],
        hops: int = 2,
        limit: int = 200,
    ) -> SubgraphContext:
        """Retrieve a bounded biomedical-only subgraph for visualization.

        Evidence and document nodes can have hundreds of thousands of
        relationships. They are intentionally excluded from this traversal so
        a two-hop graph view cannot fan out through them. Literature evidence
        is represented separately by :meth:`get_evidence_bridge_subgraph`.

        ``apoc.path.subgraphAll`` performs a breadth-first traversal and its
        ``limit`` counts nodes rather than paths, so the per-seed bound keeps
        the total work proportional to ``limit`` even when an entity lookup
        resolves to many seed nodes.
        """
        if not seed_node_ids:
            return SubgraphContext()

        bounded_limit = max(1, limit)
        bounded_seed_ids = list(dict.fromkeys(seed_node_ids))[:bounded_limit]
        per_seed_limit = max(1, bounded_limit // len(bounded_seed_ids))
        node_query = (
            "MATCH (seed:Node) "
            "WHERE seed.node_id IN $seed_ids "
            "CALL apoc.path.subgraphAll(seed, {"
            "maxLevel: $hops, "
            "bfs: true, "
            "uniqueness: 'NODE_GLOBAL', "
            "filterStartNode: true, "
            "limit: $per_seed_limit, "
            "labelFilter: $label_filter"
            "}) YIELD nodes "
            "UNWIND nodes AS n "
            "WITH DISTINCT n "
            "RETURN n.node_id AS node_id, labels(n) AS labels, properties(n) AS props "
            "ORDER BY n.node_id "
            "LIMIT $limit"
        )
        node_records = await self.execute_read(
            node_query,
            seed_ids=bounded_seed_ids,
            hops=hops,
            limit=bounded_limit,
            per_seed_limit=per_seed_limit,
            label_filter=_BIOMEDICAL_LABEL_FILTER,
        )
        node_ids = [record["node_id"] for record in node_records if record["node_id"] is not None]
        if not node_ids:
            return SubgraphContext()

        edge_limit = bounded_limit * 4
        edge_query = (
            "MATCH (a)-[r]->(b) "
            "WHERE a.node_id IN $node_ids AND b.node_id IN $node_ids "
            "RETURN DISTINCT a.node_id AS source_id, type(r) AS rel_type, "
            "b.node_id AS target_id, properties(r) AS props "
            "ORDER BY source_id, target_id, rel_type "
            "LIMIT $edge_limit"
        )
        edge_records = await self.execute_read(
            edge_query,
            node_ids=node_ids,
            edge_limit=edge_limit,
        )

        nodes = [
            GraphNode(
                node_id=record["node_id"],
                labels=tuple(record["labels"]),
                properties=dict(record["props"]),
            )
            for record in node_records
            if record["node_id"] is not None
        ]
        edges = [
            GraphEdge(
                source_id=record["source_id"],
                target_id=record["target_id"],
                rel_type=record["rel_type"],
                properties=dict(record["props"]),
            )
            for record in edge_records
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
            A subgraph of Gene/Variant/Disease nodes connected by literature
            edges with semantically distinct rel types
            (``HAS_REPORTED_VARIANT``, ``LITERATURE_VARIANT_DISEASE``,
            ``LITERATURE_GENE_DISEASE``) — kept separate from the ClinGen
            ``ASSOC_*`` and ``HAS_DOSAGE_SENSITIVITY`` edges that arrive via
            :meth:`get_subgraph`. Each edge carries ``evidence_count`` plus
            optional ``classification``, ``significance``, ``role``, and
            ``source`` for the frontend. Node identifiers use
            ``node_id`` (canonical store key).
        """
        if not gene_names:
            return SubgraphContext()

        # Two distinct rel types so literature triples don't get conflated
        # with the ClinGen ``ASSOCIATED_WITH`` edges that already come through
        # :meth:`get_subgraph`. ``source`` distinguishes literature from
        # ClinGen terminology; ``evidence_level`` carries the variant's
        # clinical significance when present on the underlying evidence.
        query = (
            "MATCH (e:Evidence)-[:SUPPORTS]->(g:Gene) "
            "WHERE g.display_name_lower IN $names "
            "MATCH (e)-[mv:MENTIONS]->(v:Variant) "
            "OPTIONAL MATCH (e)-[md:MENTIONS]->(d:Disease) "
            "WITH DISTINCT g, v, d, e, mv, md LIMIT $variant_limit "
            "RETURN "
            "g.node_id AS g_id, labels(g) AS g_labels, properties(g) AS g_props, "
            "v.node_id AS v_id, labels(v) AS v_labels, properties(v) AS v_props, "
            "d.node_id AS d_id, labels(d) AS d_labels, properties(d) AS d_props, "
            "coalesce(mv.role, '') AS mv_role, "
            "coalesce(md.role, '') AS md_role, "
            "properties(e) AS e_props"
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

        # Propagate per-edge semantic metadata so the frontend can label and
        # style the literature path distinctly from ClinGen terminology edges.
        edge_payloads: dict[tuple[str, str, str], dict[str, object]] = {}

        def _add_payload(src: str | None, dst: str | None, rel: str, props: dict[str, object]) -> None:
            if src is None or dst is None:
                return
            key = (src, dst, rel)
            # Count evidence rows backing this collapsed edge.
            edge_counts[key] = edge_counts.get(key, 0) + 1
            if key not in edge_payloads:
                edge_payloads[key] = dict(props)
            else:
                # Preserve the first non-empty semantic value seen so labels
                # don't flicker between runs.
                for k, v in props.items():
                    if v and not edge_payloads[key].get(k):
                        edge_payloads[key][k] = v

        for rec in records:
            gid = _add_node("g", rec)
            vid = _add_node("v", rec)
            did = _add_node("d", rec)
            mv_role = rec.get("mv_role") or ""
            md_role = rec.get("md_role") or ""
            e_props = rec.get("e_props") or {}
            classification = e_props.get("classification") or ""
            significance = e_props.get("significance") or ""
            source_db = e_props.get("source_db") or "literature"
            common_props: dict[str, object] = {"source": source_db}
            if classification:
                common_props["classification"] = classification
            if significance:
                common_props["significance"] = significance
            # Gene→Variant: distinct rel type so it doesn't collide with
            # ClinGen gene→disease terminology edges.
            _add_payload(gid, vid, "HAS_REPORTED_VARIANT", {**common_props, "role": mv_role or "target"})
            # Variant→Disease: literature-only, separate from ClinGen ASSOC_*.
            _add_payload(vid, did, "LITERATURE_VARIANT_DISEASE", {**common_props, "role": md_role or "context"})
            # Gene→Disease via literature evidence.
            _add_payload(gid, did, "LITERATURE_GENE_DISEASE", {**common_props, "role": md_role or "context"})

        edges = []
        for (src, dst, rel), count in edge_counts.items():
            payload = edge_payloads.get((src, dst, rel), {})
            edges.append(
                GraphEdge(
                    source_id=src,
                    target_id=dst,
                    rel_type=rel,
                    properties={**payload, "evidence_count": count},
                )
            )

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
            "WHERE n.display_name_lower IN $names "
            "OR ANY(a IN n.aliases_lower WHERE a IN $names) "
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
