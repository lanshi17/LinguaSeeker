from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EvidenceItemSummary(BaseModel):
    """
    Summary of an evidence item for task status response.
    """
    id: str = Field(..., description="Unique identifier for the evidence item")
    acmg_code: str = Field(..., description="ACMG evidence code (e.g., PS1, PM2)")
    confidence_score: float = Field(..., description="Confidence score between 0.0 and 1.0", ge=0.0, le=1.0)
    review_required: bool = Field(..., description="Whether human review is required (confidence < 0.85)")
    source_page: int = Field(..., description="Page number in the original document")


class TaskStatusResponse(BaseModel):
    """
    Response DTO for querying parsing task status.
    """
    task_id: str = Field(..., description="Unique identifier for the parsing task")
    document_id: str = Field(..., description="Unique identifier for the associated document")
    status: TaskStatus = Field(..., description="Current status of the parsing task")
    progress_percentage: int = Field(0, description="Progress percentage (0-100)", ge=0, le=100)
    current_stage: Optional[str] = Field(None, description="Current processing stage")
    created_at: datetime = Field(..., description="Timestamp when the task was created")
    updated_at: datetime = Field(..., description="Timestamp when the task was last updated")
    completed_at: Optional[datetime] = Field(None, description="Timestamp when the task was completed")
    error_message: Optional[str] = Field(None, description="Error message if task failed")
    evidence_items: List[EvidenceItemSummary] = Field(
        default_factory=list,
        description="List of extracted evidence items with summary information"
    )
    processing_time_seconds: Optional[float] = Field(None, description="Total processing time in seconds")
    file_size_bytes: Optional[int] = Field(None, description="Original file size in bytes")

    class Config:
        schema_extra = {
            "example": {
                "task_id": "task_12345",
                "document_id": "doc_67890",
                "status": "completed",
                "progress_percentage": 100,
                "current_stage": "Evidence Extraction",
                "created_at": "2026-01-31T10:00:00Z",
                "updated_at": "2026-01-31T10:05:30Z",
                "completed_at": "2026-01-31T10:05:30Z",
                "error_message": None,
                "evidence_items": [
                    {
                        "id": "evid_1",
                        "acmg_code": "PS1",
                        "confidence_score": 0.92,
                        "review_required": False,
                        "source_page": 5
                    },
                    {
                        "id": "evid_2",
                        "acmg_code": "PM2",
                        "confidence_score": 0.78,
                        "review_required": True,
                        "source_page": 12
                    }
                ],
                "processing_time_seconds": 330.5,
                "file_size_bytes": 2048000
            }
        }