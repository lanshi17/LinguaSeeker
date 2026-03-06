from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from src.service.enum import TaskStatus, WorkflowStatus


class ValidationErrorDetail(BaseModel):
    type: str = Field(..., description="Error type")
    loc: List[Union[str, int]] = Field(..., description="Location of the error")
    msg: str = Field(..., description="Error message")
    input: Any = Field(..., description="Input value that caused the error")
    ctx: Optional[Dict[str, Any]] = Field(None, description="Extra context")


class ValidationErrorResponse(BaseModel):
    code: str = Field("VALIDATION_ERROR", description="Error code")
    message: str = Field("Invalid request payload", description="Error message")
    errors: List[ValidationErrorDetail] = Field(..., description="Validation errors")


class TaskCreateRequest(BaseModel):
    file_paths: List[str] = Field(..., description="Local file paths to process")
    output_root: Optional[str] = Field(None, description="Output directory root")

    class Config:
        json_schema_extra = {
            "example": {
                "file_paths": ["/data/uploads/sample.pdf"],
                "output_root": "/data/outputs",
            }
        }


class TaskCreateResponse(BaseModel):
    task_id: str = Field(..., description="Celery task id")
    status: TaskStatus = Field(..., description="Task status")

    class Config:
        json_schema_extra = {
            "example": {"task_id": "1f6a8b7a-1b87-4d75-8c72-6f2f6a1a9c2e", "status": "PENDING"}
        }


class TaskStatusResponse(BaseModel):
    task_id: str = Field(..., description="Celery task id")
    status: TaskStatus = Field(..., description="Task status")
    workflow_status: Optional[WorkflowStatus] = Field(
        None, description="Detailed workflow stage status"
    )
    workflow_status_description: Optional[str] = Field(
        None, description="Human-readable workflow stage description"
    )
    progress_percentage: Optional[float] = Field(
        None, ge=0, le=100, description="Workflow completion percentage"
    )
    processing_steps: Optional[Dict[str, Dict[str, Any]]] = Field(
        None, description="Detailed per-step processing state"
    )
    paper_task_id: Optional[str] = Field(None, description="Paper task UUID when available")
    document_id: Optional[str] = Field(
        None, description="Document id associated with the task result"
    )
    file_size_bytes: Optional[int] = Field(None, description="Total input file size in bytes")
    processing_duration_seconds: Optional[float] = Field(
        None, description="Processing duration in seconds"
    )
    created_at: Optional[str] = Field(None, description="Task creation timestamp if available")
    updated_at: Optional[str] = Field(None, description="Task update timestamp if available")
    error: Optional[str] = Field(None, description="Error message if failed")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Structured error details")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "1f6a8b7a-1b87-4d75-8c72-6f2f6a1a9c2e",
                "status": "SUCCESS",
                "workflow_status": "COMPLETED",
                "workflow_status_description": "Workflow completed successfully.",
                "progress_percentage": 100.0,
                "processing_steps": {
                    "acquisition": {
                        "status": "COMPLETED",
                        "updated_at": "2026-02-10T08:00:01+00:00",
                        "message": "Node acquisition completed",
                        "error_code": None,
                    }
                },
                "paper_task_id": "6f03f2f8-58b0-48e1-9600-a4d1464580bc",
                "document_id": "c525fcfa-6dd9-4c9d-8d42-bd7c5a52fa7a",
                "file_size_bytes": 1048576,
                "processing_duration_seconds": 12.3,
                "created_at": "2026-02-10T08:00:00+00:00",
                "updated_at": "2026-02-10T08:00:12+00:00",
                "error": None,
                "error_details": None,
            }
        }


class TaskListItem(BaseModel):
    task_id: str = Field(..., description="Celery task id")
    status: TaskStatus = Field(..., description="Task status")
    date_done: Optional[str] = Field(None, description="Completion timestamp if available")
    document_id: Optional[str] = Field(
        None, description="Document id associated with the task result"
    )
    file_size_bytes: Optional[int] = Field(None, description="Total input file size in bytes")
    processing_duration_seconds: Optional[float] = Field(
        None, description="Processing duration in seconds"
    )
    created_at: Optional[str] = Field(None, description="Task creation timestamp if available")
    updated_at: Optional[str] = Field(None, description="Task update timestamp if available")
    result: Optional[Dict[str, Any]] = Field(None, description="Task result if completed")
    error: Optional[str] = Field(None, description="Error message if failed")


class TaskListResponse(BaseModel):
    items: List[TaskListItem] = Field(..., description="Task list items")
    next_cursor: int = Field(..., description="Next Redis scan cursor")
    count: int = Field(..., description="Number of items returned")

    class Config:
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "task_id": "1f6a8b7a-1b87-4d75-8c72-6f2f6a1a9c2e",
                        "status": "SUCCESS",
                        "date_done": "2026-02-10T08:00:00+00:00",
                        "document_id": "c525fcfa-6dd9-4c9d-8d42-bd7c5a52fa7a",
                        "file_size_bytes": 1048576,
                        "processing_duration_seconds": 12.3,
                        "created_at": "2026-02-10T08:00:00+00:00",
                        "updated_at": "2026-02-10T08:00:12+00:00",
                        "result": {"summary": "task result payload"},
                        "error": None,
                    }
                ],
                "next_cursor": 0,
                "count": 1,
            }
        }


class PaperTaskItemResponse(BaseModel):
    paper_task_id: str = Field(..., description="Paper task UUIDv4")
    filename: Optional[str] = Field(None, description="Original filename")
    status: str = Field(..., description="Paper status")
    error_code: Optional[str] = Field(None, description="Error code when applicable")
    duplicate_of: Optional[str] = Field(
        None, description="Historical paper_task_id when duplicated"
    )
    document_id: Optional[str] = Field(None, description="Document UUID when available")
    celery_task_id: Optional[str] = Field(
        None, description="Celery task id for non-duplicate processing"
    )


class TaskRequestCreateResponse(BaseModel):
    request_id: str = Field(..., description="Request UUIDv4")
    status: str = Field(..., description="Request status")
    papers: List[PaperTaskItemResponse] = Field(
        default_factory=list, description="Paper task results"
    )


class TaskRequestStatusResponse(BaseModel):
    request_id: str = Field(..., description="Request UUIDv4")
    status: str = Field(..., description="Aggregated request status")
    papers: List[PaperTaskItemResponse] = Field(
        default_factory=list, description="Current paper task list"
    )


class PubMedCandidateItem(BaseModel):
    pmid: str = Field(..., description="PubMed id")
    title: str = Field(..., description="Article title")
    journal: str = Field(..., description="Journal name")
    pub_date: str = Field(..., description="Publication date")


class PubMedCandidateSearchRequest(BaseModel):
    task_form: str = Field(..., description="Natural-language task form")
    target: str = Field(..., description="Target gene/variant or objective")
    disease: str = Field(..., description="Disease name")
    country: str = Field("不限", description="Country filter (ISO/alias)")
    language: str = Field("auto", description="Language preference")
    source: str = Field("pubmed", description="Data source, MVP supports pubmed only")
    candidate_limit: int = Field(15, ge=1, le=15, description="Candidate limit, max 15")


class PubMedCandidateSearchResponse(BaseModel):
    task_form: str = Field(..., description="Echoed task form")
    candidates: List[PubMedCandidateItem] = Field(
        default_factory=list, description="Candidate papers"
    )


class PubMedSelectionSubmitRequest(BaseModel):
    task_form: str = Field(..., description="Natural-language task form")
    selected_pmids: List[str] = Field(..., min_length=1, description="Selected PubMed IDs, 1~10")
    target: str = Field(..., description="Target gene/variant or objective")
    disease: str = Field(..., description="Disease name")
    country: str = Field("不限", description="Country filter")
    language: str = Field("auto", description="Language preference")
    source: str = Field("pubmed", description="Data source")


class InteractionStartRequest(BaseModel):
    user_input: str = Field(..., description="Natural-language user input for task clarification")


class TaskFormStructured(BaseModel):
    goal: str = Field(..., description="Research objective or evidence type")
    disease: str = Field(..., description="Disease, gene, or variant name")
    country: str = Field("不限", description="Country filter (ISO/alias)")
    language: str = Field("auto", description="Language preference")


class InteractionStartResponse(BaseModel):
    session_id: str = Field(..., description="Session UUIDv4 for continuation")
    ready: bool = Field(
        ..., description="True if task form is complete, False if clarification needed"
    )
    task_form: Optional[TaskFormStructured] = Field(
        None, description="Structured task form when ready"
    )
    question: Optional[str] = Field(None, description="Clarification question when not ready")
    round: int = Field(..., description="Current clarification round (0=ready, 1-2=clarifying)")


class InteractionRespondRequest(BaseModel):
    session_id: str = Field(..., description="Session UUIDv4 from start_interaction")
    user_response: str = Field(..., description="User response to clarification question")


class InteractionRespondResponse(BaseModel):
    ready: bool = Field(
        ..., description="True if task form is complete, False if clarification needed"
    )
    task_form: Optional[TaskFormStructured] = Field(
        None, description="Structured task form when ready"
    )
    question: Optional[str] = Field(None, description="Clarification question when not ready")
    round: int = Field(..., description="Current clarification round (0=ready, 1-2=clarifying)")
