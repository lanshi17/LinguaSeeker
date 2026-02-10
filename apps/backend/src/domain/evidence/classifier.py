"""
证据分类器模块
将 PS3/BS3 证据强度评估、分数分类、ACMG 映射、仲裁验证
封装为 EvidenceClassifier 类，实现高内聚低耦合。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from src.domain.enums import (
    ACMGEvidenceLevel,
    EvidenceClassification,
    EvidenceStrength,
    EVIDENCE_VALIDITY_THRESHOLD,
    ODDSPATH_STRENGTH_MAP,
    SCORE_CLASSIFICATION_MAP,
)
from src.domain.models import (
    ExtractedEvidenceFields,
    EvidenceStrengthClassification,
)



class EvidenceClassifier:
    """
    ACMG PS3/BS3 证据分类器。

    职责:
    - OddsPath → 证据强度映射
    - 对照变异数 → 最大证据强度确定
    - 证据强度 → ACMG 等级转换
    - PS3 四步法评分 → 综合分类
    - 仲裁结果二次验证
    """

    # ==================== 证据强度 → ACMG 等级映射 ====================

    _STRENGTH_TO_ACMG: Dict[str, List[str]] = {
        EvidenceStrength.PS3_VERY_STRONG.value: [ACMGEvidenceLevel.PVS1.value],
        EvidenceStrength.PS3.value:              [ACMGEvidenceLevel.PS3.value],
        EvidenceStrength.PS3_MODERATE.value:     [ACMGEvidenceLevel.PM1.value],
        EvidenceStrength.PS3_SUPPORTING.value:   [ACMGEvidenceLevel.PP3.value],
        EvidenceStrength.BS3.value:              [ACMGEvidenceLevel.BS3.value],
        EvidenceStrength.BS3_MODERATE.value:     [ACMGEvidenceLevel.BS2.value],
        EvidenceStrength.BS3_SUPPORTING.value:   [ACMGEvidenceLevel.BP4.value],
    }

    # ==================== OddsPath 映射 ====================

    @staticmethod
    def oddspath_to_strength(oddspath: float) -> str:
        """将 OddsPath 值映射为证据强度等级。"""
        if oddspath < 0:
            logger.debug("OddsPath < 0, returning NONE")
            return EvidenceStrength.NONE.value
        for threshold, strength in ODDSPATH_STRENGTH_MAP:
            if oddspath > threshold:
                logger.debug("OddsPath {} mapped to strength {}", oddspath, strength)
                return strength
        logger.debug("OddsPath {} mapped to default BS3", oddspath)
        return EvidenceStrength.BS3.value

    # ==================== 对照变异数 → 最大证据强度 ====================

    @staticmethod
    def max_strength_from_controls(count: int) -> str:
        """根据对照变异数量确定最大可用证据强度。"""
        if count <= 0:
            logger.debug("Control count <= 0, returning NONE")
            return EvidenceStrength.NONE.value
        elif count <= 10:
            logger.debug("Control count {} mapped to max_supporting", count)
            return "max_supporting"
        else:
            logger.debug("Control count {} mapped to max_moderate", count)
            return "max_moderate"

    # ==================== 证据强度 → ACMG 等级 ====================

    @classmethod
    def strength_to_acmg_levels(cls, strength: str) -> List[str]:
        """将证据强度映射为 ACMG 证据等级列表。"""
        return cls._STRENGTH_TO_ACMG.get(strength, [])

    # ==================== 分数 → 分类 ====================

    @staticmethod
    def score_to_classification(score: float) -> str:
        """将综合评分映射为分类标签。"""
        logger.debug("Mapping score {} to classification", score)
        return _lookup_threshold(score, SCORE_CLASSIFICATION_MAP)

    # ==================== 核心分类方法 ====================

    @classmethod
    def classify(
        cls,
        ps3_evidence: Dict[str, Any],
        extracted_fields: Optional[Dict[str, Any]] = None,
    ) -> EvidenceStrengthClassification:
        """
        对 LLM 提取的证据进行完整的强度分类。

        Args:
            ps3_evidence:    PS3 四步法评估 JSON
            extracted_fields: 结构化提取的 11 个字段 (可选)

        Returns:
            EvidenceStrengthClassification 分类结果
        """
        # 1) PS3 总分
        total_score = cls._compute_total_score(ps3_evidence)
        logger.debug("Computed PS3 total score: {}", total_score)

        # 2) 字段置信度
        field_confidence = 0.0
        if extracted_fields:
            try:
                fields_model = ExtractedEvidenceFields(**extracted_fields)
                field_confidence = fields_model.compute_overall_confidence()
            except Exception:
                logger.warning("无法解析 extracted_fields，跳过字段置信度计算")
        logger.debug("Field confidence: {}", field_confidence)

        # 3) 综合评分 (PS3: 60% + 字段置信度: 40%)
        overall_score = (
            total_score * 0.6 + field_confidence * 0.4
            if field_confidence > 0
            else total_score
        )

        # 4) 分类
        classification = cls.score_to_classification(overall_score)
        logger.debug("Overall score: {} classification: {}", overall_score, classification)

        # 5) ACMG 等级
        step4 = ps3_evidence.get("ps3_step_4", {})
        final_strength = step4.get("final_evidence_strength", "none")
        acmg_levels = cls.strength_to_acmg_levels(final_strength)
        logger.debug("Final strength: {} ACMG levels: {}", final_strength, acmg_levels)

        # 6) 有效性
        is_valid = overall_score >= EVIDENCE_VALIDITY_THRESHOLD

        # 7) 支持证据
        supporting: List[str] = []
        for step_key in ("ps3_step_1", "ps3_step_2", "ps3_step_3", "ps3_step_4"):
            refs = ps3_evidence.get(step_key, {}).get("evidence_refs", [])
            if isinstance(refs, list):
                supporting.extend(refs)

        reasoning = (
            f"PS3 步骤评分: {total_score:.1f}/100, "
            f"字段置信度: {field_confidence:.1f}/100, "
            f"综合评分: {overall_score:.1f}/100, "
            f"证据强度: {final_strength}, "
            f"有效性: {'有效' if is_valid else '无效'}"
        )

        logger.info(
            "证据分类完成: score={:.1f}, classification={}, acmg={}, valid={}",
            overall_score, classification, acmg_levels, is_valid,
        )

        return EvidenceStrengthClassification(
            overall_score=round(overall_score, 2),
            classification=classification,
            acmg_levels=acmg_levels,
            is_valid=is_valid,
            supporting_evidence=list(dict.fromkeys(supporting)),
            reasoning=reasoning,
        )

    # ==================== 仲裁验证 ====================

    @classmethod
    def validate_with_arbitration(
        cls,
        ps3_evidence: Dict[str, Any],
        arbitration_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        将仲裁 LLM 的结果与初始分类进行比对，生成最终结论。

        Args:
            ps3_evidence:      初始 PS3 证据
            arbitration_result: 仲裁 LLM 返回的 JSON

        Returns:
            合并后的最终结论字典
        """
        initial = cls.classify(ps3_evidence)

        raw_confidence = arbitration_result.get("confidence", 0.0)
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError):
            confidence = 0.0

        confidence = max(0.0, min(1.0, confidence))
        final_is_valid = confidence >= (EVIDENCE_VALIDITY_THRESHOLD / 100.0)
        arb_decision = arbitration_result.get("final_decision", "reject")

        return {
            "initial_score": initial.overall_score,
            "initial_classification": initial.classification,
            "arbitration_confidence": round(confidence, 4),
            "final_classification": initial.classification,
            "final_is_valid": final_is_valid,
            "arbitration_decision": arb_decision,
            "acmg_levels": initial.acmg_levels,
            "reasoning": initial.reasoning,
            "arbitration_feedback": arbitration_result.get("feedback", ""),
        }

    # ==================== 内部辅助方法 ====================

    @staticmethod
    def _compute_total_score(ps3_evidence: Dict[str, Any]) -> float:
        """从 PS3 四步法提取总评分。"""
        overall = ps3_evidence.get("overall_assessment", {})
        if isinstance(overall, dict) and "total_score" in overall:
            try:
                return float(overall["total_score"])
            except (TypeError, ValueError):
                pass

        total = 0.0
        for step_key in ("ps3_step_1", "ps3_step_2", "ps3_step_3", "ps3_step_4"):
            step_data = ps3_evidence.get(step_key, {})
            if isinstance(step_data, dict) and "score" in step_data:
                try:
                    total += float(step_data["score"])
                except (TypeError, ValueError):
                    pass
        return min(total, 100.0)


# ==================== 模块级工具函数 (供外部直接使用) ====================

def _lookup_threshold(score: float, mapping: List[Tuple[float, str]]) -> str:
    """在 (threshold, label) 降序列表中查找分数对应的分类。"""
    for threshold, label in mapping:
        if score >= threshold:
            return label
    return EvidenceClassification.BENIGN.value


def strength_to_acmg_levels(strength: str) -> List[str]:
    """模块级快捷方法：将证据强度映射为 ACMG 等级列表。"""
    return EvidenceClassifier.strength_to_acmg_levels(strength)


# ==================== 单例 ====================

_classifier: Optional[EvidenceClassifier] = None


def get_evidence_classifier() -> EvidenceClassifier:
    """获取 EvidenceClassifier 单例。"""
    global _classifier
    if _classifier is None:
        _classifier = EvidenceClassifier()
    return _classifier
