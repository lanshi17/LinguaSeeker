"""
实体关联分析服务
分析 Gene / Variant / Disease / Phenotype 之间的关联关系，
发现跨文献的实体共现模式和证据链。

从 dtos.py 拆分而来 —— 仅保留业务逻辑，数据结构由 dtos.py 提供。
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from loguru import logger

from src.infrastructure.neo4j import get_neo4j_client, Neo4jClient
from src.infrastructure.postgres import get_postgres_client, PostgresClient
from src.domain.evidence.dtos import AssociationReport, EntityLink


class EntityAssociationAnalyzer:
    """
    实体关联分析器。

    职责:
    - 基因关联分析 (变异、疾病、文献共现)
    - 变异关联分析 (基因、表型、文献)
    - 跨文献共现矩阵构建
    - 多文献证据链检测
    """

    def __init__(
        self,
        neo4j: Optional[Neo4jClient] = None,
        pg: Optional[PostgresClient] = None,
    ) -> None:
        self._neo4j = neo4j or get_neo4j_client()
        self._pg = pg or get_postgres_client()
        logger.info("EntityAssociationAnalyzer initialized")

    # -------------------- 基因关联分析 --------------------

    def analyze_gene_associations(self, gene_symbol: str) -> AssociationReport:
        """
        分析基因关联关系：
        - 该基因涉及的所有变异
        - 关联疾病
        - 跨文献共现
        """
        logger.info("Analyzing gene associations: {}", gene_symbol)
        report = AssociationReport("gene", gene_symbol)

        # 从 Neo4j 获取图关联
        variant_rows = self._neo4j.find_gene_related_variants(gene_symbol)
        logger.debug("Variant rows for gene {}: {}", gene_symbol, len(variant_rows))

        # 变异关联
        variant_docs: Dict[str, List[str]] = defaultdict(list)
        for row in variant_rows:
            v = row.get("variant", "")
            doc = row.get("document_id")
            if v:
                variant_docs[v].append(str(doc) if doc else "")

        for v, docs in variant_docs.items():
            real_docs = [d for d in docs if d]
            report.links.append(EntityLink(
                source_type="gene",
                source_id=gene_symbol,
                target_type="variant",
                target_id=v,
                relationship="HAS_VARIANT",
                co_occurrence_count=len(real_docs),
                document_ids=real_docs,
                confidence=min(100.0, len(real_docs) * 25.0),
            ))

        # 疾病关联 (Neo4j)
        disease_rows = self._neo4j.run_query(
            """
            MATCH (d:Disease)-[:ASSOCIATED_GENE]->(g:Gene {symbol: $gene})
            OPTIONAL MATCH (doc:Document)-[:MENTIONS]->(g)
            RETURN d.name AS disease, collect(DISTINCT doc.document_id) AS doc_ids
            """,
            {"gene": gene_symbol},
        )
        for row in disease_rows:
            disease = row.get("disease", "")
            docs = [str(d) for d in (row.get("doc_ids") or []) if d]
            report.links.append(EntityLink(
                source_type="gene",
                source_id=gene_symbol,
                target_type="disease",
                target_id=disease,
                relationship="ASSOCIATED_GENE",
                co_occurrence_count=len(docs),
                document_ids=docs,
                confidence=min(100.0, len(docs) * 20.0),
            ))

        # PostgreSQL 证据统计
        pg_records = self._pg.search_evidence_by_gene(gene_symbol)
        logger.debug("Evidence records for gene {}: {}", gene_symbol, len(pg_records))
        evidence_by_variant: Dict[str, int] = defaultdict(int)
        for rec in pg_records:
            key = getattr(rec, "variant_hgvs_c", "") or ""
            evidence_by_variant[key] += 1

        report.summary = {
            "total_variants": len(variant_docs),
            "total_documents": len({d for docs in variant_docs.values() for d in docs if d}),
            "total_evidence_records": len(pg_records),
            "evidence_per_variant": dict(evidence_by_variant),
        }

        logger.info(
            "Gene association '{}': {} variants, {} links",
            gene_symbol, len(variant_docs), len(report.links),
        )
        return report

    # -------------------- 变异关联分析 --------------------

    def analyze_variant_associations(self, variant_hgvs: str) -> AssociationReport:
        """分析变异的所有关联：基因、表型、疾病、文献"""
        logger.info("Analyzing variant associations: {}", variant_hgvs)
        report = AssociationReport("variant", variant_hgvs)

        graph_rows = self._neo4j.find_variant_evidence_graph(variant_hgvs)
        logger.debug("Graph rows for variant {}: {}", variant_hgvs, len(graph_rows))

        seen_genes: Set[str] = set()
        seen_phenotypes: Set[str] = set()
        doc_ids: List[str] = []

        for row in graph_rows:
            g = row.get("g")
            p = row.get("p")
            doc = row.get("doc")

            if g and isinstance(g, dict):
                gene = g.get("symbol", "")
                if gene and gene not in seen_genes:
                    seen_genes.add(gene)
                    report.links.append(EntityLink(
                        source_type="variant", source_id=variant_hgvs,
                        target_type="gene", target_id=gene,
                        relationship="BELONGS_TO_GENE",
                    ))

            if p and isinstance(p, dict):
                pheno = p.get("description", "")
                if pheno and pheno not in seen_phenotypes:
                    seen_phenotypes.add(pheno)
                    report.links.append(EntityLink(
                        source_type="variant", source_id=variant_hgvs,
                        target_type="phenotype", target_id=pheno,
                        relationship="HAS_PHENOTYPE",
                    ))

            if doc and isinstance(doc, dict):
                did = str(doc.get("document_id", ""))
                if did:
                    doc_ids.append(did)

        # 文献关联
        unique_docs = list(set(doc_ids))
        for did in unique_docs:
            report.links.append(EntityLink(
                source_type="variant", source_id=variant_hgvs,
                target_type="document", target_id=did,
                relationship="MENTIONED_IN",
            ))

        # PostgreSQL 补充
        pg_records = self._pg.search_evidence_by_variant(variant=variant_hgvs)
        logger.debug("Evidence records for variant {}: {}", variant_hgvs, len(pg_records))

        report.summary = {
            "related_genes": list(seen_genes),
            "related_phenotypes": list(seen_phenotypes),
            "document_count": len(unique_docs),
            "evidence_count": len(pg_records),
        }
        return report

    # -------------------- 共现矩阵 --------------------

    def build_co_occurrence_matrix(self, gene_symbol: str) -> Dict[str, Dict[str, int]]:
        """
        构建基因相关变异的跨文献共现矩阵。
        行列 = 变异ID，值 = 两变异共同出现的文献数。
        """
        logger.info("Building co-occurrence matrix for gene: {}", gene_symbol)
        rows = self._neo4j.run_query(
            """
            MATCH (g:Gene {symbol: $gene})-[:HAS_VARIANT]->(v:Variant)
            OPTIONAL MATCH (doc:Document)-[:MENTIONS]->(v)
            RETURN v.hgvs_c AS variant, collect(DISTINCT doc.document_id) AS doc_ids
            """,
            {"gene": gene_symbol},
        )

        variant_docs: Dict[str, Set[str]] = {}
        for row in rows:
            v = row.get("variant", "")
            docs = {str(d) for d in (row.get("doc_ids") or []) if d}
            if v and docs:
                variant_docs[v] = docs
        logger.debug("Co-occurrence variants for {}: {}", gene_symbol, len(variant_docs))

        variants = sorted(variant_docs.keys())
        matrix: Dict[str, Dict[str, int]] = {}
        for v1 in variants:
            matrix[v1] = {}
            for v2 in variants:
                matrix[v1][v2] = len(variant_docs[v1] & variant_docs[v2])

        return matrix

    # -------------------- 证据链检测 --------------------

    def find_evidence_chains(
        self,
        gene_symbol: str,
        min_documents: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        检测多文献证据链：
        找到至少在 min_documents 篇文献中被证实的变异-基因-疾病路径。
        """
        logger.info("Finding evidence chains for gene {} (min docs {})", gene_symbol, min_documents)
        rows = self._neo4j.run_query(
            """
            MATCH (g:Gene {symbol: $gene})-[:HAS_VARIANT]->(v:Variant)
            MATCH (v)-[:HAS_EVIDENCE]->(e:Evidence)-[:FROM_DOCUMENT]->(doc:Document)
            OPTIONAL MATCH (d:Disease)-[:ASSOCIATED_GENE]->(g)
            WITH g, v, d, collect(DISTINCT doc.document_id) AS doc_ids,
                 collect(DISTINCT e.evidence_strength) AS strengths
            WHERE size(doc_ids) >= $min_docs
            RETURN g.symbol AS gene, v.hgvs_c AS variant, v.hgvs_p AS protein_change,
                   d.name AS disease, doc_ids, strengths
            ORDER BY size(doc_ids) DESC
            """,
            {"gene": gene_symbol, "min_docs": min_documents},
        )

        chains = []
        for row in rows:
            chains.append({
                "gene": row.get("gene"),
                "variant": row.get("variant"),
                "protein_change": row.get("protein_change"),
                "disease": row.get("disease"),
                "document_count": len(row.get("doc_ids", [])),
                "document_ids": [str(d) for d in row.get("doc_ids", [])],
                "evidence_strengths": row.get("strengths", []),
            })

        logger.info(
            "Evidence chains for '{}': {} chains (min {} docs)",
            gene_symbol, len(chains), min_documents,
        )
        return chains


# ==================== 单例工厂 ====================

_analyzer: Optional[EntityAssociationAnalyzer] = None


def get_entity_association_analyzer() -> EntityAssociationAnalyzer:
    """获取 EntityAssociationAnalyzer 单例。"""
    global _analyzer
    if _analyzer is None:
        _analyzer = EntityAssociationAnalyzer()
    return _analyzer
