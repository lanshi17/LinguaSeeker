"""
图数据同步模块
在 Pipeline 产出证据后，将结构化数据同步写入 Neo4j 图数据库和 PostgreSQL，
保持两侧数据的一致性。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from src.database.neo4j_client import get_neo4j_client, Neo4jClient
from src.database.postgre_client import get_postgres_client, PostgresClient


class GraphSyncService:
    """Neo4j ↔ PostgreSQL 证据同步服务"""

    def __init__(self) -> None:
        self._neo4j: Neo4jClient = get_neo4j_client()
        self._pg: PostgresClient = get_postgres_client()
        logger.info("GraphSyncService initialized")

    # ==================== 核心同步入口 ====================

    def sync_evidence(
        self,
        document_id: str,
        evidence_output: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        将一次 Pipeline 运行的证据结果同步到 Neo4j 和 PostgreSQL。

        参数:
            document_id:     PostgreSQL documents 表中的文档 ID
            evidence_output: EvidenceOutput.dict() 格式

        返回:
            {"pg_evidence_id": int, "neo4j_synced": bool}
        """
        logger.info("Syncing evidence for document {}", document_id)
        extracted = evidence_output.get("extracted_fields") or {}
        ps3 = evidence_output.get("ps3_evidence") or {}
        classification = evidence_output.get("evidence_classification", "")
        overall_conf = evidence_output.get("overall_confidence", 0.0)
        acmg_levels = evidence_output.get("acmg_evidence_levels") or []
        strength = evidence_output.get("final_evidence_strength", "")

        # 提取各字段
        gene_info = extracted.get("gene") or {}
        variant_info = extracted.get("variant") or {}
        transcript_info = extracted.get("transcript_id") or {}
        ref_genome_info = extracted.get("reference_genome_version") or {}
        disease_info = extracted.get("disease_chpo") or extracted.get("disease_icd10") or {}
        species_info = extracted.get("species") or {}
        phenotype_info = extracted.get("phenotype") or {}
        control_info = extracted.get("negative_positive_control") or {}

        gene_symbol = gene_info.get("symbol", "")
        variant_hgvs_c = variant_info.get("hgvs_c", "")
        variant_hgvs_p = variant_info.get("hgvs_p", "")
        protein_change = variant_hgvs_p  # 同义
        transcript_id = transcript_info.get("transcript_id", "")
        ref_genome = ref_genome_info.get("version", "")
        disease_name = disease_info.get("disease_name", "")
        icd10 = disease_info.get("icd10_code", "")
        species = species_info.get("species_name", "")
        phenotype_desc = phenotype_info.get("phenotype_description", "")

        is_valid = "true" if overall_conf >= 85.0 else "false"

        # 1) --- PostgreSQL ---
        pg_record = self._pg.create_evidence_record(
            document_id=document_id,
            gene_symbol=gene_symbol or None,
            variant_hgvs_c=variant_hgvs_c or None,
            variant_hgvs_p=variant_hgvs_p or None,
            protein_change=protein_change or None,
            transcript_id=transcript_id or None,
            reference_genome=ref_genome or None,
            disease_name=disease_name or None,
            icd10_code=icd10 or None,
            species=species or None,
            phenotype=phenotype_desc or None,
            evidence_strength=strength or None,
            evidence_classification=classification or None,
            overall_confidence=overall_conf,
            is_valid=is_valid,
            acmg_levels={"levels": acmg_levels} if acmg_levels else None,
            extracted_fields=extracted or None,
            ps3_evidence=ps3 or None,
        )
        evidence_id = pg_record.evidence_id
        logger.info("PostgreSQL evidence_record created: id={}", evidence_id)

        # 2) --- Neo4j ---
        neo4j_ok = False
        try:
            self._sync_to_neo4j(
                document_id=document_id,
                evidence_id=str(evidence_id),
                gene_symbol=gene_symbol,
                variant_hgvs_c=variant_hgvs_c,
                variant_hgvs_p=variant_hgvs_p,
                transcript_id=transcript_id,
                disease_name=disease_name,
                icd10=icd10,
                phenotype_desc=phenotype_desc,
                species=species,
                strength=strength,
                classification=classification,
                overall_conf=overall_conf,
            )
            neo4j_ok = True
        except Exception as e:
            logger.error("Neo4j sync failed for evidence {}: {}", evidence_id, e)
        logger.info("Sync complete for document {} (neo4j_ok={})", document_id, neo4j_ok)

        return {
            "pg_evidence_id": evidence_id,
            "neo4j_synced": neo4j_ok,
        }

    # ==================== Neo4j 写入 ====================

    def _sync_to_neo4j(
        self,
        document_id: str,
        evidence_id: str,
        gene_symbol: str,
        variant_hgvs_c: str,
        variant_hgvs_p: str,
        transcript_id: str,
        disease_name: str,
        icd10: str,
        phenotype_desc: str,
        species: str,
        strength: str,
        classification: str,
        overall_conf: float,
    ) -> None:
        """将实体和关系写入 Neo4j"""
        logger.debug("Writing entities to Neo4j for evidence {}", evidence_id)
        neo = self._neo4j

        # 文档节点
        neo.upsert_document(str(document_id), properties={"document_id": str(document_id)})

        # 基因节点
        if gene_symbol:
            neo.upsert_gene(gene_symbol)

        # 变异节点
        if variant_hgvs_c:
            neo.upsert_variant(variant_hgvs_c, hgvs_p=variant_hgvs_p)
            if gene_symbol:
                neo.link_gene_variant(gene_symbol, variant_hgvs_c)
            # 文档提及变异
            neo.link_document_entity(str(document_id), "Variant", "hgvs_c", variant_hgvs_c)

        # 转录本
        if transcript_id and gene_symbol:
            neo.upsert_transcript(transcript_id)
            neo.link_gene_transcript(gene_symbol, transcript_id)

        # 疾病
        if disease_name:
            neo.upsert_disease(disease_name, icd10_code=icd10 or None)
            if gene_symbol:
                neo.link_disease_gene(disease_name, gene_symbol)
            neo.link_document_entity(str(document_id), "Disease", "name", disease_name)

        # 表型
        if phenotype_desc:
            neo.upsert_phenotype(phenotype_desc)
            if variant_hgvs_c:
                neo.link_variant_phenotype(variant_hgvs_c, phenotype_desc)
            neo.link_document_entity(str(document_id), "Phenotype", "description", phenotype_desc)

        # 物种
        if species:
            neo.upsert_species(species)

        # 证据节点
        neo.upsert_evidence(
            evidence_id,
            evidence_strength=strength,
            classification=classification,
            confidence=overall_conf,
        )
        if variant_hgvs_c:
            neo.link_variant_evidence(variant_hgvs_c, evidence_id)
        neo.link_evidence_document(evidence_id, str(document_id))

        # 基因节点 → 文档提及
        if gene_symbol:
            neo.link_document_entity(str(document_id), "Gene", "symbol", gene_symbol)

    # ==================== 批量同步 ====================

    def sync_batch(
        self,
        document_id: str,
        evidence_outputs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """批量同步多条证据（同一文档的多条提取结果）"""
        logger.info("Batch syncing {} evidence item(s) for document {}", len(evidence_outputs), document_id)
        results = []
        for idx, ev in enumerate(evidence_outputs):
            try:
                r = self.sync_evidence(document_id, ev)
                results.append(r)
            except Exception as e:
                logger.error("Batch sync failed at index {}: {}", idx, e)
                results.append({"pg_evidence_id": None, "neo4j_synced": False, "error": str(e)})
        return results

    # ==================== 重新同步 ====================

    def resync_document(self, document_id: str) -> Dict[str, Any]:
        """
        从 PostgreSQL 重新同步某文档的所有证据到 Neo4j。
        用于修复 Neo4j 数据不一致。
        """
        logger.info("Resyncing document {}", document_id)
        records = self._pg.get_evidence_for_document(document_id)
        synced = 0
        failed = 0
        for rec in records:
            try:
                self._sync_to_neo4j(
                    document_id=document_id,
                    evidence_id=str(rec.evidence_id),
                    gene_symbol=getattr(rec, "gene_symbol", "") or "",
                    variant_hgvs_c=getattr(rec, "variant_hgvs_c", "") or "",
                    variant_hgvs_p=getattr(rec, "variant_hgvs_p", "") or "",
                    transcript_id=getattr(rec, "transcript_id", "") or "",
                    disease_name=getattr(rec, "disease_name", "") or "",
                    icd10=getattr(rec, "icd10_code", "") or "",
                    phenotype_desc=getattr(rec, "phenotype", "") or "",
                    species=getattr(rec, "species", "") or "",
                    strength=getattr(rec, "evidence_strength", "") or "",
                    classification=getattr(rec, "evidence_classification", "") or "",
                    overall_conf=getattr(rec, "overall_confidence", 0.0) or 0.0,
                )
                synced += 1
            except Exception as e:
                logger.error("Resync failed for evidence {}: {}", rec.evidence_id, e)
                failed += 1

        logger.info("Resync document {}: {}/{} ok, {} failed", document_id, synced, len(records), failed)
        return {"total": len(records), "synced": synced, "failed": failed}


# ==================== 工厂 ====================

_sync_service: Optional[GraphSyncService] = None


def get_graph_sync_service() -> GraphSyncService:
    global _sync_service
    if _sync_service is None:
        _sync_service = GraphSyncService()
    return _sync_service
