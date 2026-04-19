# pyright: reportDeprecated=false, reportExplicitAny=false, reportAny=false, reportUnannotatedClassAttribute=false

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator

from src.services.enum import TaskStatus, WorkflowStatus


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
            "example": {
                "task_id": "1f6a8b7a-1b87-4d75-8c72-6f2f6a1a9c2e",
                "status": "PENDING",
            }
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
    parsing_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Document parsing metadata when available"
    )
    paper_task_id: Optional[str] = Field(
        None, description="Paper task UUID when available"
    )
    document_id: Optional[str] = Field(
        None, description="Document id associated with the task result"
    )
    file_size_bytes: Optional[int] = Field(
        None, description="Total input file size in bytes"
    )
    processing_duration_seconds: Optional[float] = Field(
        None, description="Processing duration in seconds"
    )
    created_at: Optional[str] = Field(
        None, description="Task creation timestamp if available"
    )
    updated_at: Optional[str] = Field(
        None, description="Task update timestamp if available"
    )
    warning_codes: Optional[List[str]] = Field(
        None, description="Non-fatal warning codes recorded for the paper task"
    )
    trace_chain: Optional[Dict[str, Any]] = Field(
        None, description="Additive node-level provenance summary"
    )
    error: Optional[str] = Field(None, description="Error message if failed")
    error_details: Optional[Dict[str, Any]] = Field(
        None, description="Structured error details"
    )

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
                "parsing_metadata": {
                    "parser_backend": "mineru",
                    "parser_task_id": "mineru-task-1",
                    "mineru_folder": "/tmp/mineru-output",
                    "image_count": 3,
                    "markdown_object_key": "doc-1/parsing/parsed_markdown.md",
                },
                "paper_task_id": "6f03f2f8-58b0-48e1-9600-a4d1464580bc",
                "document_id": "c525fcfa-6dd9-4c9d-8d42-bd7c5a52fa7a",
                "file_size_bytes": 1048576,
                "processing_duration_seconds": 12.3,
                "created_at": "2026-02-10T08:00:00+00:00",
                "updated_at": "2026-02-10T08:00:12+00:00",
                "warning_codes": ["FULLTEXT_UNAVAILABLE"],
                "trace_chain": {
                    "steps": {
                        "acquisition": {
                            "status": "COMPLETED",
                            "outcome": "success",
                        }
                    }
                },
                "error": None,
                "error_details": None,
            }
        }


class PaperTaskDetailResponse(BaseModel):
    paper_task_id: str = Field(..., description="Paper task UUIDv4")
    request_id: str = Field(..., description="Parent request UUIDv4")
    document_id: Optional[str] = Field(None, description="Document UUID when available")
    status: str = Field(..., description="Paper task status")
    workflow_status: Optional[WorkflowStatus] = Field(
        None, description="Detailed workflow stage status"
    )
    processing_steps: Optional[Dict[str, Dict[str, Any]]] = Field(
        None, description="Detailed per-step processing state"
    )
    warning_codes: Optional[List[str]] = Field(
        None, description="Non-fatal warning codes recorded for the paper task"
    )
    trace_chain: Optional[Dict[str, Any]] = Field(
        None, description="Additive node-level provenance summary"
    )
    fulltext_unavailable: Optional[bool] = Field(
        None, description="Whether the paper fell back to metadata/abstract evidence"
    )
    result_payload: Optional[Dict[str, Any]] = Field(
        None, description="Paper-task result payload when available from Celery"
    )
    parsing_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Document parsing metadata when available"
    )
    duplicate_of: Optional[str] = Field(
        None, description="Historical paper_task_id when duplicated"
    )
    error_code: Optional[str] = Field(None, description="Error code when applicable")
    error_details: Optional[Dict[str, Any]] = Field(
        None, description="Structured error details"
    )
    created_at: Optional[str] = Field(
        None, description="Task creation timestamp if available"
    )
    updated_at: Optional[str] = Field(
        None, description="Task update timestamp if available"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "paper_task_id": "6f03f2f8-58b0-48e1-9600-a4d1464580bc",
                "request_id": "e1c7ccf0-222b-4f17-95a2-a3594ef27408",
                "document_id": "c525fcfa-6dd9-4c9d-8d42-bd7c5a52fa7a",
                "status": "success",
                "workflow_status": "COMPLETED",
                "processing_steps": {
                    "acquisition": {"status": "COMPLETED"},
                    "classification": {"status": "COMPLETED"},
                    "adjudication": {"status": "COMPLETED"},
                },
                "warning_codes": ["FULLTEXT_UNAVAILABLE"],
                "trace_chain": {
                    "steps": {
                        "acquisition": {
                            "status": "COMPLETED",
                            "outcome": "success",
                        }
                    }
                },
                "fulltext_unavailable": True,
                "result_payload": {"graph_sync_result": {"neo4j_ok": True}},
                "parsing_metadata": {"parser_backend": "mineru"},
                "duplicate_of": None,
                "error_code": None,
                "error_details": None,
                "created_at": "2026-02-10T08:00:00+00:00",
                "updated_at": "2026-02-10T08:00:12+00:00",
            }
        }


class TaskListItem(BaseModel):
    task_id: str = Field(..., description="Celery task id")
    status: TaskStatus = Field(..., description="Task status")
    date_done: Optional[str] = Field(
        None, description="Completion timestamp if available"
    )
    document_id: Optional[str] = Field(
        None, description="Document id associated with the task result"
    )
    file_size_bytes: Optional[int] = Field(
        None, description="Total input file size in bytes"
    )
    processing_duration_seconds: Optional[float] = Field(
        None, description="Processing duration in seconds"
    )
    created_at: Optional[str] = Field(
        None, description="Task creation timestamp if available"
    )
    updated_at: Optional[str] = Field(
        None, description="Task update timestamp if available"
    )
    result: Optional[Dict[str, Any]] = Field(
        None, description="Task result if completed"
    )
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


class SourceProviderStatsResponse(BaseModel):
    attempts: int = Field(0, description="Total provider attempts")
    hits: int = Field(0, description="Successful provider hits with returned items or downloads")
    search_hits: int = Field(0, description="Successful search hits")
    download_hits: int = Field(0, description="Successful download hits")
    errors: int = Field(0, description="Attempts ending with an error")
    fallback_hits: int = Field(0, description="Successful hits that occurred after an earlier failed attempt")


class TaskRequestSourceStatsResponse(BaseModel):
    request_id: str = Field(..., description="Request UUIDv4")
    paper_count: int = Field(..., description="Number of paper tasks considered in the aggregation")
    fallback_count: int = Field(..., description="Number of paper tasks that used fallback across providers")
    providers: Dict[str, SourceProviderStatsResponse] = Field(
        default_factory=dict,
        description="Aggregated provider hit statistics derived from persisted source_trace",
    )


class PubMedCandidateItem(BaseModel):
    pmid: str = Field(..., description="PubMed id")
    title: str = Field(..., description="Article title")
    journal: str = Field(..., description="Journal name")
    pub_date: str = Field(..., description="Publication date")


class PubMedCandidateSearchRequest(BaseModel):
    request_id: Optional[str] = Field(
        None, description="Confirmed request ID for M2 handoff"
    )
    task_form: Optional[str] = Field(None, description="Natural-language task form")
    target: str = Field(..., description="Target gene/variant or objective")
    disease: str = Field(..., description="Disease name")
    country: str = Field("不限", description="Country filter (ISO/alias)")
    language: str = Field("auto", description="Language preference")
    source: str = Field("pubmed", description="Data source, MVP supports pubmed only")
    candidate_limit: int = Field(15, ge=1, le=15, description="Candidate limit, max 15")

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized != "pubmed":
            raise ValueError("source must be pubmed in MVP")
        return normalized


class PubMedCandidateSearchResponse(BaseModel):
    request_id: Optional[str] = Field(
        None, description="Request ID for M2 handoff continuity"
    )
    task_form: str = Field(..., description="Echoed task form")
    candidates: List[PubMedCandidateItem] = Field(
        default_factory=list, description="Candidate papers"
    )


class PubMedSelectionSubmitRequest(BaseModel):
    task_form: str = Field(..., description="Natural-language task form")
    selected_pmids: List[str] = Field(
        ..., min_length=1, description="Selected PubMed IDs, 1~10"
    )
    target: str = Field(..., description="Target gene/variant or objective")
    disease: str = Field(..., description="Disease name")
    country: str = Field("不限", description="Country filter")
    language: str = Field("auto", description="Language preference")
    source: str = Field("pubmed", description="Data source")


class LiteratureCandidateItem(BaseModel):
    candidate_id: str
    provider: str
    route: str
    title: str
    journal: Optional[str] = None
    year: Optional[str] = None
    language: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    identifiers: Dict[str, Any] = Field(default_factory=dict)
    detail_link: Optional[str] = None


class LiteratureCandidateSearchRequest(BaseModel):
    request_id: Optional[str] = Field(
        None, description="Confirmed request ID for M2 handoff"
    )
    task_form: Optional[str] = Field(None, description="Natural-language task form")
    target: str = Field(..., description="Target gene/variant or objective")
    disease: str = Field(..., description="Disease name")
    country: str = Field("不限", description="Country filter (ISO/alias)")
    language: str = Field("auto", description="Language preference")
    source: str = Field("literature", description="Data source")
    candidate_limit: int = Field(15, ge=1, le=20, description="Candidate limit, max 20")
    provider_hints: List[str] = Field(
        default_factory=list,
        description="Optional provider order hints",
    )


class LiteratureCandidateSearchResponse(BaseModel):
    request_id: Optional[str] = Field(
        None, description="Request ID for M2 handoff continuity"
    )
    task_form: str = Field(..., description="Echoed task form")
    candidates: List[LiteratureCandidateItem] = Field(
        default_factory=list, description="Normalized literature candidates"
    )


class LiteratureSelectionSubmitRequest(BaseModel):
    request_id: Optional[str] = Field(
        None, description="Existing request ID when continuing a confirmed flow"
    )
    task_form: Optional[str] = Field(None, description="Natural-language task form")
    selected_candidates: List[LiteratureCandidateItem] = Field(
        default_factory=list, description="Selected literature candidates, 1~10"
    )
    source: str = Field("literature", description="Data source")


class WebLiteratureCrawlRequest(BaseModel):
    task_form: str = Field(..., description="Natural-language task form")
    urls: List[str] = Field(..., min_length=1, description="Selected web URLs, 1~10")
    source: str = Field("web", description="Data source")
    force_refresh: bool = Field(
        False, description="Bypass URL fingerprint dedup when true"
    )


class InteractionStartRequest(BaseModel):
    user_input: str = Field(
        ..., description="Natural-language user input for task clarification"
    )


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
    question: Optional[str] = Field(
        None, description="Clarification question when not ready"
    )
    round: int = Field(
        ..., description="Current clarification round (0=ready, 1-2=clarifying)"
    )
    # M2 Contract: First-round clarification semantics
    needs_clarification: Optional[bool] = Field(
        None, description="M2: True if clarification needed (round 1)"
    )
    clarification_question: Optional[str] = Field(
        None, description="M2: Clarification question (mirrors 'question' field)"
    )


class InteractionRespondRequest(BaseModel):
    session_id: str = Field(..., description="Session UUIDv4 from start_interaction")
    user_response: str = Field(
        ..., description="User response to clarification question"
    )


class InteractionRespondResponse(BaseModel):
    ready: bool = Field(
        ..., description="True if task form is complete, False if clarification needed"
    )
    task_form: Optional[TaskFormStructured] = Field(
        None, description="Structured task form when ready"
    )
    question: Optional[str] = Field(
        None, description="Clarification question when not ready"
    )
    round: int = Field(
        ..., description="Current clarification round (0=ready, 1-2=clarifying)"
    )
    # M2 Contract: Second-round task-form-ready semantics
    task_form_ready: Optional[bool] = Field(
        None, description="M2: True if task form is ready for submission (round 2+)"
    )
    request_payload: Optional[Dict[str, Any]] = Field(
        None, description="M2: Payload for task persistence (contains task_form_text)"
    )
    task_form_payload: Optional[Dict[str, Any]] = Field(
        None, description="M2: Enriched payload for candidates/submit workflow"
    )


class ConfirmationContractRequest(BaseModel):
    task_form_payload: Dict[str, Any] = Field(
        ..., description="Complete task form with goal, disease, country, language"
    )


class BranchOption(BaseModel):
    source: str = Field(..., description="Source type: pubmed, web, or upload")


class ConfirmationContractResponse(BaseModel):
    confirmed: bool = Field(..., description="True when task form is persisted")
    request_id: str = Field(..., description="Request UUIDv4 for status queries")
    available_branches: List[BranchOption] = Field(
        ..., description="Available literature source options"
    )
