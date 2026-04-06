"""
领域数据传输对象 (DTOs)
仅包含 EntityLink / AssociationReport 等跨模块传递的数据结构。
业务逻辑已迁移至 entity_association_service.py。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


# ==================== 实体关联 DTO ====================

@dataclass
class EntityLink:
    """实体间的关联关系"""
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    relationship: str
    co_occurrence_count: int = 0
    document_ids: List[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class AssociationReport:
    """关联分析报告"""
    query_entity_type: str
    query_entity_id: str
    links: List[EntityLink] = field(default_factory=list)
    co_occurrence_matrix: Dict[str, Dict[str, int]] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_entity": {"type": self.query_entity_type, "id": self.query_entity_id},
            "links": [
                {
                    "source": {"type": link.source_type, "id": link.source_id},
                    "target": {"type": link.target_type, "id": link.target_id},
                    "relationship": link.relationship,
                    "co_occurrence_count": link.co_occurrence_count,
                    "document_ids": link.document_ids,
                    "confidence": link.confidence,
                }
                for link in self.links
            ],
            "co_occurrence_matrix": self.co_occurrence_matrix,
            "summary": self.summary,
        }
