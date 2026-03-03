"""
证据检索与质量监控 API 端点
提供基于 Gene / Variant / Protein Change 的多文档图谱检索、
实体关联分析、证据聚合和质量监控接口。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path, Query
from loguru import logger
from pydantic import BaseModel, Field

from src.database.neo4j_client import get_neo4j_client
from src.domain.graph.association_service import get_entity_association_analyzer
from src.domain.evidence.aggregator import get_evidence_aggregation_engine
from src.domain.graph.search import get_graph_search_engine
from src.domain.graph.sync import get_graph_sync_service

# ==================== 请求/响应模型 ====================


class EvidenceSearchRequest(BaseModel):
    """证据搜索请求"""
    gene_symbol: Optional[str] = Field(None, description="基因符号，如 BRCA1")
    variant: Optional[str] = Field(None, description="变异 HGVS c./p. 描述")
    protein_change: Optional[str] = Field(None, description="蛋白变化描述")
    disease_name: Optional[str] = Field(None, description="疾病名称模糊搜索")
    min_confidence: Optional[float] = Field(None, ge=0, le=100, description="最低置信度")
    only_valid: bool = Field(False, description="仅返回有效证据 (>=85)")

    class Config:
        json_schema_extra = {
            "example": {
                "gene_symbol": "BRCA1",
                "variant": "NM_007294.4:c.68_69delAG",
                "protein_change": "p.Glu23Valfs",
                "disease_name": "breast cancer",
                "min_confidence": 85,
                "only_valid": True,
            }
        }


class EvidenceSearchResponse(BaseModel):
    """证据搜索响应"""
    code: int = 0
    message: str = "ok"
    data: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {"example": {"code": 0, "message": "ok", "data": {"total": 12}}}


class AggregationResponse(BaseModel):
    """聚合响应"""
    code: int = 0
    message: str = "ok"
    data: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {"example": {"code": 0, "message": "ok", "data": {"variants": []}}}


class QualityOverviewResponse(BaseModel):
    """质量监控响应"""
    code: int = 0
    message: str = "ok"
    data: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {"example": {"code": 0, "message": "ok", "data": {"total_evidence": 0}}}


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error details.")

    class Config:
        json_schema_extra = {"example": {"detail": "Invalid input."}}


# ==================== Router ====================

router = APIRouter(prefix="/evidence", tags=["Evidence"])


def _parse_document_identifier(raw_id: str) -> tuple[str, Optional[int]]:
    normalized = str(raw_id or "").strip()
    if normalized.isdigit():
        return normalized, int(normalized)
    return normalized, None


def _inject_document_identifier(payload: Dict[str, Any], normalized: str, numeric: Optional[int]) -> Dict[str, Any]:
    identifier: Any = numeric if numeric is not None else normalized
    if identifier:
        payload["document_id"] = identifier
    if numeric is not None:
        for record in payload.get("evidence_records", []):
            if record.get("document_id") == normalized:
                record["document_id"] = numeric
    return payload


# ==================== 图谱检索 ====================

@router.post(
    "/search",
    response_model=EvidenceSearchResponse,
    summary="多文档图谱检索",
    description=(
        "基于 Gene / Variant / Protein Change 的多文档图谱检索。\n"
        "请求体为 JSON，至少包含 gene_symbol / variant / protein_change 之一。\n"
        "响应体返回 evidence 统计与明细结构。"
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Missing required search key."},
        422: {"model": ErrorResponse, "description": "Validation error."},
        500: {"model": ErrorResponse, "description": "Search failed."},
    },
)
async def search_evidence(req: EvidenceSearchRequest):
    """Run a multi-document graph search with structured filters."""
    if not any([req.gene_symbol, req.variant, req.protein_change]):
        raise HTTPException(status_code=400, detail="至少需要提供 gene_symbol / variant / protein_change 之一")

    try:
        logger.info("Evidence search request received")
        engine = get_graph_search_engine()
        result = engine.search_multi(
            gene_symbol=req.gene_symbol,
            variant=req.variant,
            protein_change=req.protein_change,
            disease_name=req.disease_name,
            min_confidence=req.min_confidence,
            only_valid=req.only_valid,
        )
        logger.debug("Evidence search result: {} evidence", result.total_evidence)
        return EvidenceSearchResponse(data=result.to_dict())
    except Exception as e:
        logger.error("Evidence search failed: {}", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/search/gene/{gene_symbol}",
    response_model=EvidenceSearchResponse,
    summary="按基因搜索",
    description="按基因符号检索所有相关变异和证据。",
    responses={
        500: {"model": ErrorResponse, "description": "Search failed."},
    },
)
async def search_by_gene(
    gene_symbol: str = Path(..., description="基因符号，如 BRCA1"),
):
    """Search evidence by gene symbol."""
    try:
        logger.info("Gene search request: {}", gene_symbol)
        engine = get_graph_search_engine()
        result = engine.search_by_gene(gene_symbol)
        logger.debug("Gene search result: {} evidence", result.total_evidence)
        return EvidenceSearchResponse(data=result.to_dict())
    except Exception as e:
        logger.error("Gene search failed: {}", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/search/variant/{variant:path}",
    response_model=EvidenceSearchResponse,
    summary="按变异搜索",
    description="按变异 HGVS 描述检索完整证据子图。",
    responses={
        500: {"model": ErrorResponse, "description": "Search failed."},
    },
)
async def search_by_variant(
    variant: str = Path(..., description="变异 HGVS c./p. 描述"),
):
    """Search evidence by variant HGVS string."""
    try:
        logger.info("Variant search request: {}", variant)
        engine = get_graph_search_engine()
        result = engine.search_by_variant(variant)
        logger.debug("Variant search result: {} evidence", result.total_evidence)
        return EvidenceSearchResponse(data=result.to_dict())
    except Exception as e:
        logger.error("Variant search failed: {}", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/document/{document_id}",
    response_model=EvidenceSearchResponse,
    summary="文档证据检索",
    description="获取某文档的所有证据。",
    responses={
        500: {"model": ErrorResponse, "description": "Lookup failed."},
    },
)
async def get_document_evidence(
    document_id: str = Path(..., description="文档 UUID"),
):
    """Fetch all evidence linked to a document id."""
    try:
        normalized_id, numeric_id = _parse_document_identifier(document_id)
        logger.info("Document evidence request: {}", normalized_id or document_id)
        engine = get_graph_search_engine()
        result = engine.get_document_evidence(normalized_id)
        logger.debug("Document evidence result: {} evidence", result.total_evidence)
        payload = _inject_document_identifier(result.to_dict(), normalized_id, numeric_id)
        return EvidenceSearchResponse(data=payload)
    except Exception as e:
        logger.error("Document evidence retrieval failed: {}", e)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 实体关联分析 ====================

@router.get(
    "/association/gene/{gene_symbol}",
    response_model=EvidenceSearchResponse,
    summary="基因关联分析",
    description="分析基因的实体关联关系（变异、疾病、文献共现）。",
    responses={
        500: {"model": ErrorResponse, "description": "Analysis failed."},
    },
)
async def analyze_gene_associations(
    gene_symbol: str = Path(..., description="基因符号"),
):
    """Analyze associations for a gene symbol."""
    try:
        logger.info("Gene association request: {}", gene_symbol)
        analyzer = get_entity_association_analyzer()
        report = analyzer.analyze_gene_associations(gene_symbol)
        logger.debug("Gene association result: {} link(s)", len(report.links))
        return EvidenceSearchResponse(data=report.to_dict())
    except Exception as e:
        logger.error("Gene association analysis failed: {}", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/association/variant/{variant:path}",
    response_model=EvidenceSearchResponse,
    summary="变异关联分析",
    description="分析变异的实体关联关系。",
    responses={
        500: {"model": ErrorResponse, "description": "Analysis failed."},
    },
)
async def analyze_variant_associations(
    variant: str = Path(..., description="变异 HGVS c./p. 描述"),
):
    """Analyze associations for a variant."""
    try:
        logger.info("Variant association request: {}", variant)
        analyzer = get_entity_association_analyzer()
        report = analyzer.analyze_variant_associations(variant)
        logger.debug("Variant association result: {} link(s)", len(report.links))
        return EvidenceSearchResponse(data=report.to_dict())
    except Exception as e:
        logger.error("Variant association analysis failed: {}", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/co-occurrence/{gene_symbol}",
    response_model=EvidenceSearchResponse,
    summary="共现矩阵",
    description="获取基因相关变异的跨文献共现矩阵。",
    responses={
        500: {"model": ErrorResponse, "description": "Computation failed."},
    },
)
async def get_co_occurrence_matrix(
    gene_symbol: str = Path(..., description="基因符号"),
):
    """Build a co-occurrence matrix for a gene."""
    try:
        logger.info("Co-occurrence matrix request: {}", gene_symbol)
        analyzer = get_entity_association_analyzer()
        matrix = analyzer.build_co_occurrence_matrix(gene_symbol)
        logger.debug("Co-occurrence matrix size: {}", len(matrix))
        return EvidenceSearchResponse(data={"gene_symbol": gene_symbol, "matrix": matrix})
    except Exception as e:
        logger.error("Co-occurrence matrix failed: {}", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/evidence-chains/{gene_symbol}",
    response_model=EvidenceSearchResponse,
    summary="证据链检测",
    description="检测多文献证据链并返回链路列表。",
    responses={
        500: {"model": ErrorResponse, "description": "Detection failed."},
    },
)
async def get_evidence_chains(
    gene_symbol: str = Path(..., description="基因符号"),
    min_documents: int = Query(2, ge=1, description="最少文献数"),
):
    """Detect evidence chains across multiple documents."""
    try:
        logger.info("Evidence chain request: {}", gene_symbol)
        analyzer = get_entity_association_analyzer()
        chains = analyzer.find_evidence_chains(gene_symbol, min_documents)
        logger.debug("Evidence chains found: {}", len(chains))
        return EvidenceSearchResponse(data={"gene_symbol": gene_symbol, "chains": chains})
    except Exception as e:
        logger.error("Evidence chain detection failed: {}", e)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 证据聚合 ====================

@router.post(
    "/aggregate",
    response_model=AggregationResponse,
    summary="证据聚合",
    description=(
        "多条件证据聚合，跨文献整合 ACMG 证据链。\n"
        "请求体为 JSON，支持 gene_symbol / variant / protein_change / disease_name。"
    ),
    responses={
        422: {"model": ErrorResponse, "description": "Validation error."},
        500: {"model": ErrorResponse, "description": "Aggregation failed."},
    },
)
async def aggregate_evidence(req: EvidenceSearchRequest):
    """Aggregate evidence across documents with the same filters."""
    try:
        logger.info("Evidence aggregation request")
        eng = get_evidence_aggregation_engine()
        report = eng.aggregate_multi(
            gene_symbol=req.gene_symbol,
            variant=req.variant,
            protein_change=req.protein_change,
            disease_name=req.disease_name,
            min_confidence=req.min_confidence,
            only_valid=req.only_valid,
        )
        logger.debug("Aggregation result: {} variant(s)", len(report.variants))
        return AggregationResponse(data=report.to_dict())
    except Exception as e:
        logger.error("Evidence aggregation failed: {}", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/aggregate/gene/{gene_symbol}",
    response_model=AggregationResponse,
    summary="按基因聚合",
    description="将基因下所有变异的证据进行跨文献聚合。",
    responses={
        500: {"model": ErrorResponse, "description": "Aggregation failed."},
    },
)
async def aggregate_by_gene(
    gene_symbol: str = Path(..., description="基因符号"),
):
    """Aggregate evidence for all variants under a gene."""
    try:
        logger.info("Gene aggregation request: {}", gene_symbol)
        eng = get_evidence_aggregation_engine()
        report = eng.aggregate_by_gene(gene_symbol)
        logger.debug("Gene aggregation result: {} variant(s)", len(report.variants))
        return AggregationResponse(data=report.to_dict())
    except Exception as e:
        logger.error("Gene aggregation failed: {}", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/aggregate/variant",
    response_model=AggregationResponse,
    summary="按变异聚合",
    description="将特定变异在多篇文献中的证据进行聚合。",
    responses={
        400: {"model": ErrorResponse, "description": "Missing query parameter."},
        500: {"model": ErrorResponse, "description": "Aggregation failed."},
    },
)
async def aggregate_by_variant(
    variant: Optional[str] = Query(None, description="变异 HGVS c./p. 描述"),
    protein_change: Optional[str] = Query(None, description="蛋白变化描述"),
):
    """Aggregate evidence for a single variant or protein change."""
    if not variant and not protein_change:
        raise HTTPException(status_code=400, detail="需要提供 variant 或 protein_change")
    try:
        logger.info("Variant aggregation request")
        eng = get_evidence_aggregation_engine()
        report = eng.aggregate_by_variant(variant=variant, protein_change=protein_change)
        logger.debug("Variant aggregation result: {} variant(s)", len(report.variants))
        return AggregationResponse(data=report.to_dict())
    except Exception as e:
        logger.error("Variant aggregation failed: {}", e)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 质量监控 ====================

@router.get(
    "/quality",
    summary="证据质量监控概览（MVP已下线）",
    description="MVP 范围内 quality API 已下线；兼容旧调用返回 404。",
    responses={
        404: {"model": ErrorResponse, "description": "Quality API removed in MVP."},
    },
)
async def quality_overview(
    gene_symbol: Optional[str] = Query(None, description="可选基因过滤"),
):
    """Quality API is out of MVP scope and intentionally unavailable."""
    logger.info("Quality overview request rejected (MVP disabled)")
    raise HTTPException(status_code=404, detail="Quality API removed in MVP")


# ==================== 图数据库 ====================

@router.get(
    "/graph/stats",
    response_model=EvidenceSearchResponse,
    summary="图数据库统计",
    description="获取 Neo4j 图数据库的节点和关系统计。",
    responses={
        500: {"model": ErrorResponse, "description": "Lookup failed."},
    },
)
async def graph_statistics():
    """Return Neo4j node and relationship statistics."""
    try:
        logger.info("Graph statistics request")
        client = get_neo4j_client()
        stats = client.get_graph_statistics()
        logger.debug("Graph statistics entries: {}", len(stats))
        return EvidenceSearchResponse(data={"statistics": stats})
    except Exception as e:
        logger.error("Graph statistics failed: {}", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/sync/document/{document_id}",
    response_model=EvidenceSearchResponse,
    summary="重新同步文档",
    description="将文档的 PostgreSQL 证据重新同步到 Neo4j。",
    responses={
        500: {"model": ErrorResponse, "description": "Sync failed."},
    },
)
async def resync_document(
    document_id: str = Path(..., description="文档 UUID"),
):
    """Resync a document into Neo4j."""
    try:
        logger.info("Resync document request: {}", document_id)
        svc = get_graph_sync_service()
        result = svc.resync_document(document_id)
        logger.debug("Resync result: {}", result)
        return EvidenceSearchResponse(data=result)
    except Exception as e:
        logger.error("Document resync failed: {}", e)
        raise HTTPException(status_code=500, detail=str(e))
