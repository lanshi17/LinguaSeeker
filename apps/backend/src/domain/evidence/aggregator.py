"""
证据聚合引擎
跨文献 ACMG 证据链聚合与报告生成。
将多篇文献的分散证据整合为统一的变异级评估。
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from src.infrastructure.postgres import get_postgres_client
from src.domain.enums import (
    EVIDENCE_VALIDITY_THRESHOLD,
    EvidenceClassification,
    EvidenceStrength,
    SCORE_CLASSIFICATION_MAP,
)
from src.domain.evidence.classifier import (
    EvidenceClassifier,
    _lookup_threshold,
    strength_to_acmg_levels,
)


# ==================== 数据结构 ====================

@dataclass
class AggregatedVariantEvidence:
    """变异级聚合证据"""
    gene_symbol: str
    variant_hgvs_c: Optional[str] = None
    variant_hgvs_p: Optional[str] = None
    protein_change: Optional[str] = None

    # 聚合统计
    document_count: int = 0
    evidence_count: int = 0
    valid_evidence_count: int = 0

    # 综合评分
    max_confidence: float = 0.0
    mean_confidence: float = 0.0
    weighted_confidence: float = 0.0
    consensus_classification: str = ""
    consensus_strength: str = ""
    consensus_acmg_levels: List[str] = field(default_factory=list)

    # 详细记录
    evidence_records: List[Dict[str, Any]] = field(default_factory=list)
    strength_distribution: Dict[str, int] = field(default_factory=dict)
    classification_distribution: Dict[str, int] = field(default_factory=dict)
    document_ids: List[str] = field(default_factory=list)

    # 质量指标
    concordance_rate: float = 0.0  # 文献间一致率
    quality_grade: str = ""  # A/B/C/D

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gene_symbol": self.gene_symbol,
            "variant_hgvs_c": self.variant_hgvs_c,
            "variant_hgvs_p": self.variant_hgvs_p,
            "protein_change": self.protein_change,
            "document_count": self.document_count,
            "evidence_count": self.evidence_count,
            "valid_evidence_count": self.valid_evidence_count,
            "max_confidence": self.max_confidence,
            "mean_confidence": round(self.mean_confidence, 2),
            "weighted_confidence": round(self.weighted_confidence, 2),
            "consensus_classification": self.consensus_classification,
            "consensus_strength": self.consensus_strength,
            "consensus_acmg_levels": self.consensus_acmg_levels,
            "strength_distribution": self.strength_distribution,
            "classification_distribution": self.classification_distribution,
            "concordance_rate": round(self.concordance_rate, 2),
            "quality_grade": self.quality_grade,
            "document_ids": self.document_ids,
        }


@dataclass
class AggregationReport:
    """聚合报告"""
    query_type: str  # "gene" / "variant" / "multi"
    query_params: Dict[str, Any] = field(default_factory=dict)
    variants: List[AggregatedVariantEvidence] = field(default_factory=list)
    overall_stats: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": {"type": self.query_type, "params": self.query_params},
            "variants": [v.to_dict() for v in self.variants],
            "overall_stats": self.overall_stats,
        }


# ==================== 聚合引擎 ====================

class EvidenceAggregationEngine:
    """证据聚合引擎"""

    def __init__(self) -> None:
        self._pg = get_postgres_client()
        logger.info("EvidenceAggregationEngine initialized")

    # -------------------- 按基因聚合 --------------------

    def aggregate_by_gene(self, gene_symbol: str) -> AggregationReport:
        """将基因下所有变异的证据进行聚合"""
        logger.info("Aggregating evidence by gene: {}", gene_symbol)
        records = self._pg.search_evidence_by_gene(gene_symbol, limit=500)
        logger.debug("Fetched {} record(s) for gene {}", len(records), gene_symbol)
        report = AggregationReport("gene", {"gene_symbol": gene_symbol})

        # 按变异分组
        groups = self._group_records_by_variant(records)
        for key, recs in groups.items():
            agg = self._aggregate_variant_group(gene_symbol, key, recs)
            report.variants.append(agg)

        report.overall_stats = self._compute_overall_stats(report.variants)
        logger.info(
            "Gene aggregation '{}': {} variants, {} total evidence",
            gene_symbol, len(report.variants), report.overall_stats.get("total_evidence", 0),
        )
        return report

    # -------------------- 按变异聚合 --------------------

    def aggregate_by_variant(
        self,
        variant: Optional[str] = None,
        protein_change: Optional[str] = None,
    ) -> AggregationReport:
        """将特定变异在多篇文献中的证据进行聚合"""
        logger.info("Aggregating evidence by variant: {} protein: {}", variant, protein_change)
        records = self._pg.search_evidence_by_variant(
            variant=variant, protein_change=protein_change, limit=200,
        )
        logger.debug("Fetched {} record(s) for variant aggregation", len(records))
        report = AggregationReport("variant", {"variant": variant, "protein_change": protein_change})

        if records:
            gene = getattr(records[0], "gene_symbol", "") or ""
            key = (
                getattr(records[0], "variant_hgvs_c", variant) or variant or "",
                getattr(records[0], "variant_hgvs_p", "") or "",
            )
            agg = self._aggregate_variant_group(gene, key, records)
            report.variants.append(agg)

        report.overall_stats = self._compute_overall_stats(report.variants)
        return report

    # -------------------- 按多条件聚合 --------------------

    def aggregate_multi(
        self,
        gene_symbol: Optional[str] = None,
        variant: Optional[str] = None,
        protein_change: Optional[str] = None,
        disease_name: Optional[str] = None,
        min_confidence: Optional[float] = None,
        only_valid: bool = False,
    ) -> AggregationReport:
        """多条件聚合"""
        logger.info("Aggregating evidence with multi filters")
        records = self._pg.search_evidence_multi(
            gene_symbol=gene_symbol,
            variant=variant,
            protein_change=protein_change,
            disease_name=disease_name,
            min_confidence=min_confidence,
            only_valid=only_valid,
            limit=500,
        )
        logger.debug("Fetched {} record(s) for multi aggregation", len(records))
        report = AggregationReport("multi", {
            "gene_symbol": gene_symbol, "variant": variant,
            "protein_change": protein_change, "disease_name": disease_name,
        })

        groups = self._group_records_by_variant(records)
        for key, recs in groups.items():
            gene = gene_symbol or (getattr(recs[0], "gene_symbol", "") if recs else "")
            agg = self._aggregate_variant_group(gene or "", key, recs)
            report.variants.append(agg)

        report.overall_stats = self._compute_overall_stats(report.variants)
        return report

    # -------------------- 质量监控概览 --------------------

    def quality_overview(self, gene_symbol: Optional[str] = None) -> Dict[str, Any]:
        """证据质量监控概览"""
        logger.info("Building quality overview")
        if gene_symbol:
            records = self._pg.search_evidence_by_gene(gene_symbol, limit=1000)
        else:
            records = self._pg.search_evidence_multi(limit=1000)
        logger.debug("Quality overview record count: {}", len(records))

        total = len(records)
        valid_count = sum(1 for r in records if getattr(r, "is_valid", "") == "true")
        confidences = [getattr(r, "overall_confidence", 0) or 0 for r in records]

        strength_dist: Dict[str, int] = defaultdict(int)
        class_dist: Dict[str, int] = defaultdict(int)
        for r in records:
            s = getattr(r, "evidence_strength", "unknown") or "unknown"
            c = getattr(r, "evidence_classification", "unknown") or "unknown"
            strength_dist[s] += 1
            class_dist[c] += 1

        return {
            "total_evidence": total,
            "valid_evidence": valid_count,
            "invalid_evidence": total - valid_count,
            "validity_rate": round(valid_count / total * 100, 1) if total else 0,
            "avg_confidence": round(sum(confidences) / len(confidences), 1) if confidences else 0,
            "max_confidence": max(confidences) if confidences else 0,
            "min_confidence": min(confidences) if confidences else 0,
            "strength_distribution": dict(strength_dist),
            "classification_distribution": dict(class_dist),
        }

    # ==================== 内部方法 ====================

    @staticmethod
    def _group_records_by_variant(records) -> Dict[Tuple[str, str], list]:
        """按 (hgvs_c, hgvs_p) 分组"""
        groups: Dict[Tuple[str, str], list] = defaultdict(list)
        for rec in records:
            key = (
                getattr(rec, "variant_hgvs_c", "") or "",
                getattr(rec, "variant_hgvs_p", "") or "",
            )
            groups[key].append(rec)
        return groups

    def _aggregate_variant_group(
        self,
        gene_symbol: str,
        key: Tuple[str, str],
        records: list,
    ) -> AggregatedVariantEvidence:
        """对同一变异的多条记录进行聚合"""
        logger.debug("Aggregating variant group {} with {} record(s)", key, len(records))
        hgvs_c, hgvs_p = key
        agg = AggregatedVariantEvidence(
            gene_symbol=gene_symbol,
            variant_hgvs_c=hgvs_c or None,
            variant_hgvs_p=hgvs_p or None,
        )

        confidences: List[float] = []
        strength_counts: Dict[str, int] = defaultdict(int)
        class_counts: Dict[str, int] = defaultdict(int)
        doc_ids: set = set()

        for rec in records:
            conf = getattr(rec, "overall_confidence", 0) or 0.0
            confidences.append(conf)

            strength = getattr(rec, "evidence_strength", "") or ""
            classification = getattr(rec, "evidence_classification", "") or ""
            doc_id = getattr(rec, "document_id", None)
            protein = getattr(rec, "protein_change", "")

            if strength:
                strength_counts[strength] += 1
            if classification:
                class_counts[classification] += 1
            if doc_id:
                doc_ids.add(str(doc_id))
            if protein and not agg.protein_change:
                agg.protein_change = protein

            is_valid = getattr(rec, "is_valid", "") == "true"
            if is_valid:
                agg.valid_evidence_count += 1

            # 转换为字典存入详细记录
            rec_dict = {}
            for attr in ("evidence_id", "document_id", "evidence_strength",
                         "evidence_classification", "overall_confidence",
                         "is_valid"):
                value = getattr(rec, attr, None)
                if attr == "document_id" and value is not None:
                    value = str(value)
                rec_dict[attr] = value
            agg.evidence_records.append(rec_dict)

        agg.evidence_count = len(records)
        agg.document_count = len(doc_ids)
        agg.document_ids = sorted(doc_ids)
        agg.strength_distribution = dict(strength_counts)
        agg.classification_distribution = dict(class_counts)

        if confidences:
            agg.max_confidence = max(confidences)
            agg.mean_confidence = sum(confidences) / len(confidences)
            # 加权：有效证据权重更高
            weights = [1.5 if getattr(r, "is_valid", "") == "true" else 1.0 for r in records]
            agg.weighted_confidence = (
                sum(c * w for c, w in zip(confidences, weights)) / sum(weights)
            )

        # 共识分类：取出现次数最多的
        if class_counts:
            agg.consensus_classification = max(class_counts, key=class_counts.get)  # type: ignore
        else:
            agg.consensus_classification = _lookup_threshold(
                agg.weighted_confidence, SCORE_CLASSIFICATION_MAP,
            )

        if strength_counts:
            agg.consensus_strength = max(strength_counts, key=strength_counts.get)  # type: ignore
        agg.consensus_acmg_levels = strength_to_acmg_levels(agg.consensus_strength)

        # 一致率
        if class_counts and len(records) > 1:
            max_agree = max(class_counts.values())
            agg.concordance_rate = max_agree / len(records) * 100
        else:
            agg.concordance_rate = 100.0

        # 质量等级
        agg.quality_grade = self._compute_quality_grade(agg)
        return agg

    @staticmethod
    def _compute_quality_grade(agg: AggregatedVariantEvidence) -> str:
        """
        综合质量等级:
        A: 多文献一致 + 高置信度
        B: 多文献但不完全一致 或 单文献高置信度
        C: 低置信度或少量证据
        D: 无效或矛盾
        """
        if (
            agg.document_count >= 3
            and agg.concordance_rate >= 80
            and agg.weighted_confidence >= 80
        ):
            return "A"
        elif (
            agg.document_count >= 2 and agg.weighted_confidence >= 70
        ) or (
            agg.document_count == 1 and agg.weighted_confidence >= 85
        ):
            return "B"
        elif agg.weighted_confidence >= 50 and agg.valid_evidence_count > 0:
            return "C"
        else:
            return "D"

    @staticmethod
    def _compute_overall_stats(variants: List[AggregatedVariantEvidence]) -> Dict[str, Any]:
        """计算聚合报告的总体统计"""
        if not variants:
            return {"total_variants": 0, "total_evidence": 0}

        total_evidence = sum(v.evidence_count for v in variants)
        total_valid = sum(v.valid_evidence_count for v in variants)
        all_docs = set()
        for v in variants:
            all_docs.update(v.document_ids)

        grade_dist: Dict[str, int] = defaultdict(int)
        for v in variants:
            grade_dist[v.quality_grade] += 1

        return {
            "total_variants": len(variants),
            "total_evidence": total_evidence,
            "total_valid_evidence": total_valid,
            "total_documents": len(all_docs),
            "quality_grade_distribution": dict(grade_dist),
            "avg_concordance": round(
                sum(v.concordance_rate for v in variants) / len(variants), 1,
            ),
        }


# ==================== 工厂 ====================

_engine: Optional[EvidenceAggregationEngine] = None


def get_evidence_aggregation_engine() -> EvidenceAggregationEngine:
    global _engine
    if _engine is None:
        _engine = EvidenceAggregationEngine()
    return _engine
