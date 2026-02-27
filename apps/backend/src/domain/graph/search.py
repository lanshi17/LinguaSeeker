"""
多文档图谱搜索模块
联合 Neo4j 图数据库与 PostgreSQL 关系数据库，
基于 Variation / Gene / Protein Change 进行多文献关联图谱检索。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from loguru import logger

from src.database.neo4j_client import get_neo4j_client
from src.database.postgre_client import get_postgres_client
from src.domain.variant import get_variation_data_service, VariationDataService


# ==================== 数据结构 ====================

@dataclass
class GraphNode:
    """图谱节点"""
    node_id: str
    node_type: str  # gene / variant / document / evidence / phenotype / disease
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """图谱边"""
    source_id: str
    target_id: str
    relationship: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """搜索结果"""
    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[GraphEdge] = field(default_factory=list)
    evidence_records: List[Dict[str, Any]] = field(default_factory=list)
    document_count: int = 0
    total_evidence: int = 0
    variation: Optional[Dict[str, Any]] = None
    citations: List[Dict[str, Any]] = field(default_factory=list)
    scorecards: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "nodes": [
                {"id": n.node_id, "type": n.node_type, "label": n.label, **n.properties}
                for n in self.nodes
            ],
            "edges": [
                {"source": e.source_id, "target": e.target_id, "relationship": e.relationship, **e.properties}
                for e in self.edges
            ],
            "evidence_records": self.evidence_records,
            "document_count": self.document_count,
            "total_evidence": self.total_evidence,
        }
        if self.variation is not None:
            payload["variation"] = self.variation
        if self.citations:
            payload["citations"] = self.citations
        if self.scorecards:
            payload["scorecards"] = self.scorecards
        return payload


# ==================== 搜索引擎 ====================

class GraphSearchEngine:
    """多文档图谱搜索引擎"""

    def __init__(self) -> None:
        self._neo4j = get_neo4j_client()
        self._pg = get_postgres_client()
        self._variants: VariationDataService = get_variation_data_service()
        logger.info("GraphSearchEngine initialized")

    # -------------------- 基于变异搜索 --------------------

    def search_by_variant(
        self,
        variant: str,
        include_evidence: bool = True,
    ) -> SearchResult:
        """
        以 Variation (HGVS c./p.) 为入口检索完整子图。

        返回涉及该变异的基因、表型、疾病、证据及关联文献。
        """
        logger.info("Graph search by variant: {}", variant)
        result = SearchResult()
        seen_nodes: Set[str] = set()

        variation_id: Optional[int] = None
        if variant:
            variation = self._variants.resolve_variation(variant)
            if variation:
                variation_id = int(variation.variation_id)
                payload = self._variants.build_variation_payload(variation_id)
                result.variation = payload.get("variation")
                result.citations = payload.get("citations", [])
                result.scorecards = payload.get("scorecards", [])
        if result.variation is None:
            result.variation = {"primary_hgvs": variant}

        # 1) Neo4j 图检索
        graph_rows = self._neo4j.find_variant_evidence_graph(
            variant_hgvs_c=variant,
            variation_id=variation_id,
        )
        logger.debug("Graph rows for variant {}: {}", variant, len(graph_rows))
        for row in graph_rows:
            self._extract_nodes_edges(row, result, seen_nodes)

        # 2) PostgreSQL 补充证据记录
        if include_evidence:
            pg_records = self._pg.search_evidence_by_variant(
                variant=variant,
                clinvar_variation_id=variation_id,
            )
            logger.debug("Evidence records for variant {}: {}", variant, len(pg_records))
            for rec in pg_records:
                result.evidence_records.append(self._evidence_to_dict(rec))

        result.document_count = len({
            r.get("document_id") for r in result.evidence_records if r.get("document_id")
        })
        result.total_evidence = len(result.evidence_records)

        logger.info(
            "Variant search '{}': {} nodes, {} edges, {} evidence from {} docs",
            variant, len(result.nodes), len(result.edges),
            result.total_evidence, result.document_count,
        )
        return result

    # -------------------- 基于基因搜索 --------------------

    def search_by_gene(
        self,
        gene_symbol: str,
        include_evidence: bool = True,
    ) -> SearchResult:
        """以 Gene 为入口检索该基因所有变异及关联证据。"""
        logger.info("Graph search by gene: {}", gene_symbol)
        result = SearchResult()
        seen_nodes: Set[str] = set()

        # Neo4j
        graph_rows = self._neo4j.find_gene_related_variants(gene_symbol)
        logger.debug("Graph rows for gene {}: {}", gene_symbol, len(graph_rows))
        for row in graph_rows:
            gene_id = f"gene:{row.get('gene', '')}"
            variant_id = f"variant:{row.get('variant', '')}"

            if gene_id not in seen_nodes:
                result.nodes.append(GraphNode(gene_id, "gene", row.get("gene", "")))
                seen_nodes.add(gene_id)
            if variant_id not in seen_nodes and row.get("variant"):
                result.nodes.append(GraphNode(
                    variant_id, "variant", row.get("variant", ""),
                    {"protein_change": row.get("protein_change")},
                ))
                seen_nodes.add(variant_id)
                result.edges.append(GraphEdge(gene_id, variant_id, "HAS_VARIANT"))

            if row.get("document_id"):
                doc_id = f"doc:{row['document_id']}"
                if doc_id not in seen_nodes:
                    result.nodes.append(GraphNode(
                        doc_id, "document", row.get("doc_title", str(row["document_id"])),
                    ))
                    seen_nodes.add(doc_id)

        # PostgreSQL
        if include_evidence:
            pg_records = self._pg.search_evidence_by_gene(gene_symbol)
            logger.debug("Evidence records for gene {}: {}", gene_symbol, len(pg_records))
            for rec in pg_records:
                result.evidence_records.append(self._evidence_to_dict(rec))

        result.document_count = len({
            r.get("document_id") for r in result.evidence_records if r.get("document_id")
        })
        result.total_evidence = len(result.evidence_records)
        return result

    # -------------------- 多条件联合搜索 --------------------

    def search_multi(
        self,
        gene_symbol: Optional[str] = None,
        variant: Optional[str] = None,
        protein_change: Optional[str] = None,
        disease_name: Optional[str] = None,
        min_confidence: Optional[float] = None,
        only_valid: bool = False,
    ) -> SearchResult:
        """
        多条件联合图谱检索。
        同时查询 Neo4j 图关系和 PostgreSQL 结构化证据。
        """
        logger.info("Graph multi-search requested")
        result = SearchResult()
        seen_nodes: Set[str] = set()

        # Neo4j 多文档证据
        graph_rows = self._neo4j.find_multi_document_evidence(
            gene_symbol=gene_symbol,
            variant_hgvs_c=variant,
            protein_change=protein_change,
        )
        logger.debug("Graph rows for multi-search: {}", len(graph_rows))
        for row in graph_rows:
            self._build_multi_nodes(row, result, seen_nodes)

        # PostgreSQL 多条件搜索
        pg_records = self._pg.search_evidence_multi(
            gene_symbol=gene_symbol,
            variant=variant,
            protein_change=protein_change,
            disease_name=disease_name,
            min_confidence=min_confidence,
            only_valid=only_valid,
        )
        logger.debug("Evidence records for multi-search: {}", len(pg_records))
        for rec in pg_records:
            result.evidence_records.append(self._evidence_to_dict(rec))

        result.document_count = len({
            r.get("document_id") for r in result.evidence_records if r.get("document_id")
        })
        result.total_evidence = len(result.evidence_records)

        logger.info(
            "Multi-search: gene={}, variant={}, protein={} → {} evidence from {} docs",
            gene_symbol, variant, protein_change,
            result.total_evidence, result.document_count,
        )
        return result

    # -------------------- 文档级证据检索 --------------------

    def get_document_evidence(self, document_id: str) -> SearchResult:
        """获取某文档的所有证据及其图谱关系"""
        normalized_id = str(document_id).strip()
        logger.info("Fetching document evidence: {}", normalized_id)
        result = SearchResult()
        pg_records = self._pg.get_evidence_for_document(normalized_id)
        logger.debug("Document {} evidence records: {}", normalized_id, len(pg_records))
        for rec in pg_records:
            result.evidence_records.append(self._evidence_to_dict(rec))
        result.document_count = 1 if pg_records else 0
        result.total_evidence = len(pg_records)
        return result

    # ==================== 内部辅助 ====================

    def _extract_nodes_edges(
        self,
        row: Dict[str, Any],
        result: SearchResult,
        seen: Set[str],
    ) -> None:
        """从 Neo4j 图查询行中提取节点和边"""
        node_mappings = [
            ("v", "variant", lambda r: r.get("v", {}).get("hgvs_c", "")),
            ("g", "gene", lambda r: r.get("g", {}).get("symbol", "")),
            ("p", "phenotype", lambda r: r.get("p", {}).get("description", "")),
            ("e", "evidence", lambda r: r.get("e", {}).get("evidence_id", "")),
            ("doc", "document", lambda r: str(r.get("doc", {}).get("document_id", ""))),
        ]

        created_ids: Dict[str, str] = {}
        for key, ntype, label_fn in node_mappings:
            node_data = row.get(key)
            if not node_data:
                continue
            label = label_fn(row)
            nid = f"{ntype}:{label}"
            created_ids[key] = nid
            if nid not in seen:
                props = dict(node_data) if isinstance(node_data, dict) else {}
                result.nodes.append(GraphNode(nid, ntype, label, props))
                seen.add(nid)

        # 建立边
        edge_pairs = [
            ("g", "v", "HAS_VARIANT"),
            ("v", "p", "HAS_PHENOTYPE"),
            ("v", "e", "HAS_EVIDENCE"),
            ("e", "doc", "FROM_DOCUMENT"),
        ]
        for src_key, tgt_key, rel in edge_pairs:
            if src_key in created_ids and tgt_key in created_ids:
                result.edges.append(GraphEdge(created_ids[src_key], created_ids[tgt_key], rel))

    def _build_multi_nodes(
        self,
        row: Dict[str, Any],
        result: SearchResult,
        seen: Set[str],
    ) -> None:
        """从多文档图谱查询结果构建节点"""
        fields = [
            ("gene", "gene"), ("variant", "variant"),
            ("protein_change", "variant_protein"),
            ("evidence_id", "evidence"), ("document_id", "document"),
            ("phenotype", "phenotype"), ("disease", "disease"),
        ]
        created: Dict[str, str] = {}
        for field_name, ntype in fields:
            val = row.get(field_name)
            if not val:
                continue
            nid = f"{ntype}:{val}"
            created[field_name] = nid
            if nid not in seen:
                result.nodes.append(GraphNode(nid, ntype, str(val)))
                seen.add(nid)

        # 边
        if "gene" in created and "variant" in created:
            result.edges.append(GraphEdge(created["gene"], created["variant"], "HAS_VARIANT"))
        if "variant" in created and "evidence_id" in created:
            result.edges.append(GraphEdge(created["variant"], created["evidence_id"], "HAS_EVIDENCE"))
        if "evidence_id" in created and "document_id" in created:
            result.edges.append(GraphEdge(created["evidence_id"], created["document_id"], "FROM_DOCUMENT"))
        if "gene" in created and "disease" in created:
            result.edges.append(GraphEdge(created["disease"], created["gene"], "ASSOCIATED_GENE"))

    @staticmethod
    def _evidence_to_dict(record) -> Dict[str, Any]:
        """将 EvidenceRecord ORM 对象转换为字典"""
        if hasattr(record, "__dict__"):
            d = {
                k: v for k, v in record.__dict__.items()
                if not k.startswith("_")
            }
            doc_id = d.get("document_id")
            if isinstance(doc_id, UUID):
                d["document_id"] = str(doc_id)
            # 序列化 datetime
            for k in ("created_at", "updated_at"):
                if k in d and d[k] is not None:
                    d[k] = d[k].isoformat()
            return d
        return dict(record) if record else {}


# ==================== 工厂 ====================

_search_engine: Optional[GraphSearchEngine] = None


def get_graph_search_engine() -> GraphSearchEngine:
    global _search_engine
    if _search_engine is None:
        _search_engine = GraphSearchEngine()
    return _search_engine
