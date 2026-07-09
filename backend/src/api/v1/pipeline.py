"""Pipeline orchestrator API routes."""

from __future__ import annotations

import base64
import binascii
import uuid
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

import aiofiles
from loguru import logger
from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request

from src.api.auth import get_current_account
from src.api.rate_limit import limiter
from src.api.v1.contracts import (
    PhaseErrorResponse,
    PhaseStatusResponse,
    PhaseSummaryResponse,
    PipelinePhasesResponse,
    PipelineRunListResponse,
    PipelineRunRequest,
    PipelineRunResponse,
    PipelineRunSummaryResponse,
    PipelineStatusResponse,
)
from src.core.config import get_config
from src.core.auth.contracts import AuthContext

from src.agents.contracts import (
    PhaseStatus,
    PhaseStatusDetail,
    PipelineGraphState,
    PipelineMode,
    PipelineStatus,
    SourceType,
)
from src.agents.content_hash import normalize_identifier
from src.dao.postgresql.job_queue import JobQueueRepository

router = APIRouter()


# ── Global pipeline runner (initialized in app lifespan) ─────────────────────

_pipeline_runner = None
_job_queue: JobQueueRepository | None = None


def get_pipeline_runner():
    """Get the global pipeline runner instance."""
    global _pipeline_runner
    if _pipeline_runner is None:
        raise RuntimeError("Pipeline runner not initialized")
    return _pipeline_runner


def set_pipeline_runner(runner):
    """Set the global pipeline runner instance."""
    global _pipeline_runner
    _pipeline_runner = runner


def get_job_queue() -> JobQueueRepository | None:
    """Get the global job queue repository."""
    return _job_queue


def set_job_queue(jq: JobQueueRepository) -> None:
    """Set the global job queue repository."""
    global _job_queue
    _job_queue = jq


# ── Helpers ──────────────────────────────────────────────────────────────────


def _normalize_identifiers(identifiers: list[str]) -> str:
    """Normalize identifiers to a canonical form for dedup.

    Strips whitespace, lowercases, and strips common prefixes like
    'PMID:', 'DOI:', 'PMCID:' to ensure equivalent identifiers
    produce the same key.
    """
    normalized: list[str] = []
    for raw in identifiers:
        normalized.append(normalize_identifier(raw))
    return ",".join(sorted(normalized))


def _build_source_key(body: PipelineRunRequest, content_hash: str | None = None) -> str | None:
    """Build the dedup source key, including extraction target scope when present.

    For online runs with identifiers, identifiers are always the primary key
    (query text varies but the same PMID should deduplicate). Local uploads use
    content hash when available so same filenames do not block different files.
    """
    base_key: str | None = None
    if body.source_type == "local" and content_hash:
        base_key = f"content:{content_hash}"
    elif body.identifiers:
        base_key = _normalize_identifiers(body.identifiers)
    else:
        base_key = body.filename or body.query or None
    if not base_key:
        return None
    if body.extraction_target is None:
        return base_key
    return f"{base_key}|{body.extraction_target.scope_key}"


def _determine_current_phase(state: PipelineGraphState) -> str | None:
    """Determine which phase is currently running."""
    phase_map = {
        "phase_1": state.phase_1_status,
        "phase_2": state.phase_2_status,
        "phase_3": state.phase_3_status,
    }
    for name, detail in phase_map.items():
        if detail.status == PhaseStatus.RUNNING:
            return name
    return None


def _phase_detail_to_response(detail: PhaseStatusDetail) -> PhaseStatusResponse:
    """Convert PhaseStatusDetail to API response model."""
    error_response = None
    if detail.error:
        error_response = PhaseErrorResponse(
            message=detail.error.message,
            retryable=detail.error.retryable,
            attempt=detail.error.attempt,
            max_retries=detail.error.max_retries,
        )

    return PhaseStatusResponse(
        status=detail.status.value,
        started_at=detail.started_at,
        completed_at=detail.completed_at,
        duration_seconds=detail.duration_seconds,
        error=error_response,
        summary=PhaseSummaryResponse.model_validate(detail.summary) if detail.summary else None,
        count=detail.summary.get("count") if detail.summary and isinstance(detail.summary.get("count"), int) else None,
    )


def _compute_elapsed(started_at: str | None, completed_at: str | None) -> float | None:
    """Compute elapsed seconds between two ISO timestamps.

    Returns None if started_at is missing. For running pipelines
    (completed_at is None), computes elapsed against current time.
    """
    if not started_at:
        return None
    try:
        start = datetime.fromisoformat(started_at)
        end = datetime.fromisoformat(completed_at) if completed_at else datetime.now()
        return max(0.0, (end - start).total_seconds())
    except (ValueError, TypeError):
        return None


def _state_title(state: PipelineGraphState) -> str | None:
    """Derive a human-readable title from PipelineGraphState."""
    if state.query:
        return state.query[:120]
    if state.identifiers:
        return ", ".join(state.identifiers[:5])
    if state.source_key:
        return state.source_key[:120]
    if state.upload_file_path:
        return PurePosixPath(state.upload_file_path.replace("\\", "/")).name
    return None


def _prepare_phase_rerun_state(
    existing_state: PipelineGraphState,
    target_phase: int,
) -> PipelineGraphState:
    """Reset target/downstream phase state before re-running a phase."""
    updates: dict[str, Any] = {
        "mode": PipelineMode.PHASE,
        "target_phase": target_phase,
        "pipeline_status": PipelineStatus.PENDING,
        "error_message": None,
        "error_phase": None,
        "completed_at": None,
    }
    for phase_num in range(target_phase, 4):
        updates[f"phase_{phase_num}_status"] = PhaseStatusDetail()
        updates[f"phase_{phase_num}_output"] = None
    if target_phase <= 2:
        updates["skip_phase_3_reason"] = None
    return existing_state.model_copy(deep=True, update=updates)


# ── Routes ───────────────────────────────────────────────────────────────────


@router.post("/run", response_model=PipelineRunResponse, status_code=202)
@limiter.limit("10/minute")
async def start_pipeline_run(
    request: Request,
    body: PipelineRunRequest,
    account: AuthContext = Depends(get_current_account),
):
    """Enqueue a new pipeline run job.

    Returns immediately with processing_run_id and status_url.
    The background dispatcher picks up queued jobs one at a time.
    """
    runner = get_pipeline_runner()
    jq = get_job_queue()
    owner_user_id = str(account.owner_user_id) if account.owner_user_id else None

    # Phase re-run: resume from existing state for target_phase 2/3
    if body.mode == "phase" and body.processing_run_id:
        existing_state = await runner.get_last_state(body.processing_run_id)
        if existing_state is None or existing_state.owner_user_id != owner_user_id:
            raise HTTPException(
                status_code=404,
                detail=f"Pipeline run {body.processing_run_id} not found",
            )
        if existing_state.pipeline_status in (PipelineStatus.PENDING, PipelineStatus.RUNNING):
            raise HTTPException(
                status_code=409,
                detail=f"Pipeline run {body.processing_run_id} is still active",
            )

        request_data: dict[str, Any] = {
            "mode": "phase",
            "source_type": body.source_type,
            "target_phase": body.target_phase,
            "processing_run_id_ref": body.processing_run_id,
            "owner_user_id": owner_user_id,
        }

        if jq is not None:
            job_id = uuid.uuid4()
            await jq.enqueue(
                job_id=job_id,
                processing_run_id=uuid.UUID(existing_state.processing_run_id),
                source_document_id=uuid.UUID(existing_state.source_document_id),
                owner_user_id=account.owner_user_id,
                request_data=request_data,
            )
        else:
            # Fallback: direct start when job queue is not configured
            initial_state = _prepare_phase_rerun_state(existing_state, body.target_phase)
            await runner.start(initial_state)

        return PipelineRunResponse(
            processing_run_id=existing_state.processing_run_id,
            source_document_id=existing_state.source_document_id,
            status="queued" if jq is not None else "accepted",
            status_url=f"/api/v1/pipeline/runs/{existing_state.processing_run_id}/status",
        )

    processing_run_id = str(uuid.uuid4())
    source_document_id = str(uuid.uuid4())

    # Decode base64 content and write to temp file if provided
    upload_file_path = None
    if body.content_base64:
        max_size_bytes = get_config().mineru.max_file_size_mb * 1024 * 1024
        estimated_size = len(body.content_base64) * 3 // 4
        if estimated_size > max_size_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {get_config().mineru.max_file_size_mb}MB",
            )

        try:
            content_bytes = base64.b64decode(body.content_base64, validate=True)
        except binascii.Error as exc:
            raise HTTPException(status_code=422, detail=f"Invalid base64 content: {exc}") from exc
        raw_fname = body.filename or f"{processing_run_id}.bin"
        fname = PurePosixPath(raw_fname.replace("\\", "/")).name
        temp_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "pipeline" / "uploads"
        temp_dir.mkdir(parents=True, exist_ok=True)
        upload_file_path = str(temp_dir / f"{processing_run_id}_{fname}")
        async with aiofiles.open(upload_file_path, "wb") as f:
            await f.write(content_bytes)

    online_action = "download" if body.source_type == "online" else None
    source_key = _build_source_key(body)

    # Build a temporary state for optional content-hash based cache/dedup.
    temp_state = PipelineGraphState(
        processing_run_id=processing_run_id,
        source_document_id=source_document_id,
        owner_user_id=owner_user_id,
        mode=PipelineMode(body.mode),
        source_type=SourceType(body.source_type),
        target_phase=body.target_phase,
        source_key=source_key or None,
        upload_file_path=upload_file_path,
        pre_parsed_markdown=body.pre_parsed_markdown,
        query=body.query,
        identifiers=body.identifiers,
        action=online_action,
        relevance_gate=body.relevance_gate,
        literature_types=body.literature_types,
        created_at=datetime.now().isoformat(),
        extraction_target=body.extraction_target,
        extraction_profile=body.extraction_profile,
        extraction_mode=body.extraction_mode,
        ablation_disable_review=body.ablation_disable_review,
        ablation_disable_target_guard=body.ablation_disable_target_guard,
        ablation_disable_grounding=body.ablation_disable_grounding,
        ablation_original_only=body.ablation_original_only,
        review_reject_policy=body.review_reject_policy,
        extraction_track_mode=body.extraction_track_mode,
    )
    content_hash = None
    hash_required = runner.processing_cache_enabled or runner.duplicate_run_prevention_enabled
    if hash_required:
        content_hash = await runner.compute_initial_content_hash(temp_state)
    if content_hash:
        temp_state.content_hash = content_hash
        temp_state.source_key = _build_source_key(body, content_hash)
        source_key = temp_state.source_key
        cached_state = (
            await runner.check_processing_cache(content_hash, owner_user_id=owner_user_id)
            if runner.processing_cache_enabled
            else None
        )
        if cached_state is not None and cached_state.pipeline_status == PipelineStatus.COMPLETED:
            logger.info(
                "Processing cache hit for content_hash={}, returning cached run={}",
                content_hash[:12],
                cached_state.processing_run_id,
            )
            if upload_file_path:
                Path(upload_file_path).unlink(missing_ok=True)
            return PipelineRunResponse(
                processing_run_id=cached_state.processing_run_id,
                source_document_id=cached_state.source_document_id,
                status="cached",
                status_url=f"/api/v1/pipeline/runs/{cached_state.processing_run_id}/status",
            )

    # N3: Duplicate run prevention
    if (
        runner.duplicate_run_prevention_enabled
        and source_key
        and await runner.is_running_for_source(source_key, owner_user_id=owner_user_id)
    ):
        if upload_file_path:
            Path(upload_file_path).unlink(missing_ok=True)
        raise HTTPException(
            status_code=409,
            detail=f"A pipeline run is already in progress for this source: {source_key}",
        )

    # Build request data for the job queue
    request_data: dict[str, Any] = {
        "mode": body.mode,
        "source_type": body.source_type,
        "target_phase": body.target_phase,
        "owner_user_id": owner_user_id,
        "source_key": source_key,
        "upload_file_path": upload_file_path,
        "pre_parsed_markdown": body.pre_parsed_markdown,
        "query": body.query,
        "identifiers": body.identifiers,
        "action": online_action,
        "relevance_gate": body.relevance_gate,
        "literature_types": body.literature_types,
        "created_at": datetime.now().isoformat(),
        "extraction_mode": body.extraction_mode,
        "ablation_disable_review": body.ablation_disable_review,
        "ablation_disable_target_guard": body.ablation_disable_target_guard,
        "ablation_disable_grounding": body.ablation_disable_grounding,
        "ablation_original_only": body.ablation_original_only,
        "review_reject_policy": body.review_reject_policy,
        "extraction_track_mode": body.extraction_track_mode,
        "extraction_profile": body.extraction_profile,
    }
    if body.extraction_target is not None:
        request_data["extraction_target"] = body.extraction_target.model_dump()

    if jq is not None:
        job_id = uuid.uuid4()
        await jq.enqueue(
            job_id=job_id,
            processing_run_id=uuid.UUID(processing_run_id),
            source_document_id=uuid.UUID(source_document_id),
            owner_user_id=account.owner_user_id,
            request_data=request_data,
        )
    else:
        # Fallback: direct start when job queue is not configured
        from sqlalchemy.exc import IntegrityError

        try:
            await runner.start(temp_state)
        except IntegrityError:
            if upload_file_path:
                Path(upload_file_path).unlink(missing_ok=True)
            raise HTTPException(
                status_code=409,
                detail=f"A pipeline run is already in progress for this source: {source_key}",
            )

    return PipelineRunResponse(
        processing_run_id=processing_run_id,
        source_document_id=source_document_id,
        status="queued" if jq is not None else "accepted",
        status_url=f"/api/v1/pipeline/runs/{processing_run_id}/status",
    )


@router.get("/runs", response_model=PipelineRunListResponse)
async def list_pipeline_runs(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    search: str | None = None,
    account: AuthContext = Depends(get_current_account),
):
    """List all pipeline runs as compact summaries (newest first).

    Args:
        status: Filter by pipeline_status (pending, running, completed, failed).
        search: Case-insensitive substring match on title / identifiers / source_key.
    """
    runner = get_pipeline_runner()
    owner_user_id = str(account.owner_user_id) if account.owner_user_id else None
    rows, total = await runner.list_runs(
        limit=limit,
        offset=offset,
        status=status,
        search=search,
        owner_user_id=owner_user_id,
    )

    items = []
    for row in rows:
        elapsed = _compute_elapsed(row.started_at, row.completed_at)
        items.append(
            PipelineRunSummaryResponse(
                processing_run_id=row.processing_run_id,
                pipeline_status=row.pipeline_status,
                title=row.title,
                started_at=row.started_at,
                completed_at=row.completed_at,
                elapsed_seconds=elapsed,
                current_phase=row.current_phase,
                completed_phases=row.completed_phases,
                total_phases=row.total_phases,
            )
        )

    return PipelineRunListResponse(items=items, total=total)


@router.get("/runs/{processing_run_id}/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    processing_run_id: str,
    account: AuthContext = Depends(get_current_account),
):
    """Get the current status of a pipeline run.

    Checks job queue first (for queued/running jobs), then falls back to
    the in-memory cache and PostgreSQL for pipeline state details.
    """
    runner = get_pipeline_runner()
    jq = get_job_queue()
    owner_user_id = str(account.owner_user_id) if account.owner_user_id else None

    # Check job queue first — a queued job may not have pipeline state yet
    if jq is not None:
        job_status = await jq.get_status(processing_run_id, owner_user_id=account.owner_user_id)
        if job_status == "queued":
            _empty_phases = PipelinePhasesResponse(
                phase_1=PhaseStatusResponse(status="pending"),
                phase_2=PhaseStatusResponse(status="pending"),
                phase_3=PhaseStatusResponse(status="pending"),
            )
            return PipelineStatusResponse(
                processing_run_id=processing_run_id,
                source_document_id="",
                pipeline_status="queued",
                phases=_empty_phases,
            )

    state = await runner.get_last_state(processing_run_id)

    if state is None or state.owner_user_id != owner_user_id:
        raise HTTPException(
            status_code=404,
            detail=f"Pipeline run {processing_run_id} not found",
        )

    phases = PipelinePhasesResponse(
        phase_1=_phase_detail_to_response(state.phase_1_status),
        phase_2=_phase_detail_to_response(state.phase_2_status),
        phase_3=_phase_detail_to_response(state.phase_3_status),
    )

    elapsed = _compute_elapsed(state.started_at, state.completed_at)
    title = _state_title(state)

    return PipelineStatusResponse(
        processing_run_id=state.processing_run_id,
        source_document_id=state.source_document_id,
        pipeline_status=state.pipeline_status.value,
        current_phase=_determine_current_phase(state),
        skip_phase_3_reason=state.skip_phase_3_reason.value if state.skip_phase_3_reason else None,
        phases=phases,
        error_message=state.error_message,
        error_phase=state.error_phase,
        started_at=state.started_at,
        completed_at=state.completed_at,
        elapsed_seconds=elapsed,
        title=title,
    )
