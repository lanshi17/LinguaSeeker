from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class EvidenceItemSummary(BaseModel):
    """
    Summary of an evidence item for API responses.
    """
    id: str = Field(..., description="Unique identifier for the evidence item")
    acmg_code: str = Field(..., description="ACMG evidence code (e.g., PS1, PM2)")
    confidence_score: float = Field(..., description="Confidence score between 0.0 and 1.0", ge=0.0, le=1.0)
    review_required: bool = Field(..., description="Whether human review is required (confidence < 0.85)")
    source_page: int = Field(..., description="Page number in the original document")
    source_coordinates: Optional[dict] = Field(None, description="Bounding box coordinates {x, y, width, height}")
    supporting_text: str = Field(..., description="Extracted supporting text passage")
    variant_id: Optional[str] = Field(None, description="Linked genetic variant ID")
    human_reviewed: bool = Field(False, description="Whether this item has been human-reviewed")
    created_at: datetime = Field(..., description="When the evidence was extracted")


class EvidenceListResponse(BaseModel):
    """
    Response DTO for listing evidence items from a document.
    """
    document_id: str = Field(..., description="Document identifier")
    total_evidence_items: int = Field(..., description="Total number of evidence items found")
    auto_accepted: int = Field(..., description="Number of items auto-accepted (confidence >= 0.85)")
    review_required: int = Field(..., description="Number of items requiring human review")
    evidence_items: List[EvidenceItemSummary] = Field(
        default_factory=list,
        description="List of extracted evidence items"
    )
    processing_completed_at: Optional[datetime] = Field(None, description="When processing completed")
    average_confidence: float = Field(0.0, description="Average confidence score across all items")

    class Config:
        schema_extra = {
            "example": {
                "document_id": "doc_12345",
                "total_evidence_items": 8,
                "auto_accepted": 6,
                "review_required": 2,
                "evidence_items": [
                    {
                        "id": "evid_1",
                        "acmg_code": "PS1",
                        "confidence_score": 0.92,
                        "review_required": False,
                        "source_page": 5,
                        "source_coordinates": {"x": 100.5, "y": 200.0, "width": 300.0, "height": 50.0},
                        "supporting_text": "The same amino acid change as established pathogenic variant...",
                        "variant_id": "var_67890",
                        "human_reviewed": False,
                        "created_at": "2026-01-31T10:05:30Z"
                    },
                    {
                        "id": "evid_2",
                        "acmg_code": "PM2",
                        "confidence_score": 0.78,
                        "review_required": True,
                        "source_page": 12,
                        "source_coordinates": {"x": 150.0, "y": 300.5, "width": 250.0, "height": 45.0},
                        "supporting_text": "Absent from controls or extremely low frequency...",
                        "variant_id": None,
                        "human_reviewed": False,
                        "created_at": "2026-01-31T10:05:35Z"
                    }
                ],
                "processing_completed_at": "2026-01-31T10:05:30Z",
                "average_confidence": 0.85
            }
        }