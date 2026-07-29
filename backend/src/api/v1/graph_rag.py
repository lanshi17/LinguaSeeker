"""GraphRAG Q&A and knowledge graph exploration routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from starlette.requests import Request

from src.api.auth import get_current_account
from src.api.deps import get_neo4j_repository
from src.api.rate_limit import limiter
from src.core.auth.contracts import AuthContext
from src.core.config import get_config
from src.core.graph_rag.contracts import (
    GraphEdgeResponse,
    GraphNodeResponse,
    GraphRagQueryRequest,
    GraphRagQueryResponse,
    GraphSubgraphResponse,
)
from src.core.graph_rag.core.qa_engine import GraphRagQaEngine, QaEngineConfig
from src.dao.neo4j.contracts import SubgraphContext
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

    seed_ids: list[str] = []
    if gene_symbol:
        seed_ids.extend(await repository.find_node_ids_by_name(
            label="Gene", names=[gene_symbol.strip(), gene_symbol.strip().upper()],
        ))
    if disease_name:
        seed_ids.extend(await repository.find_node_ids_by_name(
            label="Disease", names=[disease_name.strip(), disease_name.strip().casefold()],
        ))
    if variant_hgvs_p:
        seed_ids.extend(await repository.find_node_ids_by_name(
            label="Variant", names=[variant_hgvs_p.strip()],
        ))
    if phenotype:
        seed_ids.extend(await repository.find_node_ids_by_name(
            label="Phenotype", names=[phenotype.strip(), phenotype.strip().casefold()],
        ))

    # Deduplicate preserving order
    seed_ids = list(dict.fromkeys(seed_ids))

    if not seed_ids:
        raise HTTPException(
            status_code=400,
            detail="No matching nodes found for the provided entities",
        )

    subgraph = await repository.get_subgraph(
        seed_node_ids=seed_ids,
        hops=hops,
        limit=limit,
    )
    if mode == "terminology_only":
        from src.core.graph_rag.contracts import GraphEntityType

        allowed_labels = {
            GraphEntityType.GENE.value,
            GraphEntityType.VARIANT.value,
            GraphEntityType.DISEASE.value,
            GraphEntityType.PHENOTYPE.value,
        }
        subgraph.nodes = [n for n in subgraph.nodes if any(label in allowed_labels for label in n.labels)]
        allowed_ids = {n.node_id for n in subgraph.nodes}
        subgraph.edges = [
            e for e in subgraph.edges if e.source_id in allowed_ids and e.target_id in allowed_ids
        ]

    return _serialize_subgraph(subgraph)


def _serialize_subgraph(subgraph: SubgraphContext) -> GraphSubgraphResponse:
    """Convert a Neo4j subgraph to the API response model."""
    nodes = [
        GraphNodeResponse(
            node_id=n.node_id,
            labels=list(n.labels),
            display_name=str(n.properties.get("display_name", n.node_id)),
            properties=n.properties,
        )
        for n in subgraph.nodes
    ]
    edges = [
        GraphEdgeResponse(
            source_id=e.source_id,
            target_id=e.target_id,
            rel_type=e.rel_type,
            properties=e.properties,
        )
        for e in subgraph.edges
    ]
    return GraphSubgraphResponse(nodes=nodes, edges=edges)
