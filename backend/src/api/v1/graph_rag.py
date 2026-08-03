"""GraphRAG Q&A and knowledge graph exploration routes."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from starlette.requests import Request

from src.api.auth import get_current_account
from src.api.deps import get_neo4j_repository
from src.api.rate_limit import limiter
from src.core.auth.contracts import AuthContext
from src.core.config import get_config
from src.core.graph_rag.contracts import (
    GraphEntityType,
    GraphEdgeResponse,
    GraphNodeResponse,
    GraphRagQueryRequest,
    GraphRagQueryResponse,
    GraphSubgraphResponse,
)
from src.core.graph_rag.core.qa_engine import GraphRagQaEngine, QaEngineConfig
from src.dao.neo4j.contracts import GraphNode, SubgraphContext
from src.dao.neo4j.repository import Neo4jRepository

router = APIRouter()


def _build_qa_engine(repository: Neo4jRepository | None) -> GraphRagQaEngine:
    """Build a GraphRagQaEngine from the global Neo4j repository."""
    if repository is None:
        raise HTTPException(status_code=503, detail="Neo4j repository is not available")
    cfg = get_config()
    graph_rag_cfg = cfg.graph_rag
    return GraphRagQaEngine(
        repository=repository,
        config=QaEngineConfig(
            enabled=graph_rag_cfg.enabled,
            default_hops=graph_rag_cfg.hops,
            default_mode=graph_rag_cfg.mode,
        ),
        settings=cfg,
    )


@router.post("/query", response_model=GraphRagQueryResponse)
@limiter.limit("30/minute")
async def query_graph_rag(
    request: Request,
    body: GraphRagQueryRequest,
    repository: Neo4jRepository | None = Depends(get_neo4j_repository),
    account: AuthContext = Depends(get_current_account),
) -> GraphRagQueryResponse:
    """Answer a natural-language question using the knowledge graph."""
    engine = _build_qa_engine(repository)
    try:
        return await engine.query(question=body.question, hops=body.hops, mode=body.mode)
    except Exception as exc:
        logger.exception("GraphRAG query failed")
        raise HTTPException(status_code=500, detail=f"GraphRAG query failed: {exc}") from exc


@router.get("/graph", response_model=GraphSubgraphResponse)
async def get_knowledge_graph(
    gene_symbol: str | None = Query(None, description="Filter by gene symbol"),
    disease_name: str | None = Query(None, description="Filter by disease name"),
    variant_hgvs_p: str | None = Query(None, description="Filter by HGVS protein variant"),
    phenotype: str | None = Query(None, description="Filter by phenotype term"),
    hops: int = Query(2, ge=1, le=4, description="Subgraph expansion hops"),
    mode: str = Query("full", description="terminology_only or full"),
    limit: int = Query(200, ge=1, le=500, description="Maximum nodes to return"),
    repository: Neo4jRepository | None = Depends(get_neo4j_repository),
    account: AuthContext = Depends(get_current_account),
) -> GraphSubgraphResponse:
    """Return a subgraph centered on the provided biomedical entities."""
    if repository is None:
        raise HTTPException(status_code=503, detail="Neo4j repository is not available")

    # Fan out the per-entity name lookups in parallel instead of awaiting
    # each Neo4j round-trip sequentially - the four label lookups are
    # independent and previously dominated subgraph latency.
    lookup_tasks: list[Awaitable[list[str]]] = []
    if gene_symbol:
        lookup_tasks.append(repository.find_node_ids_by_name(
            label="Gene", names=[gene_symbol.strip(), gene_symbol.strip().upper()],
        ))
    if disease_name:
        lookup_tasks.append(repository.find_node_ids_by_name(
            label="Disease", names=[disease_name.strip(), disease_name.strip().casefold()],
        ))
    if variant_hgvs_p:
        lookup_tasks.append(repository.find_node_ids_by_name(
            label="Variant", names=[variant_hgvs_p.strip()],
        ))
    if phenotype:
        lookup_tasks.append(repository.find_node_ids_by_name(
            label="Phenotype", names=[phenotype.strip(), phenotype.strip().casefold()],
        ))

    seed_ids: list[str] = []
    if lookup_tasks:
        for ids in await asyncio.gather(*lookup_tasks):
            seed_ids.extend(ids)

    # Deduplicate preserving order
    seed_ids = list(dict.fromkeys(seed_ids))

    biomedical_task = (
        repository.get_biomedical_subgraph(
            seed_node_ids=seed_ids, hops=hops, limit=limit,
        )
        if seed_ids
        else None
    )
    bridge_task = (
        repository.get_evidence_bridge_subgraph(gene_names=[gene_symbol.strip()])
        if mode != "terminology_only" and gene_symbol
        else None
    )

    # In full mode, augment a gene query with the gene→variant→disease
    # relationships bridged by literature evidence documents. These nodes live
    # in a separate identifier space from the terminology baseline and are not
    # reachable via generic multi-hop expansion, so they are merged in here.
    if biomedical_task is not None and bridge_task is not None:
        subgraph, bridge = await asyncio.gather(biomedical_task, bridge_task)
        subgraph = _merge_subgraphs(subgraph, bridge)
    elif biomedical_task is not None:
        subgraph = await biomedical_task
    elif bridge_task is not None:
        subgraph = await bridge_task
    else:
        subgraph = SubgraphContext()

    if not subgraph.nodes:
        raise HTTPException(
            status_code=400,
            detail="No matching nodes found for the provided entities",
        )

    subgraph = _project_visible_biomedical_subgraph(subgraph)

    return _serialize_subgraph(subgraph)


def _merge_subgraphs(a: SubgraphContext, b: SubgraphContext) -> SubgraphContext:
    """Merge two subgraphs, de-duplicating nodes by id and edges by triple."""
    nodes = {n.node_id: n for n in a.nodes}
    for n in b.nodes:
        nodes.setdefault(n.node_id, n)
    edges = {(e.source_id, e.target_id, e.rel_type): e for e in a.edges}
    for e in b.edges:
        edges.setdefault((e.source_id, e.target_id, e.rel_type), e)
    return SubgraphContext(nodes=list(nodes.values()), edges=list(edges.values()))


def _project_visible_biomedical_subgraph(subgraph: SubgraphContext) -> SubgraphContext:
    """Keep biomedical nodes only when they retain a visible relationship.

    Generic expansion can reach a biomedical entity solely through Evidence or
    Document nodes. Once those intermediary nodes are removed from the visual
    graph, retaining the entity would create an isolated node. A self-loop is
    still a visible relationship and therefore keeps its node.
    """
    allowed_labels = {
        GraphEntityType.GENE.value,
        GraphEntityType.VARIANT.value,
        GraphEntityType.DISEASE.value,
        GraphEntityType.PHENOTYPE.value,
    }
    biomedical_nodes = [node for node in subgraph.nodes if any(label in allowed_labels for label in node.labels)]
    biomedical_ids = {node.node_id for node in biomedical_nodes}
    visible_edges = [
        edge for edge in subgraph.edges if edge.source_id in biomedical_ids and edge.target_id in biomedical_ids
    ]
    connected_ids = {node_id for edge in visible_edges for node_id in (edge.source_id, edge.target_id)}
    return SubgraphContext(
        nodes=[node for node in biomedical_nodes if node.node_id in connected_ids],
        edges=visible_edges,
        summary_text=subgraph.summary_text,
        source_evidence_ids=subgraph.source_evidence_ids,
    )


def _display_name_for(node: GraphNode) -> str:
    """Resolve a human-readable label across terminology and literature nodes.

    Terminology nodes carry ``display_name``; literature-extracted nodes carry
    ``name`` (gene/variant) or ``doc_id`` (evidence documents) instead.
    """
    props = node.properties
    for key in ("display_name", "name", "doc_id"):
        value = props.get(key)
        if value:
            return str(value)
    return node.node_id


# Human-readable suffix for an edge's rel_type, derived from its
# ``source_db`` and ``evidence_level`` properties. Distinguishes a ClinGen
# "definitive" gene-disease association from a "limited" one and a dosage
# "haploinsufficiency" from "no evidence" — so the graph carries real
# semantics instead of collapsing them all to ``ASSOCIATED_WITH``.
def _edge_rel_type(rel_type: str, properties: dict[str, object]) -> str:
    source = str(properties.get("source_db") or "").strip()
    level = str(properties.get("evidence_level") or "").strip()
    if rel_type == "ASSOCIATED_WITH" and source == "ClinGen" and level:
        return f"ASSOC_{_slugify_level(level)}"
    if rel_type == "HAS_DOSAGE_SENSITIVITY" and level:
        return f"DOSAGE_{_slugify_level(level)}"
    return rel_type


def _slugify_level(level: str) -> str:
    """Stable, uppercase identifier for a free-text evidence level."""
    return (
        level.upper()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
    )


def _serialize_subgraph(subgraph: SubgraphContext) -> GraphSubgraphResponse:
    """Convert a Neo4j subgraph to the API response model."""
    nodes = [
        GraphNodeResponse(
            node_id=n.node_id,
            labels=list(n.labels),
            display_name=_display_name_for(n),
            properties=n.properties,
        )
        for n in subgraph.nodes
    ]
    edges = [
        GraphEdgeResponse(
            source_id=e.source_id,
            target_id=e.target_id,
            rel_type=_edge_rel_type(e.rel_type, e.properties),
            properties=e.properties,
        )
        for e in subgraph.edges
    ]
    return GraphSubgraphResponse(nodes=nodes, edges=edges)
