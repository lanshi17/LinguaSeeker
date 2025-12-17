"""报告实体 - 对应PostgreSQL Reports表"""
from typing import Optional
from uuid import UUID


class Report:
    """报告实体"""
    
    def __init__(
        self,
        report_id: UUID,
        task_id: UUID,
        final_rating: dict,
        consistency_score: float,
        metadata: Optional[dict] = None
    ):
        self.report_id = report_id
        self.task_id = task_id
        self.final_rating = final_rating  # JSON格式，含DeepSeek/GPT-4o的决策
        self.consistency_score = consistency_score
        self.metadata = metadata or {}
    
    def calculate_consistency(self) -> float:
        """计算证据一致性评分"""
        pass
    
    def to_dict(self) -> dict:
        """转换为字典"""
        pass
