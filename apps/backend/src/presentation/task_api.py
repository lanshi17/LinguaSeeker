import json
import hashlib
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, Path as ApiPath, Query, UploadFile, File, Form
from loguru import logger
from pydantic import BaseModel, Field

from src.celery_app import celery_app
from src.database.minio_client import MinIOClient
from src.database.postgre_client import get_postgres_client
from src.database.redis_client import list_celery_task_meta
from src.domain.literature.pubmed_service import get_pubmed_service
from src.service.tasks import process_pdf_task, process_pubmed_paper_task
from src.service.dtos import (
    PubMedCandidateItem,
    PubMedCandidateSearchRequest,
    PubMedCandidateSearchResponse,
    PubMedSelectionSubmitRequest,
    PaperTaskItemResponse,
    TaskRequestCreateResponse,
    TaskRequestStatusResponse,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskListItem,
    TaskListResponse,
    TaskStatusResponse,
    ValidationErrorResponse,
    InteractionStartRequest,
    InteractionStartResponse,
    InteractionRespondRequest,
    InteractionRespondResponse,
)
from src.service.enum import TaskStatus
from src.domain.agent.interaction import InteractionAgent
from src.utils.sanitizers import sanitize_filename

router = APIRouter(prefix="/tasks", tags=["Task"])

_interaction_agent: Optional[InteractionAgent] = None


def get_interaction_agent() -> InteractionAgent:
    global _interaction_agent
    if _interaction_agent is None:
        _interaction_agent = InteractionAgent()
    return _interaction_agent


MAX_UPLOAD_FILES = 10
MAX_UPLOAD_FILE_SIZE_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_TOTAL_BYTES = 50 * 1024 * 1024
ALLOWED_SUFFIXES = {".pdf", ".docx"}


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error details.")


def _extract_task_id(meta: Dict[str, Any]) -> str:
    task_id = meta.get("task_id") or meta.get("id")
    if task_id:
        return str(task_id)
    key = meta.get("_key", "")
    if isinstance(key, str) and key.startswith("celery-task-meta-"):
        return key.replace("celery-task-meta-", "", 1)
    return ""


def _parse_date_done(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _extract_task_metrics(meta: Dict[str, Any]) -> Dict[str, Any]:
    result = meta.get("result")
    if not isinstance(result, dict):
        result = {}

    updated_at = result.get("updated_at") or meta.get("date_done")
    return {
        "file_size_bytes": result.get("file_size_bytes"),
        "processing_duration_seconds": result.get("processing_duration_seconds"),
        "created_at": result.get("created_at"),
        "updated_at": updated_at,
    }


def _safe_task_meta(async_result: AsyncResult) -> Dict[str, Any]:
    getter = getattr(async_result, "_get_task_meta", None)
    if not callable(getter):
        return {}
    try:
        meta = getter()
    except Exception as exc:
        logger.warning("Failed to read task meta for {}: {}", async_result.id, exc)
        return {}
    return meta or {}


def _build_task_list_item(meta: Dict[str, Any], include_result: bool) -> TaskListItem:
    task_id = _extract_task_id(meta)
    status = TaskStatus.from_celery(str(meta.get("status", "PENDING")))
    date_done = meta.get("date_done")
    result = None
    error = None
    metrics = _extract_task_metrics(meta)
    raw_result = meta.get("result")
    document_id = None

    if status == TaskStatus.success and include_result:
        if isinstance(raw_result, dict):
            result = raw_result

    if isinstance(raw_result, dict):
        doc_value = raw_result.get("document_id")
        if doc_value is not None:
            document_id = str(doc_value)

    if status == TaskStatus.failure:
        raw_error = raw_result
        if isinstance(raw_error, str):
            error = raw_error
        elif raw_error is not None:
            try:
                error = json.dumps(raw_error, ensure_ascii=False)
            except TypeError:
                error = str(raw_error)

    return TaskListItem(
        task_id=task_id,
        status=status,
        date_done=date_done,
        document_id=document_id,
        file_size_bytes=metrics.get("file_size_bytes"),
        processing_duration_seconds=metrics.get("processing_duration_seconds"),
        created_at=metrics.get("created_at"),
        updated_at=metrics.get("updated_at"),
        result=result,
        error=error,
    )


def _task_sort_key(item: TaskListItem) -> datetime:
    parsed = _parse_date_done(item.date_done)
    return parsed or datetime.min.replace(tzinfo=timezone.utc)


def _paper_item_model(entry: Any) -> PaperTaskItemResponse:
    duplicate_of = getattr(entry, "duplicate_of", None)
    document_id = getattr(entry, "document_id", None)
    return PaperTaskItemResponse(
        paper_task_id=str(entry.paper_task_id),
        filename=getattr(entry, "original_filename", None),
        status=getattr(entry, "status", "queued"),
        error_code=getattr(entry, "error_code", None),
        duplicate_of=str(duplicate_of) if duplicate_of else None,
        document_id=str(document_id) if document_id else None,
        celery_task_id=getattr(entry, "celery_task_id", None),
    )


def _synthetic_hash_from_pmid(pmid: str) -> str:
    return hashlib.sha256(f"pmid:{pmid}".encode("utf-8")).hexdigest()


@router.post(
    "/interaction/start",
    summary="Start interaction for task clarification",
    description=(
        "Start a clarification session with the interaction agent.\n"
        "The agent will extract structured task form fields from natural-language input.\n"
        "Returns immediately if input is clear, or asks a clarification question (max 2 rounds)."
    ),
    response_model=InteractionStartResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input."},
        500: {"model": ErrorResponse, "description": "Agent processing failed."},
    },
)
async def start_interaction(payload: InteractionStartRequest) -> InteractionStartResponse:
    if not payload.user_input or not payload.user_input.strip():
        raise HTTPException(status_code=400, detail="user_input is required")

    agent = get_interaction_agent()
    try:
        result = await agent.start_interaction(payload.user_input)
        return InteractionStartResponse(**result)
    except Exception as exc:
        logger.exception("Interaction agent start failed: {}", exc)
        raise HTTPException(status_code=500, detail="Agent processing failed")


@router.post(
    "/interaction/respond",
    summary="Respond to clarification question",
    description=(
        "Continue a clarification session by responding to the agent's question.\n"
        "Returns structured task form when ready, or asks another question (max 2 rounds total)."
    ),
    response_model=InteractionRespondResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid session_id or user_response."},
        404: {"model": ErrorResponse, "description": "Session not found."},
        500: {"model": ErrorResponse, "description": "Agent processing failed."},
    },
)
async def respond_interaction(payload: InteractionRespondRequest) -> InteractionRespondResponse:
    if not payload.user_response or not payload.user_response.strip():
        raise HTTPException(status_code=400, detail="user_response is required")

    agent = get_interaction_agent()
    try:
        result = await agent.respond_interaction(payload.session_id, payload.user_response)
        return InteractionRespondResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Interaction agent respond failed: {}", exc)
        raise HTTPException(status_code=500, detail="Agent processing failed")


@router.post(
    "",
    summary="Create a task",
    description=(
        "Create a background processing task.\n"
        "Request body: JSON with file_paths and optional output_root.\n"
        "Response body: task id and initial status."
    ),
    response_model=TaskCreateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input."},
        503: {"model": ErrorResponse, "description": "Task queue unavailable."},
        422: {"model": ValidationErrorResponse, "description": "Validation error."},
    },
)
def create_task(payload: TaskCreateRequest) -> TaskCreateResponse:
    """Queue a new processing task and return the task metadata."""
    if not payload.file_paths:
        raise HTTPException(status_code=400, detail="file_paths is required")

    try:
        logger.debug(
            "Queueing task for file_paths: {} output_root: {}",
            payload.file_paths,
            payload.output_root,
        )
        async_result = process_pdf_task.delay(payload.file_paths, payload.output_root)
    except Exception as exc:
        logger.exception("Failed to queue task: {}", exc)
        raise HTTPException(status_code=503, detail="Task queue unavailable")
    logger.debug("Task queued: {} status: {}", async_result.id, async_result.status)
    return TaskCreateResponse(
        task_id=async_result.id,
        status=TaskStatus.from_celery(async_result.status),
    )


@router.post(
    "/requests/pubmed/candidates",
    summary="Search PubMed candidates",
    description="Search PubMed candidate papers by task form and filters (MVP source: pubmed only).",
    response_model=PubMedCandidateSearchResponse,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Invalid query or unsupported source/country.",
        },
        504: {"model": ErrorResponse, "description": "PubMed fetch timeout."},
    },
)
async def search_pubmed_candidates(
    payload: PubMedCandidateSearchRequest,
) -> PubMedCandidateSearchResponse:
    if payload.source.lower() != "pubmed":
        raise HTTPException(status_code=400, detail="Fetch no result: source must be pubmed in MVP")
    query = f"{payload.target} {payload.disease}".strip()
    if not query:
        raise HTTPException(
            status_code=400, detail="INPUT_INVALID: target and disease are required"
        )
    service = get_pubmed_service()
    try:
        rows = await service.search_candidates(
            query=query,
            country=payload.country,
            candidate_limit=payload.candidate_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.warning("PubMed candidate fetch failed: {}", exc)
        raise HTTPException(status_code=504, detail="Fetch timeout while querying PubMed")

    if not rows:
        raise HTTPException(status_code=400, detail="Fetch no result from PubMed")

    return PubMedCandidateSearchResponse(
        task_form=payload.task_form,
        candidates=[
            PubMedCandidateItem(
                pmid=item.pmid,
                title=item.title,
                journal=item.journal,
                pub_date=item.pub_date,
            )
            for item in rows
        ],
    )


@router.post(
    "/requests/pubmed/submit",
    summary="Submit selected PubMed papers",
    description="Create request and paper tasks from selected PubMed candidates (1~10), with per-paper dedup and task queueing.",
    response_model=TaskRequestCreateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid selection or unsupported source."},
        503: {"model": ErrorResponse, "description": "Dependency unavailable."},
    },
)
def submit_pubmed_selection(payload: PubMedSelectionSubmitRequest) -> TaskRequestCreateResponse:
    if payload.source.lower() != "pubmed":
        raise HTTPException(status_code=400, detail="Fetch no result: source must be pubmed in MVP")
    pmids = [str(p).strip() for p in payload.selected_pmids if str(p).strip()]
    if not pmids:
        raise HTTPException(status_code=400, detail="INPUT_INVALID: selected_pmids is required")
    if len(pmids) > 10:
        raise HTTPException(status_code=400, detail="INPUT_INVALID: selected_pmids max is 10")

    postgres = get_postgres_client()
    request_entry = postgres.create_task_request(
        task_form_text=payload.task_form,
        status="queued",
        metadata={
            "entry": "pubmed",
            "target": payload.target,
            "disease": payload.disease,
            "country": payload.country,
            "language": payload.language,
            "selected_count": len(pmids),
        },
    )

    paper_entries: List[Any] = []
    for pmid in pmids:
        existing_document = postgres.get_document_by_pmid(pmid)
        synthetic_hash = _synthetic_hash_from_pmid(pmid)
        historical_paper = postgres.find_latest_paper_task_by_hash(synthetic_hash)

        if existing_document is not None:
            paper_entry = postgres.create_paper_task(
                request_id=request_entry.request_id,
                document_id=existing_document.document_id,
                original_filename=f"PMID:{pmid}",
                file_hash=synthetic_hash,
                status="success",
                error_code="FILE_DUPLICATE",
                duplicate_of=(historical_paper.paper_task_id if historical_paper else None),
            )
            postgres.append_paper_task_log(
                paper_entry.paper_task_id,
                status="success",
                node="dedup",
                error_code="FILE_DUPLICATE",
                message=f"Duplicate PMID detected: {pmid}",
            )
            paper_entries.append(paper_entry)
            continue

        document = postgres.create_document(
            title=f"PMID:{pmid}",
            original_filename=f"PMID:{pmid}",
            pmid=pmid,
            local_path=None,
            file_hash=synthetic_hash,
            status="queued",
        )
        paper_entry = postgres.create_paper_task(
            request_id=request_entry.request_id,
            document_id=document.document_id,
            original_filename=f"PMID:{pmid}",
            file_hash=synthetic_hash,
            status="queued",
        )
        postgres.append_paper_task_log(
            paper_entry.paper_task_id,
            status="queued",
            node="acquisition",
            message=f"PubMed paper queued: {pmid}",
            payload={"pmid": pmid},
        )

        async_result = process_pubmed_paper_task.apply_async(
            args=[
                pmid,
                str(document.document_id),
                str(paper_entry.paper_task_id),
                str(request_entry.request_id),
            ],
        )
        paper_entry = postgres.update_paper_task(
            paper_entry.paper_task_id,
            celery_task_id=async_result.id,
        )
        paper_entries.append(paper_entry)

    request_entry = postgres.refresh_task_request_status(request_entry.request_id)
    return TaskRequestCreateResponse(
        request_id=str(request_entry.request_id),
        status=request_entry.status,
        papers=[_paper_item_model(item) for item in paper_entries],
    )


@router.post(
    "/requests/upload",
    summary="Create request by upload",
    description=(
        "Create a request with natural-language task form and upload files (PDF/DOCX).\n"
        "Applies global SHA-256 dedup, one Celery task per non-duplicate paper, and request-level status aggregation."
    ),
    response_model=TaskRequestCreateResponse,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Invalid input or upload constraints violated.",
        },
        503: {"model": ErrorResponse, "description": "Storage/database/queue unavailable."},
    },
)
async def create_task_request_by_upload(
    task_form: str = Form(..., description="Natural-language task form text."),
    files: List[UploadFile] = File(..., description="Uploaded files (PDF/DOCX)."),
) -> TaskRequestCreateResponse:
    normalized_form = (task_form or "").strip()
    if not normalized_form:
        raise HTTPException(status_code=400, detail="Task form text is required")
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")
    if len(files) > MAX_UPLOAD_FILES:
        raise HTTPException(status_code=400, detail=f"Too many files: max {MAX_UPLOAD_FILES}")

    try:
        postgres = get_postgres_client()
        minio = MinIOClient()
    except Exception as exc:
        logger.exception("Failed to initialize dependencies for upload request: {}", exc)
        raise HTTPException(status_code=503, detail="Dependency unavailable")

    request_entry = postgres.create_task_request(
        task_form_text=normalized_form,
        status="queued",
        metadata={"entry": "upload", "paper_count": len(files)},
    )

    total_bytes = 0
    paper_entries: List[Any] = []

    for upload in files:
        filename = sanitize_filename(upload.filename or "")
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise HTTPException(status_code=400, detail="Unsupported file type. Allowed: PDF, DOCX")

        payload = await upload.read()
        file_size = len(payload)
        if file_size > MAX_UPLOAD_FILE_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="File too large. Max 10MB per file")
        total_bytes += file_size
        if total_bytes > MAX_UPLOAD_TOTAL_BYTES:
            raise HTTPException(status_code=400, detail="Total upload size exceeded. Max 50MB")

        file_hash = hashlib.sha256(payload).hexdigest()
        existing_document = postgres.find_document_by_hash(file_hash)
        historical_paper = postgres.find_latest_paper_task_by_hash(file_hash)

        if existing_document is not None:
            paper_entry = postgres.create_paper_task(
                request_id=request_entry.request_id,
                document_id=existing_document.document_id,
                original_filename=filename or None,
                file_hash=file_hash,
                status="success",
                error_code="FILE_DUPLICATE",
                duplicate_of=(historical_paper.paper_task_id if historical_paper else None),
            )
            postgres.append_paper_task_log(
                paper_entry.paper_task_id,
                status="success",
                node="dedup",
                error_code="FILE_DUPLICATE",
                message="Duplicate file detected by SHA-256",
            )
            paper_entries.append(paper_entry)
            continue

        try:
            storage_key = MinIOClient.build_literature_object_key(
                file_hash=file_hash,
                original_filename=filename or f"{file_hash}{suffix}",
            )
            upload_ref = await minio.upload_literature_upload(
                storage_key=storage_key,
                payload=payload,
                content_type=upload.content_type or "application/octet-stream",
                metadata={
                    "hash": file_hash,
                    "uploaded_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as exc:
            logger.exception("Failed to upload file to object storage: {}", exc)
            raise HTTPException(status_code=503, detail="Failed to store uploaded file")

        document = postgres.create_document(
            title=filename or file_hash,
            original_filename=filename or None,
            local_path=upload_ref.object_key,
            file_hash=file_hash,
            status="queued",
        )
        paper_entry = postgres.create_paper_task(
            request_id=request_entry.request_id,
            document_id=document.document_id,
            original_filename=filename or None,
            file_hash=file_hash,
            status="queued",
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(payload)
            tmp_path = tmp_file.name

        try:
            async_result = process_pdf_task.apply_async(
                args=[[tmp_path]],
                kwargs={
                    "file_hash": file_hash,
                    "document_id": str(document.document_id),
                    "paper_task_id": str(paper_entry.paper_task_id),
                    "request_id": str(request_entry.request_id),
                },
            )
        except Exception as exc:
            logger.exception("Failed to enqueue paper task {}: {}", paper_entry.paper_task_id, exc)
            postgres.update_paper_task(
                paper_entry.paper_task_id,
                status="failed",
                error_code="INTERNAL_ERROR",
            )
            postgres.append_paper_task_log(
                paper_entry.paper_task_id,
                status="failed",
                node="queue",
                error_code="INTERNAL_ERROR",
                message="Task queue unavailable",
            )
            raise HTTPException(status_code=503, detail="Task queue unavailable")

        paper_entry = postgres.update_paper_task(
            paper_entry.paper_task_id,
            celery_task_id=async_result.id,
        )
        postgres.append_paper_task_log(
            paper_entry.paper_task_id,
            status="queued",
            node="queue",
            message="Paper task queued",
            payload={"celery_task_id": async_result.id},
        )
        paper_entries.append(paper_entry)

    request_entry = postgres.refresh_task_request_status(request_entry.request_id)
    return TaskRequestCreateResponse(
        request_id=str(request_entry.request_id),
        status=request_entry.status,
        papers=[_paper_item_model(item) for item in paper_entries],
    )


@router.get(
    "/requests/{request_id}",
    summary="Get request status",
    description="Fetch aggregated request status and all paper task states.",
    response_model=TaskRequestStatusResponse,
    responses={404: {"model": ErrorResponse, "description": "Request not found."}},
)
def get_task_request_status(
    request_id: str = ApiPath(..., description="Request UUIDv4."),
) -> TaskRequestStatusResponse:
    try:
        request_uuid = UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid request_id")

    postgres = get_postgres_client()
    request_entry = postgres.refresh_task_request_status(request_uuid)
    if request_entry is None:
        raise HTTPException(status_code=404, detail="Request not found")
    papers = postgres.list_paper_tasks_by_request(request_uuid)
    return TaskRequestStatusResponse(
        request_id=str(request_entry.request_id),
        status=request_entry.status,
        papers=[_paper_item_model(item) for item in papers],
    )


@router.get(
    "/{task_id}",
    summary="Get task status",
    description=(
        "Fetch task status and document reference by task id.\n"
        "Response body includes status plus document_id or error when available."
    ),
    response_model=TaskStatusResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Task not found."},
    },
)
def get_task_status(
    task_id: str = ApiPath(..., description="Celery task id."),
) -> TaskStatusResponse:
    """Return latest task status from Celery backend."""
    logger.debug("Fetching task status for task_id: {}", task_id)
    async_result = AsyncResult(task_id, app=celery_app)

    if async_result is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    meta = _safe_task_meta(async_result)
    metrics = _extract_task_metrics(meta)
    response = TaskStatusResponse(
        task_id=task_id,
        status=TaskStatus.from_celery(async_result.status),
        document_id=None,
        file_size_bytes=metrics.get("file_size_bytes"),
        processing_duration_seconds=metrics.get("processing_duration_seconds"),
        created_at=metrics.get("created_at"),
        updated_at=metrics.get("updated_at"),
        error=None,
    )
    if async_result.failed():
        response.error = str(async_result.result)
        logger.debug("Task failed: {} error: {}", task_id, response.error)
    elif async_result.successful():
        result_payload = async_result.result
        if isinstance(result_payload, dict):
            response.file_size_bytes = response.file_size_bytes or result_payload.get(
                "file_size_bytes"
            )
            response.processing_duration_seconds = (
                response.processing_duration_seconds
                or result_payload.get("processing_duration_seconds")
            )
            response.created_at = response.created_at or result_payload.get("created_at")
            response.updated_at = response.updated_at or result_payload.get("updated_at")
            doc_value = result_payload.get("document_id")
            if doc_value is not None:
                response.document_id = str(doc_value)
        logger.debug("Task succeeded: {}", task_id)
    else:
        logger.debug("Task status: {} status: {}", task_id, async_result.status)

    return response


@router.get(
    "",
    summary="List tasks",
    description=(
        "List recent tasks with optional filtering and pagination.\n"
        "Response body contains items, next_cursor and count."
    ),
    response_model=TaskListResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid query parameters."},
    },
)
def list_tasks(
    limit: int = Query(50, ge=1, le=200, description="Max number of items to return."),
    cursor: int = Query(0, ge=0, description="Scan cursor for pagination."),
    status: Optional[TaskStatus] = Query(None, description="Filter by task status."),
    include_result: bool = Query(False, description="Include result payloads in list items."),
) -> TaskListResponse:
    """Return a paginated list of tasks from Redis task meta."""
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")

    items: list[TaskListItem] = []
    next_cursor = cursor
    scan_count = min(200, limit)

    while len(items) < limit:
        next_cursor, metas = list_celery_task_meta(cursor=next_cursor, count=scan_count)
        if not metas and next_cursor == 0:
            break

        for meta in metas:
            item = _build_task_list_item(meta, include_result)
            if not item.task_id:
                continue
            if status and item.status != status:
                continue
            items.append(item)
            if len(items) >= limit:
                break

        if next_cursor == 0:
            break

    items.sort(key=_task_sort_key, reverse=True)
    return TaskListResponse(items=items, next_cursor=next_cursor, count=len(items))
