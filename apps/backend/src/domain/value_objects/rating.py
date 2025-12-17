"""评级相关值对象"""
from typing import List, Optional
from enum import Enum


class EvidenceLevel(str, Enum):
    """证据等级"""
    PS3_STRONG = "PS3_Strong"
    PS3_MODERATE = "PS3_Moderate"
    PS3_SUPPORTING = "PS3_Supporting"
    INSUFFICIENT = "Insufficient"
    CONFLICTING = "Conflicting"


class RatingResult:
    """评级结果值对象"""
    
    def __init__(
        self,
        variant_id: str,
        gene_symbol: str,
        final_level: EvidenceLevel,
        evidence_summary: List[dict],
        model_decision: dict,
        consistency_score: float
    ):
        self.variant_id = variant_id
        self.gene_symbol = gene_symbol
        self.final_level = final_level
        self.evidence_summary = evidence_summary
        self.model_decision = model_decision  # DeepSeek/GPT-4o的决策详情
        self.consistency_score = consistency_score
    
    def is_sufficient(self) -> bool:
        """判断证据是否充分"""
        pass
