# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportDeprecated=false, reportUnusedCallResult=false, reportCallInDefaultInitializer=false, reportUnnecessaryComparison=false, reportMissingTypeStubs=false, reportUnnecessaryCast=false

import json
import hashlib
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, cast
from uuid import UUID

from celery.result import AsyncResult
from fastapi import (
    APIRouter,
    HTTPException,
    Path as ApiPath,
    Query,
    Request,
    UploadFile,
    File,
    Form,
)
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from src.celery_app import celery_app
from src.infrastructure.enum import MinioBucketNameEnum
from src.infrastructure.minio import MinIOClient
from src.infrastructure.postgres import get_postgres_client
from src.infrastructure.redis import list_celery_task_meta
from src.domain.literature import get_literature_acquisition_agent, get_pubmed_service
from src.api.dependencies import contract_http_exception
from src.services.task_manager import (
    process_pdf_task,
    process_pubmed_paper_task,
    resume_supervisor_task,
    process_web_page_task,
)
from src.services.dtos import (
    PubMedCandidateItem,
    PubMedCandidateSearchRequest,
    PubMedCandidateSearchResponse,
    PubMedSelectionSubmitRequest,
    WebLiteratureCrawlRequest,
    PaperTaskItemResponse,
    TaskRequestCreateResponse,
    TaskRequestStatusResponse,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskListItem,
    TaskListResponse,
    PaperTaskDetailResponse,
    TaskStatusResponse,
    ValidationErrorResponse,
    InteractionStartRequest,
    InteractionStartResponse,
    InteractionRespondRequest,
    InteractionRespondResponse,
    ConfirmationContractRequest,
    ConfirmationContractResponse,
    BranchOption,
    SourceProviderStatsResponse,
    TaskRequestSourceStatsResponse,
)
from src.services.enum import (
    TaskStatus,
    WorkflowStatus,
    calculate_progress_percentage,
    coerce_workflow_status,
    normalize_processing_steps,
    workflow_status_description,
)
from src.services.traceability import build_trace_chain, normalize_warning_codes
from src.domain.agent.interaction import InteractionAgent
from src.utils.sanitizers import sanitize_filename

router = APIRouter(prefix="/tasks", tags=["Task"])

_interaction_agent: Optional[InteractionAgent] = None


def get_interaction_agent() -> InteractionAgent:
    global _interaction_agent
    if _interaction_agent is None:
        _interaction_agent = InteractionAgent()
    return _interaction_agent


def _shape_start_response(agent_result: Dict[str, Any]) -> Dict[str, Any]:
    """Shape agent result for M2 contract: add needs_clarification and clarification_question."""
    shaped = dict(agent_result)
    if not shaped.get("ready"):
        shaped["needs_clarification"] = True
        shaped["clarification_question"] = shaped.get("question")
    return shaped


def _shape_respond_response(agent_result: Dict[str, Any]) -> Dict[str, Any]:
    """Shape agent result for M2 contract: add task_form_ready, request_payload, task_form_payload."""
    shaped = dict(agent_result)
    if shaped.get("ready"):
        shaped["task_form_ready"] = True
        task_form = shaped.get("task_form")
        if isinstance(task_form, dict):
            required_fields = ("goal", "disease", "country", "language")
            missing_fields = [
                field for field in required_fields if not task_form.get(field)
            ]
            if missing_fields:
                raise contract_http_exception(
                    500,
                    "INTERNAL_ERROR",
                    f"Interaction agent returned incomplete task form: missing {', '.join(missing_fields)}",
                )
            shaped["request_payload"] = {
                "task_form_text": json.dumps(task_form, ensure_ascii=False)
            }
            shaped["task_form_payload"] = {
                "goal": task_form["goal"],
                "disease": task_form["disease"],
                "country": task_form["country"],
                "language": task_form["language"],
            }
    return shaped


MAX_UPLOAD_FILES = 10
MAX_UPLOAD_FILE_SIZE_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_TOTAL_BYTES = 50 * 1024 * 1024


async def _prevalidate_upload_files(files: List[UploadFile]) -> List[Dict[str, Any]]:
    total_bytes = 0
    prepared_uploads: List[Dict[str, Any]] = []

    for upload in files:
        filename = sanitize_filename(upload.filename or "")
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise contract_http_exception(
                400,
                "FILE_TYPE_UNSUPPORTED",
                "Unsupported file type. Allowed: PDF, DOCX",
            )

        payload = await upload.read()
        file_size = len(payload)
        if file_size > MAX_UPLOAD_FILE_SIZE_BYTES:
            raise contract_http_exception(
                400, "FILE_TOO_LARGE", "File too large. Max 10MB per file"
            )

        total_bytes += file_size
        if total_bytes > MAX_UPLOAD_TOTAL_BYTES:
            raise contract_http_exception(
                400,
                "FILE_TOO_LARGE",
                "Total upload size exceeded. Max 50MB",
            )

        prepared_uploads.append(
            {
                "upload": upload,
                "filename": filename,
                "suffix": suffix,
                "payload": payload,
                "file_hash": hashlib.sha256(payload).hexdigest(),
            }
        )

    return prepared_uploads


def _has_successful_historical_paper(historical_paper: Any) -> bool:
    return (
        historical_paper is not None
        and str(getattr(historical_paper, "status", "")) == "success"
    )


def _create_duplicate_paper_entry(
    postgres: Any,
    *,
    request_id: Any,
    document_id: Any,
    original_filename: Optional[str],
    file_hash: str,
    historical_paper: Any,
    message: str,
) -> Any:
    paper_entry = postgres.create_paper_task(
        request_id=request_id,
        document_id=document_id,
        original_filename=original_filename,
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
        message=message,
    )
    return paper_entry


def _create_managed_upload_temp_file(
    *,
    payload: bytes,
    suffix: str,
    paper_task_id: Any,
) -> str:
    workdir = Path.cwd() / "tmp" / f"run_upload_{paper_task_id}"
    workdir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=workdir, delete=False, suffix=suffix
    ) as tmp_file:
        tmp_file.write(payload)
        return tmp_file.name


def _cleanup_upload_temp_file(temp_path: Optional[str]) -> None:
    if not temp_path:
        return
    temp_file = Path(temp_path)
    try:
        if temp_file.exists():
            temp_file.unlink()
        parent = temp_file.parent
        if parent.name.startswith("run_upload_") and parent.exists():
            for entry in parent.iterdir():
                if entry.exists():
                    return
            parent.rmdir()
    except OSError as exc:
        logger.warning("Failed to cleanup temporary upload file {}: {}", temp_path, exc)


ALLOWED_SUFFIXES = {".pdf", ".docx"}


def _uuid_str(value: Any) -> str:
    return str(cast(UUID, cast(object, value)))


def _uuid_value(value: Any) -> UUID:
    return cast(UUID, cast(object, value))


def _uuid_optional_str(value: Any) -> Optional[str]:
    return None if value is None else _uuid_str(value)


def _status_str(value: Any, default: str = "queued") -> str:
    raw = cast(Optional[str], cast(object, value))
    return raw or default


def _celery_task(task: Any) -> Any:
    return cast(Any, task)


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
    if isinstance(meta, dict):
        return meta
    return {}


def _as_iso_datetime(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, str):
        return value
    return None


def _as_bool_flag(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return None


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


def _aggregate_source_stats(papers: List[Any]) -> Dict[str, Any]:
    provider_stats: Dict[str, Dict[str, int]] = {}
    fallback_count = 0

    for paper in papers:
        node_trace = getattr(paper, "node_trace", None)
        if not isinstance(node_trace, dict):
            continue
        acquisition_detail = node_trace.get("acquisition_detail")
        if not isinstance(acquisition_detail, dict):
            continue
        source_trace = acquisition_detail.get("source_trace")
        if not isinstance(source_trace, list):
            continue

        had_previous_failure = False
        used_fallback = False
        for attempt in source_trace:
            if not isinstance(attempt, dict):
                continue
            provider = str(attempt.get("provider") or "").strip()
            if not provider:
                continue
            stats = provider_stats.setdefault(
                provider,
                {
                    "attempts": 0,
                    "hits": 0,
                    "search_hits": 0,
                    "download_hits": 0,
                    "errors": 0,
                    "fallback_hits": 0,
                },
            )
            stats["attempts"] += 1

            success = bool(attempt.get("success"))
            items_count = int(attempt.get("items_count") or 0)
            downloads_count = int(attempt.get("downloads_count") or 0)
            error = attempt.get("error")

            if error:
                stats["errors"] += 1
                had_previous_failure = True
                continue

            if success and (items_count > 0 or downloads_count > 0):
                stats["hits"] += 1
                if items_count > 0:
                    stats["search_hits"] += 1
                if downloads_count > 0:
                    stats["download_hits"] += 1
                if had_previous_failure:
                    stats["fallback_hits"] += 1
                    used_fallback = True

        if used_fallback:
            fallback_count += 1

    return {
        "paper_count": len(papers),
        "fallback_count": fallback_count,
        "providers": {
            provider: SourceProviderStatsResponse(**stats)
            for provider, stats in provider_stats.items()
        },
    }


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
async def start_interaction(
    payload: InteractionStartRequest,
) -> InteractionStartResponse:
    if not payload.user_input or not payload.user_input.strip():
        raise contract_http_exception(400, "INPUT_INVALID", "user_input is required")

    agent = get_interaction_agent()
    try:
        result = await agent.start_interaction(payload.user_input)
        shaped_result = _shape_start_response(result)
        return InteractionStartResponse(**shaped_result)
    except Exception as exc:
        logger.exception("Interaction agent start failed: {}", exc)
        raise contract_http_exception(500, "INTERNAL_ERROR", "Agent processing failed")


@router.post(
    "/interaction/respond",
    summary="Respond to clarification question",
    description=(
        "Continue a clarification session by responding to the agent's question.\n"
        "Returns structured task form when ready, or asks another question (max 2 rounds total)."
    ),
    response_model=InteractionRespondResponse,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Invalid session_id or user_response.",
        },
        404: {"model": ErrorResponse, "description": "Session not found."},
        500: {"model": ErrorResponse, "description": "Agent processing failed."},
    },
)
async def respond_interaction(
    payload: InteractionRespondRequest,
) -> InteractionRespondResponse:
    if not payload.user_response or not payload.user_response.strip():
        raise contract_http_exception(400, "INPUT_INVALID", "user_response is required")

    agent = get_interaction_agent()
    try:
        result = await agent.respond_interaction(
            payload.session_id, payload.user_response
        )
        shaped_result = _shape_respond_response(result)
        return InteractionRespondResponse(**shaped_result)
    except ValueError as exc:
        raise contract_http_exception(404, "RESOURCE_NOT_FOUND", str(exc))
    except Exception as exc:
        logger.exception("Interaction agent respond failed: {}", exc)
        raise contract_http_exception(500, "INTERNAL_ERROR", "Agent processing failed")


@router.post(
    "/interaction/confirm",
    summary="Confirm task form and persist request",
    description=(
        "Confirm a complete task form and persist it to the task_request table.\n"
        "Required fields: goal, disease, country, language in task_form_payload.\n"
        "Returns request_id for status tracking and available_branches for M2 workflow."
    ),
    response_model=ConfirmationContractResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Missing required fields."},
        500: {"model": ErrorResponse, "description": "Database persistence failed."},
    },
)
async def confirm_task_form(
    payload: ConfirmationContractRequest,
) -> ConfirmationContractResponse:
    """Validate and persist complete task form, return request_id and branches."""
    task_form_payload = payload.task_form_payload

    # Validate required fields
    required_fields = {"goal", "disease", "country", "language"}
    missing_fields = [
        field for field in required_fields if not task_form_payload.get(field)
    ]

    if missing_fields:
        raise contract_http_exception(
            400,
            "INPUT_INVALID",
            f"Required fields missing: {', '.join(missing_fields)}",
        )

    # Persist task form to database
    postgres = get_postgres_client()
    task_form_text = json.dumps(task_form_payload, ensure_ascii=False)
    metadata = {
        "source": "interaction",
        "interaction_flow": True,
    }

    try:
        request_entry = postgres.create_task_request(
            task_form_text=task_form_text,
            status="queued",
            metadata=metadata,
        )
        request_id = _uuid_str(request_entry.request_id)
    except Exception as exc:
        logger.exception("Failed to persist task form: {}", exc)
        raise contract_http_exception(
            500, "INTERNAL_ERROR", "Failed to persist task form"
        )

    # Return confirmation with available branches
    available_branches = [
        BranchOption(source="pubmed"),
        BranchOption(source="web"),
        BranchOption(source="upload"),
    ]

    return ConfirmationContractResponse(
        confirmed=True,
        request_id=request_id,
        available_branches=available_branches,
    )


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
        raise contract_http_exception(400, "INPUT_INVALID", "file_paths is required")

    try:
        logger.debug(
            "Queueing task for file_paths: {} output_root: {}",
            payload.file_paths,
            payload.output_root,
        )
        async_result = _celery_task(process_pdf_task).delay(
            payload.file_paths, payload.output_root
        )
    except Exception as exc:
        logger.exception("Failed to queue task: {}", exc)
        raise contract_http_exception(503, "INTERNAL_ERROR", "Task queue unavailable")
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
    # M2 Contract: accept either request_id (reuse) or task_form (legacy)
    if not payload.request_id and not payload.task_form:
        raise contract_http_exception(
            400, "INPUT_INVALID", "Either request_id or task_form is required"
        )

    # Determine task_form and request_id for response
    response_request_id = None
    response_task_form = ""

    if payload.request_id:
        # M2 Reuse path: fetch confirmed request
        postgres = get_postgres_client()
        request_entry = postgres.get_task_request(payload.request_id)
        if request_entry is None:
            raise contract_http_exception(
                400, "INPUT_INVALID", f"Request {payload.request_id} not found"
            )
        response_request_id = payload.request_id
        task_form_text = request_entry.task_form_text
        response_task_form = str(task_form_text) if task_form_text is not None else ""
    else:
        # Legacy path: use provided task_form (no request_id)
        response_task_form = (payload.task_form or "").strip()

    if payload.source.lower() != "pubmed":
        raise contract_http_exception(
            400, "INPUT_INVALID", "source must be pubmed in MVP"
        )
    query = f"{payload.target} {payload.disease}".strip()
    if not query:
        raise contract_http_exception(
            400, "INPUT_INVALID", "target and disease are required"
        )
    service = get_pubmed_service()
    try:
        rows = await service.search_candidates(
            query=query,
            country=payload.country,
            candidate_limit=payload.candidate_limit,
        )
    except ValueError as exc:
        raise contract_http_exception(400, "INPUT_INVALID", str(exc))
    except Exception as exc:
        logger.exception("PubMed candidate fetch failed: {}", exc)
        raise contract_http_exception(
            504, "FETCH_TIMEOUT", "Fetch timeout while querying PubMed"
        )

    if not rows:
        raise contract_http_exception(
            400, "FETCH_NO_RESULT", "Fetch no result from PubMed"
        )

    return PubMedCandidateSearchResponse(
        request_id=response_request_id,
        task_form=response_task_form,
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
        400: {
            "model": ErrorResponse,
            "description": "Invalid selection or unsupported source.",
        },
        503: {"model": ErrorResponse, "description": "Dependency unavailable."},
    },
)
def submit_pubmed_selection(
    payload: PubMedSelectionSubmitRequest,
) -> TaskRequestCreateResponse:
    if payload.source.lower() != "pubmed":
        raise contract_http_exception(
            400, "INPUT_INVALID", "source must be pubmed in MVP"
        )
    pmids = [str(p).strip() for p in payload.selected_pmids if str(p).strip()]
    if not pmids:
        raise contract_http_exception(
            400, "INPUT_INVALID", "selected_pmids is required"
        )
    if len(pmids) > 10:
        raise contract_http_exception(400, "INPUT_INVALID", "selected_pmids max is 10")

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
    request_entry_id = _uuid_str(request_entry.request_id)

    paper_entries: List[Any] = []
    for pmid in pmids:
        existing_document = postgres.get_document_by_pmid(pmid)
        synthetic_hash = _synthetic_hash_from_pmid(pmid)
        historical_paper = postgres.find_latest_paper_task_by_hash(synthetic_hash)
        existing_document_id = (
            _uuid_optional_str(existing_document.document_id)
            if existing_document is not None
            else None
        )

        if existing_document is not None and _has_successful_historical_paper(
            historical_paper
        ):
            paper_entry = _create_duplicate_paper_entry(
                postgres,
                request_id=request_entry_id,
                document_id=existing_document_id,
                original_filename=f"PMID:{pmid}",
                file_hash=synthetic_hash,
                historical_paper=historical_paper,
                message=f"Duplicate PMID detected: {pmid}",
            )
            paper_entries.append(paper_entry)
            continue

        try:
            document = postgres.create_document(
                title=f"PMID:{pmid}",
                original_filename=f"PMID:{pmid}",
                pmid=pmid,
                local_path=None,
                file_hash=synthetic_hash,
                status="queued",
            )
        except IntegrityError as exc:
            logger.warning("PubMed document create conflict for {}: {}", pmid, exc)
            existing_document = postgres.get_document_by_pmid(
                pmid
            ) or postgres.find_document_by_hash(synthetic_hash)
            historical_paper = postgres.find_latest_paper_task_by_hash(synthetic_hash)
            if existing_document is not None and _has_successful_historical_paper(
                historical_paper
            ):
                paper_entry = _create_duplicate_paper_entry(
                    postgres,
                    request_id=request_entry_id,
                    document_id=existing_document_id,
                    original_filename=f"PMID:{pmid}",
                    file_hash=synthetic_hash,
                    historical_paper=historical_paper,
                    message=f"Duplicate PMID detected after concurrent create: {pmid}",
                )
            else:
                paper_entry = postgres.create_paper_task(
                    request_id=request_entry_id,
                    document_id=existing_document_id,
                    original_filename=f"PMID:{pmid}",
                    file_hash=synthetic_hash,
                    status="failed",
                    error_code="INTERNAL_ERROR",
                )
                postgres.append_paper_task_log(
                    _uuid_str(paper_entry.paper_task_id),
                    status="failed",
                    node="document",
                    error_code="INTERNAL_ERROR",
                    message="Concurrent document creation conflict",
                )
            paper_entries.append(paper_entry)
            continue
        document_id = _uuid_str(document.document_id)
        paper_entry = postgres.create_paper_task(
            request_id=request_entry_id,
            document_id=document_id,
            original_filename=f"PMID:{pmid}",
            file_hash=synthetic_hash,
            status="queued",
        )
        paper_task_id = _uuid_str(paper_entry.paper_task_id)
        postgres.append_paper_task_log(
            paper_task_id,
            status="queued",
            node="acquisition",
            message=f"PubMed paper queued: {pmid}",
            payload={"pmid": pmid},
        )

        async_result = _celery_task(process_pubmed_paper_task).apply_async(
            args=[
                pmid,
                document_id,
                paper_task_id,
                request_entry_id,
            ],
        )
        paper_entry = postgres.update_paper_task(
            paper_task_id,
            celery_task_id=async_result.id,
        )
        paper_entries.append(paper_entry)

    request_entry = postgres.refresh_task_request_status(request_entry_id)
    return TaskRequestCreateResponse(
        request_id=str(getattr(request_entry, "request_id", request_entry_id)),
        status=_status_str(getattr(request_entry, "status", None)),
        papers=[_paper_item_model(item) for item in paper_entries],
    )


@router.post(
    "/requests/web/crawl",
    summary="Create request by web crawl",
    description=(
        "Create a request from selected web URLs, apply URL-fingerprint dedup, "
        "and enqueue one Celery task per non-duplicate page."
    ),
    response_model=TaskRequestCreateResponse,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Invalid input or unsupported source.",
        },
        503: {"model": ErrorResponse, "description": "Database/queue unavailable."},
    },
)
def create_task_request_by_web_crawl(
    payload: WebLiteratureCrawlRequest,
) -> TaskRequestCreateResponse:
    if payload.source.lower() != "web":
        raise contract_http_exception(400, "INPUT_INVALID", "source must be web")

    urls = [str(url).strip() for url in payload.urls if str(url).strip()]
    if not urls:
        raise contract_http_exception(400, "INPUT_INVALID", "urls is required")
    if len(urls) > 10:
        raise contract_http_exception(400, "INPUT_INVALID", "urls max is 10")

    agent = get_literature_acquisition_agent()
    plan_items = agent.plan_web_request(urls)
    postgres = get_postgres_client()
    request_entry = postgres.create_task_request(
        task_form_text=payload.task_form,
        status="queued",
        metadata={
            "entry": "web",
            "source": payload.source,
            "url_count": len(plan_items),
            "force_refresh": payload.force_refresh,
        },
    )
    request_id = str(request_entry.request_id)

    paper_entries: List[Any] = []
    for plan_item in plan_items:
        existing_document = None
        historical_paper = None
        if not payload.force_refresh:
            existing_document = postgres.find_document_by_hash(plan_item.fingerprint)
            historical_paper = postgres.find_latest_paper_task_by_hash(
                plan_item.fingerprint
            )

        if existing_document is not None and _has_successful_historical_paper(
            historical_paper
        ):
            existing_document_id = str(existing_document.document_id)
            duplicate_of = (
                str(historical_paper.paper_task_id) if historical_paper else None
            )
            paper_entry = postgres.create_paper_task(
                request_id=request_id,
                document_id=existing_document_id,
                original_filename=plan_item.display_name,
                file_hash=plan_item.fingerprint,
                status="success",
                error_code="FILE_DUPLICATE",
                duplicate_of=duplicate_of,
            )
            postgres.append_paper_task_log(
                str(paper_entry.paper_task_id),
                status="success",
                node="dedup",
                error_code="FILE_DUPLICATE",
                message=f"Duplicate web URL detected: {plan_item.normalized_value}",
            )
            paper_entries.append(paper_entry)
            continue

        try:
            document = postgres.create_document(
                title=plan_item.display_name,
                original_filename=plan_item.display_name,
                local_path=plan_item.normalized_value,
                file_hash=plan_item.fingerprint,
                status="queued",
                summary=f"Queued web crawl source: {plan_item.normalized_value}",
            )
        except IntegrityError as exc:
            logger.warning(
                "Web document create conflict for {}: {}",
                plan_item.normalized_value,
                exc,
            )
            existing_document = postgres.find_document_by_hash(plan_item.fingerprint)
            if payload.force_refresh and existing_document is not None:
                document_id = str(existing_document.document_id)
                paper_entry = postgres.create_paper_task(
                    request_id=request_id,
                    document_id=document_id,
                    original_filename=plan_item.display_name,
                    file_hash=plan_item.fingerprint,
                    status="queued",
                )
                paper_task_id = str(paper_entry.paper_task_id)
                postgres.append_paper_task_log(
                    paper_task_id,
                    status="queued",
                    node="acquisition",
                    message=f"Web page re-queued after document conflict: {plan_item.normalized_value}",
                    payload={"url": plan_item.normalized_value, "source": "web", "force_refresh": True},
                )
                async_result = _celery_task(process_web_page_task).apply_async(
                    args=[
                        plan_item.normalized_value,
                        document_id,
                        paper_task_id,
                        request_id,
                    ]
                )
                paper_entry = postgres.update_paper_task(
                    paper_task_id,
                    celery_task_id=async_result.id,
                )
                paper_entries.append(paper_entry)
                continue
            historical_paper = postgres.find_latest_paper_task_by_hash(
                plan_item.fingerprint
            )
            if existing_document is not None and _has_successful_historical_paper(
                historical_paper
            ):
                existing_document_id = str(existing_document.document_id)
                duplicate_of = (
                    str(historical_paper.paper_task_id) if historical_paper else None
                )
                paper_entry = postgres.create_paper_task(
                    request_id=request_id,
                    document_id=existing_document_id,
                    original_filename=plan_item.display_name,
                    file_hash=plan_item.fingerprint,
                    status="success",
                    error_code="FILE_DUPLICATE",
                    duplicate_of=duplicate_of,
                )
                postgres.append_paper_task_log(
                    str(paper_entry.paper_task_id),
                    status="success",
                    node="dedup",
                    error_code="FILE_DUPLICATE",
                    message=f"Duplicate web URL detected after concurrent create: {plan_item.normalized_value}",
                )
            else:
                paper_entry = postgres.create_paper_task(
                    request_id=request_id,
                    document_id=(
                        str(existing_document.document_id)
                        if existing_document
                        else None
                    ),
                    original_filename=plan_item.display_name,
                    file_hash=plan_item.fingerprint,
                    status="failed",
                    error_code="INTERNAL_ERROR",
                )
                postgres.append_paper_task_log(
                    str(paper_entry.paper_task_id),
                    status="failed",
                    node="document",
                    error_code="INTERNAL_ERROR",
                    message="Concurrent document creation conflict",
                )
            paper_entries.append(paper_entry)
            continue
        document_id = str(document.document_id)
        paper_entry = postgres.create_paper_task(
            request_id=request_id,
            document_id=document_id,
            original_filename=plan_item.display_name,
            file_hash=plan_item.fingerprint,
            status="queued",
        )
        paper_task_id = str(paper_entry.paper_task_id)
        postgres.append_paper_task_log(
            paper_task_id,
            status="queued",
            node="acquisition",
            message=f"Web page queued: {plan_item.normalized_value}",
            payload={"url": plan_item.normalized_value, "source": "web"},
        )

        async_result = _celery_task(process_web_page_task).apply_async(
            args=[
                plan_item.normalized_value,
                document_id,
                paper_task_id,
                request_id,
            ]
        )
        paper_entry = postgres.update_paper_task(
            paper_task_id,
            celery_task_id=async_result.id,
        )
        paper_entries.append(paper_entry)

    request_entry = postgres.refresh_task_request_status(request_id) or request_entry
    return TaskRequestCreateResponse(
        request_id=str(getattr(request_entry, "request_id", request_id)),
        status=str(getattr(request_entry, "status", "queued")),
        papers=[_paper_item_model(item) for item in paper_entries],
    )


# TODO(P1): create_task_request_by_upload mixes sync PostgresClient calls with async MinIO calls.
#   This blocks the event loop during postgres operations under concurrent load.
#   Fix: Either wrap postgres calls with `await anyio.to_thread.run_sync()`
#   or migrate PostgresClient to AsyncSession. See architecture refactor plan.


@router.post(
    "/requests/upload",
    summary="Create request by upload",
    description=(
        "Create a request with natural-language task form and upload files (PDF/DOCX),\n"
        "or reuse a confirmed request by request_id (M2 handoff from confirmation endpoint).\n"
        "Applies global SHA-256 dedup, one Celery task per non-duplicate paper, and request-level status aggregation."
    ),
    response_model=TaskRequestCreateResponse,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Invalid input or upload constraints violated.",
        },
        503: {
            "model": ErrorResponse,
            "description": "Storage/database/queue unavailable.",
        },
    },
)
async def create_task_request_by_upload(
    request: Request,
    task_form: Optional[str] = Form(
        None, description="Natural-language task form text (legacy path)."
    ),
    request_id: Optional[str] = Form(
        None,
        description="Confirmed request_id from confirmation endpoint (M2 handoff).",
    ),
    files: List[UploadFile] = File(..., description="Uploaded files (PDF/DOCX)."),
) -> TaskRequestCreateResponse:
    # M2 Contract: either request_id (reuse path) or task_form (legacy path) required
    raw_form = await request.form()
    normalized_request_id = str(request_id or "").strip()
    task_form_supplied = "task_form" in raw_form
    if not normalized_request_id and task_form is None and not task_form_supplied:
        raise contract_http_exception(
            400, "INPUT_INVALID", "Either request_id or task_form is required"
        )
    if not normalized_request_id and task_form_supplied and not str(task_form or "").strip():
        raise contract_http_exception(422, "INPUT_INVALID", "Task form text is required")

    if not files:
        raise contract_http_exception(
            400, "INPUT_INVALID", "At least one file is required"
        )
    if len(files) > MAX_UPLOAD_FILES:
        raise contract_http_exception(
            400,
            "INPUT_INVALID",
            f"Too many files: max {MAX_UPLOAD_FILES}",
        )

    try:
        postgres = get_postgres_client()
        minio = MinIOClient()
    except Exception as exc:
        logger.exception(
            "Failed to initialize dependencies for upload request: {}", exc
        )
        raise contract_http_exception(503, "INTERNAL_ERROR", "Dependency unavailable")

    prepared_uploads = await _prevalidate_upload_files(files)

    # M2 Contract: reuse existing request if request_id provided, else create new
    if normalized_request_id:
        # Reuse path: fetch existing confirmed request
        request_entry = postgres.get_task_request(normalized_request_id)
        if request_entry is None:
            raise contract_http_exception(
                400, "INPUT_INVALID", f"Request {normalized_request_id} not found"
            )
        request_entry_id = _uuid_str(request_entry.request_id)
    else:
        # Legacy path: create new request from task_form
        normalized_form = (task_form or "").strip()
        if not normalized_form:
            raise contract_http_exception(
                422, "INPUT_INVALID", "Task form text is required"
            )
        request_entry = postgres.create_task_request(
            task_form_text=normalized_form,
            status="queued",
            metadata={"entry": "upload", "paper_count": len(prepared_uploads)},
        )
        request_entry_id = _uuid_str(request_entry.request_id)

    paper_entries: List[Any] = []

    for prepared in prepared_uploads:
        upload = prepared["upload"]
        filename = prepared["filename"]
        suffix = prepared["suffix"]
        payload = prepared["payload"]
        file_hash = prepared["file_hash"]
        existing_document = postgres.find_document_by_hash(file_hash)
        historical_paper = postgres.find_latest_paper_task_by_hash(file_hash)
        existing_document_id = (
            _uuid_optional_str(existing_document.document_id)
            if existing_document is not None
            else None
        )

        if existing_document is not None and _has_successful_historical_paper(
            historical_paper
        ):
            paper_entry = _create_duplicate_paper_entry(
                postgres,
                request_id=request_entry_id,
                document_id=existing_document_id,
                original_filename=filename or None,
                file_hash=file_hash,
                historical_paper=historical_paper,
                message="Duplicate file detected by SHA-256",
            )
            paper_entries.append(paper_entry)
            continue

        upload_ref = None
        document = None
        paper_entry = None
        tmp_path = None
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
            paper_entry = postgres.create_paper_task(
                request_id=request_entry_id,
                original_filename=filename or None,
                file_hash=file_hash,
                status="failed",
                error_code="INTERNAL_ERROR",
            )
            postgres.append_paper_task_log(
                _uuid_str(paper_entry.paper_task_id),
                status="failed",
                node="upload",
                error_code="INTERNAL_ERROR",
                message="Failed to store uploaded file",
            )
            paper_entries.append(paper_entry)
            continue

        try:
            document = postgres.create_document(
                title=filename or file_hash,
                original_filename=filename or None,
                local_path=upload_ref.object_key,
                file_hash=file_hash,
                status="queued",
            )
        except IntegrityError as exc:
            logger.warning("Document create conflict for hash {}: {}", file_hash, exc)
            existing_document = postgres.find_document_by_hash(file_hash)
            historical_paper = postgres.find_latest_paper_task_by_hash(file_hash)
            if upload_ref is not None:
                try:
                    await minio.delete_file(
                        MinioBucketNameEnum.LITERATURE_UPLOADS.value,
                        upload_ref.object_key,
                    )
                except Exception as cleanup_exc:
                    logger.warning(
                        "Failed to cleanup duplicate upload object {}: {}",
                        upload_ref.object_key,
                        cleanup_exc,
                    )
            if existing_document is not None and _has_successful_historical_paper(
                historical_paper
            ):
                paper_entry = _create_duplicate_paper_entry(
                    postgres,
                    request_id=request_entry_id,
                    document_id=existing_document_id,
                    original_filename=filename or None,
                    file_hash=file_hash,
                    historical_paper=historical_paper,
                    message="Duplicate file detected after concurrent create",
                )
            else:
                paper_entry = postgres.create_paper_task(
                    request_id=request_entry_id,
                    document_id=existing_document_id,
                    original_filename=filename or None,
                    file_hash=file_hash,
                    status="failed",
                    error_code="INTERNAL_ERROR",
                )
                postgres.append_paper_task_log(
                    _uuid_str(paper_entry.paper_task_id),
                    status="failed",
                    node="document",
                    error_code="INTERNAL_ERROR",
                    message="Concurrent document creation conflict",
                )
            paper_entries.append(paper_entry)
            continue
        except Exception as exc:
            logger.exception("Failed to create document for {}: {}", filename, exc)
            if upload_ref is not None:
                try:
                    await minio.delete_file(
                        MinioBucketNameEnum.LITERATURE_UPLOADS.value,
                        upload_ref.object_key,
                    )
                except Exception as cleanup_exc:
                    logger.warning(
                        "Failed to cleanup upload object {} after document error: {}",
                        upload_ref.object_key,
                        cleanup_exc,
                    )
            paper_entry = postgres.create_paper_task(
                request_id=request_entry_id,
                original_filename=filename or None,
                file_hash=file_hash,
                status="failed",
                error_code="INTERNAL_ERROR",
            )
            postgres.append_paper_task_log(
                _uuid_str(paper_entry.paper_task_id),
                status="failed",
                node="document",
                error_code="INTERNAL_ERROR",
                message="Failed to create document record",
            )
            paper_entries.append(paper_entry)
            continue

        document_id = _uuid_str(document.document_id)
        try:
            paper_entry = postgres.create_paper_task(
                request_id=request_entry_id,
                document_id=document_id,
                original_filename=filename or None,
                file_hash=file_hash,
                status="queued",
            )
            paper_task_id = _uuid_str(paper_entry.paper_task_id)
            tmp_path = _create_managed_upload_temp_file(
                payload=payload,
                suffix=suffix,
                paper_task_id=paper_task_id,
            )
            async_result = _celery_task(process_pdf_task).apply_async(
                args=[[tmp_path]],
                kwargs={
                    "file_hash": file_hash,
                    "document_id": document_id,
                    "paper_task_id": paper_task_id,
                    "request_id": request_entry_id,
                },
            )
        except Exception as exc:
            logger.exception(
                "Failed to enqueue paper task {}: {}",
                _uuid_str(paper_entry.paper_task_id) if paper_entry else filename,
                exc,
            )
            if paper_entry is None:
                paper_entry = postgres.create_paper_task(
                    request_id=request_entry_id,
                    document_id=_uuid_optional_str(document.document_id)
                    if document is not None
                    else None,
                    original_filename=filename or None,
                    file_hash=file_hash,
                    status="failed",
                    error_code="INTERNAL_ERROR",
                )
            else:
                paper_entry = postgres.update_paper_task(
                    _uuid_str(paper_entry.paper_task_id),
                    status="failed",
                    error_code="INTERNAL_ERROR",
                )
            if document is not None:
                postgres.update_document(
                    _uuid_value(document.document_id),
                    status="failed",
                    summary="Task queue unavailable",
                )
            _cleanup_upload_temp_file(tmp_path)
            if paper_entry is None:
                raise RuntimeError("paper entry missing after queue failure")
            failed_paper_task_id = _uuid_str(paper_entry.paper_task_id)
            postgres.append_paper_task_log(
                failed_paper_task_id,
                status="failed",
                node="queue",
                error_code="INTERNAL_ERROR",
                message="Task queue unavailable",
            )
            paper_entries.append(paper_entry)
            continue

        paper_entry = postgres.update_paper_task(
            paper_task_id,
            celery_task_id=async_result.id,
        )
        postgres.append_paper_task_log(
            paper_task_id,
            status="queued",
            node="queue",
            message="Paper task queued",
            payload={"celery_task_id": async_result.id},
        )
        paper_entries.append(paper_entry)

    request_entry = (
        postgres.refresh_task_request_status(request_entry_id) or request_entry
    )
    return TaskRequestCreateResponse(
        request_id=str(getattr(request_entry, "request_id", request_entry_id)),
        status=_status_str(getattr(request_entry, "status", None)),
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
        raise contract_http_exception(400, "INPUT_INVALID", "Invalid request_id")

    postgres = get_postgres_client()
    request_entry = postgres.refresh_task_request_status(request_uuid)
    if request_entry is None:
        raise contract_http_exception(404, "RESOURCE_NOT_FOUND", "Request not found")
    papers = postgres.list_paper_tasks_by_request(request_uuid)
    return TaskRequestStatusResponse(
        request_id=str(request_entry.request_id),
        status=_status_str(request_entry.status),
        papers=[_paper_item_model(item) for item in papers],
    )


@router.get(
    "/requests/{request_id}/source-stats",
    summary="Get aggregated source hit statistics",
    description="Aggregate persisted source_trace data for all paper tasks under the request.",
    response_model=TaskRequestSourceStatsResponse,
    responses={404: {"model": ErrorResponse, "description": "Request not found."}},
)
def get_task_request_source_stats(
    request_id: str = ApiPath(..., description="Request UUIDv4."),
) -> TaskRequestSourceStatsResponse:
    try:
        request_uuid = UUID(request_id)
    except ValueError:
        raise contract_http_exception(400, "INPUT_INVALID", "Invalid request_id")

    postgres = get_postgres_client()
    request_entry = postgres.get_task_request(request_uuid)
    if request_entry is None:
        raise contract_http_exception(404, "RESOURCE_NOT_FOUND", "Request not found")

    papers = postgres.list_paper_tasks_by_request(request_uuid)
    aggregated = _aggregate_source_stats(papers)
    return TaskRequestSourceStatsResponse(
        request_id=str(request_entry.request_id),
        paper_count=aggregated["paper_count"],
        fallback_count=aggregated["fallback_count"],
        providers=aggregated["providers"],
    )


@router.post(
    "/papers/{paper_task_id}/resume",
    response_model=TaskCreateResponse,
    summary="Resume interrupted supervisor workflow",
    responses={
        404: {"description": "Paper task not found"},
        409: {"description": "Paper task already finalized"},
    },
)
def resume_paper_task(
    paper_task_id: str = ApiPath(..., description="Paper task ID"),
) -> TaskCreateResponse:
    try:
        parsed_paper_task_id = UUID(paper_task_id)
    except ValueError:
        raise contract_http_exception(400, "INPUT_INVALID", "Invalid paper_task_id")

    postgres = get_postgres_client()
    paper_task = postgres.get_paper_task(str(parsed_paper_task_id))
    if paper_task is None:
        raise contract_http_exception(404, "RESOURCE_NOT_FOUND", "Paper task not found")

    workflow_status = coerce_workflow_status(
        getattr(paper_task, "workflow_status", None),
        default=WorkflowStatus.pending,
    )
    paper_status = str(getattr(paper_task, "status", "") or "").lower()
    if paper_status == "success" or workflow_status in {
        WorkflowStatus.completed,
        WorkflowStatus.failed,
    }:
        raise contract_http_exception(
            status_code=409,
            error_code="INVALID_STATE",
            detail="Paper task already finalized",
        )

    try:
        resume_task = cast(Any, resume_supervisor_task)
        async_result = resume_task.apply_async(
            args=[str(parsed_paper_task_id)],
        )
    except Exception:
        logger.exception(
            "Failed to enqueue resume task for paper_task_id=%s", paper_task_id
        )
        raise contract_http_exception(
            503, "INTERNAL_ERROR", "Failed to enqueue resume task"
        )

    postgres.update_paper_task(
        str(parsed_paper_task_id),
        celery_task_id=async_result.id,
        status="running",
        workflow_status=WorkflowStatus.pending.value,
    )
    postgres.append_paper_task_log(
        str(parsed_paper_task_id),
        status="running",
        node="resume",
        message="Supervisor resume task queued",
        payload={"celery_task_id": async_result.id},
    )

    request_id = str(getattr(paper_task, "request_id", "") or "")
    if request_id:
        postgres.refresh_task_request_status(request_id)

    return TaskCreateResponse(task_id=async_result.id, status=TaskStatus.pending)


@router.get(
    "/papers/{paper_task_id}",
    summary="Get paper task detail",
    description=(
        "Fetch the stable paper-task read model by paper_task_id.\n"
        "Response body includes workflow detail, warnings, trace chain, duplicate/fulltext flags, and result payload when available."
    ),
    response_model=PaperTaskDetailResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Paper task not found."},
    },
)
def get_paper_task_detail(
    paper_task_id: str = ApiPath(..., description="Paper task UUIDv4"),
) -> PaperTaskDetailResponse:
    try:
        parsed_paper_task_id = UUID(paper_task_id)
    except ValueError:
        raise contract_http_exception(400, "INPUT_INVALID", "Invalid paper_task_id")

    postgres = get_postgres_client()
    paper_entry = postgres.get_paper_task(str(parsed_paper_task_id))
    if paper_entry is None:
        raise contract_http_exception(
            404, "RESOURCE_NOT_FOUND", f"Paper task {paper_task_id} not found"
        )

    processing_steps = normalize_processing_steps(
        getattr(paper_entry, "processing_steps", None),
        node_trace=getattr(paper_entry, "node_trace", None),
    )
    response = PaperTaskDetailResponse(
        paper_task_id=str(getattr(paper_entry, "paper_task_id")),
        request_id=str(getattr(paper_entry, "request_id")),
        document_id=_uuid_optional_str(getattr(paper_entry, "document_id", None)),
        status=_status_str(getattr(paper_entry, "status", None), default="queued"),
        workflow_status=coerce_workflow_status(
            getattr(paper_entry, "workflow_status", None),
            default=WorkflowStatus.pending,
        ),
        processing_steps=processing_steps,
        warning_codes=normalize_warning_codes(getattr(paper_entry, "warning_codes", None)),
        trace_chain=build_trace_chain(
            node_trace=getattr(paper_entry, "node_trace", None),
            processing_steps=processing_steps,
        ),
        fulltext_unavailable=_as_bool_flag(
            getattr(paper_entry, "fulltext_unavailable", None)
        ),
        result_payload=None,
        parsing_metadata=None,
        duplicate_of=_uuid_optional_str(getattr(paper_entry, "duplicate_of", None)),
        error_code=getattr(paper_entry, "error_code", None),
        error_details=(
            getattr(paper_entry, "error_details", None)
            if isinstance(getattr(paper_entry, "error_details", None), dict)
            else None
        ),
        created_at=_as_iso_datetime(getattr(paper_entry, "created_at", None)),
        updated_at=_as_iso_datetime(getattr(paper_entry, "updated_at", None)),
    )

    celery_task_id = getattr(paper_entry, "celery_task_id", None)
    if celery_task_id:
        async_result = AsyncResult(str(celery_task_id), app=celery_app)
        result_payload = getattr(async_result, "result", None)
        if isinstance(result_payload, dict):
            response.result_payload = result_payload
            parsing_metadata = result_payload.get("parsing_metadata")
            if isinstance(parsing_metadata, dict):
                response.parsing_metadata = parsing_metadata

    if response.parsing_metadata is None:
        get_latest_log = getattr(postgres, "get_latest_paper_task_log", None)
        if callable(get_latest_log):
            parsing_log = get_latest_log(str(parsed_paper_task_id), node="parsing")
            parsing_payload = getattr(parsing_log, "payload", None)
            if isinstance(parsing_payload, dict):
                nested_metadata = parsing_payload.get("parsing_metadata")
                if isinstance(nested_metadata, dict):
                    response.parsing_metadata = nested_metadata
                elif any(
                    key in parsing_payload
                    for key in (
                        "parser_backend",
                        "parser_task_id",
                        "mineru_folder",
                        "image_count",
                        "markdown_object_key",
                        "image_object_keys",
                    )
                ):
                    response.parsing_metadata = parsing_payload

    return response


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
        raise contract_http_exception(
            404, "RESOURCE_NOT_FOUND", f"Task {task_id} not found"
        )

    meta = _safe_task_meta(async_result)
    metrics = _extract_task_metrics(meta)
    response = TaskStatusResponse(
        task_id=task_id,
        status=TaskStatus.from_celery(async_result.status),
        workflow_status=None,
        workflow_status_description=None,
        progress_percentage=None,
        processing_steps=None,
        parsing_metadata=None,
        paper_task_id=None,
        document_id=None,
        file_size_bytes=metrics.get("file_size_bytes"),
        processing_duration_seconds=metrics.get("processing_duration_seconds"),
        created_at=metrics.get("created_at"),
        updated_at=metrics.get("updated_at"),
        warning_codes=None,
        trace_chain=None,
        error=None,
        error_details=None,
    )

    postgres = None
    try:
        postgres = get_postgres_client()
        paper_entry = postgres.get_paper_task_by_celery_task_id(task_id)
    except Exception as db_exc:
        logger.warning("Failed to load paper task for {}: {}", task_id, db_exc)
        paper_entry = None

    if paper_entry is not None:
        response.paper_task_id = (
            str(getattr(paper_entry, "paper_task_id", "") or "") or None
        )
        document_id = getattr(paper_entry, "document_id", None)
        if document_id is not None:
            response.document_id = str(document_id)

        db_file_size = getattr(paper_entry, "file_size_bytes", None)
        if db_file_size is not None:
            response.file_size_bytes = db_file_size

        db_duration = getattr(paper_entry, "processing_duration_seconds", None)
        if db_duration is not None:
            response.processing_duration_seconds = db_duration

        response.created_at = response.created_at or _as_iso_datetime(
            getattr(paper_entry, "created_at", None)
        )
        response.updated_at = (
            _as_iso_datetime(getattr(paper_entry, "updated_at", None))
            or response.updated_at
        )

        processing_steps = normalize_processing_steps(
            getattr(paper_entry, "processing_steps", None),
            node_trace=getattr(paper_entry, "node_trace", None),
        )
        response.processing_steps = processing_steps
        response.progress_percentage = calculate_progress_percentage(processing_steps)
        response.warning_codes = normalize_warning_codes(
            getattr(paper_entry, "warning_codes", None)
        )
        response.trace_chain = build_trace_chain(
            node_trace=getattr(paper_entry, "node_trace", None),
            processing_steps=processing_steps,
        )

        workflow_status = coerce_workflow_status(
            getattr(paper_entry, "workflow_status", None),
            default=WorkflowStatus.pending,
        )
        response.workflow_status = workflow_status
        response.workflow_status_description = workflow_status_description(
            workflow_status
        )

        error_code = getattr(paper_entry, "error_code", None)
        error_details = getattr(paper_entry, "error_details", None)
        details_payload: Dict[str, Any] = {}
        if isinstance(error_details, dict):
            details_payload.update(error_details)
        if error_code:
            details_payload.setdefault("error_code", error_code)
        if details_payload:
            response.error_details = details_payload

        if response.parsing_metadata is None and postgres is not None:
            get_latest_log = getattr(postgres, "get_latest_paper_task_log", None)
            if callable(get_latest_log):
                parsing_log = get_latest_log(
                    getattr(paper_entry, "paper_task_id", None), node="parsing"
                )
                parsing_payload = getattr(parsing_log, "payload", None)
                if isinstance(parsing_payload, dict):
                    nested_metadata = parsing_payload.get("parsing_metadata")
                    if isinstance(nested_metadata, dict):
                        response.parsing_metadata = nested_metadata
                    elif any(
                        key in parsing_payload
                        for key in (
                            "parser_backend",
                            "parser_task_id",
                            "mineru_folder",
                            "image_count",
                            "markdown_object_key",
                            "image_object_keys",
                        )
                    ):
                        response.parsing_metadata = parsing_payload

    if async_result.failed():
        response.error = str(async_result.result)
        if response.error_details is None:
            response.error_details = {"message": response.error}
        else:
            response.error_details.setdefault("message", response.error)
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
            response.created_at = response.created_at or result_payload.get(
                "created_at"
            )
            response.updated_at = response.updated_at or result_payload.get(
                "updated_at"
            )
            doc_value = result_payload.get("document_id")
            if doc_value is not None:
                response.document_id = str(doc_value)
            if response.workflow_status is None:
                workflow_value = result_payload.get("workflow_status")
                if workflow_value is not None:
                    workflow_status = coerce_workflow_status(workflow_value)
                    response.workflow_status = workflow_status
                    response.workflow_status_description = workflow_status_description(
                        workflow_status
                    )
            if response.processing_steps is None:
                payload_steps = result_payload.get("processing_steps")
                if payload_steps is not None:
                    response.processing_steps = normalize_processing_steps(
                        payload_steps
                    )
                    response.progress_percentage = calculate_progress_percentage(
                        response.processing_steps
                    )
            progress_percentage = result_payload.get("progress_percentage")
            if response.progress_percentage is None and isinstance(
                progress_percentage, (float, int)
            ):
                response.progress_percentage = float(progress_percentage)
            parsing_metadata = result_payload.get("parsing_metadata")
            if isinstance(parsing_metadata, dict):
                response.parsing_metadata = parsing_metadata
            if response.warning_codes is None:
                response.warning_codes = normalize_warning_codes(
                    result_payload.get("warning_codes")
                )
            if response.trace_chain is None:
                trace_chain = result_payload.get("trace_chain")
                if isinstance(trace_chain, dict):
                    response.trace_chain = trace_chain
        logger.debug("Task succeeded: {}", task_id)
    else:
        logger.debug("Task status: {} status: {}", task_id, async_result.status)

    if response.workflow_status is None:
        if response.status == TaskStatus.success:
            response.workflow_status = WorkflowStatus.completed
        elif response.status == TaskStatus.failure:
            response.workflow_status = WorkflowStatus.failed
        elif response.status in (TaskStatus.started, TaskStatus.retry):
            response.workflow_status = WorkflowStatus.processing_pdf
        else:
            response.workflow_status = WorkflowStatus.pending
        response.workflow_status_description = workflow_status_description(
            response.workflow_status
        )

    if response.processing_steps is not None and response.progress_percentage is None:
        response.progress_percentage = calculate_progress_percentage(
            response.processing_steps
        )

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
    include_result: bool = Query(
        False, description="Include result payloads in list items."
    ),
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
