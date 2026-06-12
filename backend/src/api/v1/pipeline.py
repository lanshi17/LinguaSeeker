"""Pipeline orchestrator API routes."""
from __future__ import annotations

import base64
import binascii
import uuid
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Literal

import aiofiles
from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request
from pydantic import BaseModel, Field, model_validator

from src.api.auth import require_api_key
from src.api.rate_limit import limiter
from src.core.config import get_config

from src.agents.contracts import (
    PhaseStatus,
    PhaseStatusDetail,
    PipelineGraphState,
    PipelineMode,
    PipelineStatus,
    SourceType,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ExtractionTarget,
)

router = APIRouter()


# ── Request/Response models ──────────────────────────────────────────────────


class PipelineRunRequest(BaseModel):
    """Request body for starting a pipeline run."""

    source_type: Literal["local", "online"]
    mode: Literal["full", "phase"] = "full"
    target_phase: int | None = Field(default=None, ge=1, le=3)  # N2: range validation
    processing_run_id: str | None = None  # For phase mode re-run from existing state

    # Local upload fields
    filename: str | None = None
    content_base64: str | None = None

    # Pre-parsed markdown: bypasses Phase 1 MinerU parsing entirely.
    # When provided, Phase 1 constructs metadata directly from this text.
    pre_parsed_markdown: str | None = None

    # Online acquisition fields
    query: str | None = None
    identifiers: list[str] | None = None

    # Target gene-disease hypothesis (Phase 2/3 evidence extraction)
    extraction_target: ExtractionTarget | None = Field(default=None, alias="target")

    @model_validator(mode="after")
    def validate_request(self) -> "PipelineRunRequest":
        """Validate phase mode and source-specific requirements (N1 fix)."""
        # Phase mode requires target_phase
        if self.mode == "phase" and self.target_phase is None:
            raise ValueError("target_phase is required when mode is 'phase'")

        # Phase mode with target > 1 requires processing_run_id
        if self.mode == "phase" and self.target_phase is not None and self.target_phase > 1:
            if not self.processing_run_id:
                raise ValueError(
                    "processing_run_id is required when mode='phase' and target_phase > 1"
                )

        # Source-specific validation (skip for phase re-run)
        if not (self.mode == "phase" and self.processing_run_id):
            if self.source_type == "local":
                if not self.content_base64 and not self.pre_parsed_markdown:
                    raise ValueError(
                        "source_type='local' requires content_base64 or pre_parsed_markdown"
                    )
            elif self.source_type == "online":
                if not self.query and not self.identifiers:
                    raise ValueError(
                        "source_type='online' requires query or identifiers"
                    )

        return self


class PhaseStatusResponse(BaseModel):
    """Per-phase status detail for API response."""

    status: str
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    error: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None


class PipelineRunResponse(BaseModel):
    """Response from starting a pipeline run."""

    processing_run_id: str
    source_document_id: str
    status: str
    status_url: str


class PipelineStatusResponse(BaseModel):
    """Response for pipeline status query with per-phase details."""

    processing_run_id: str
    source_document_id: str
    pipeline_status: str
    current_phase: str | None = None
    skip_phase_3_reason: str | None = None
    phases: dict[str, PhaseStatusResponse]
    error_message: str | None = None
    error_phase: int | None = None
    started_at: str | None = None
    completed_at: str | None = None


# ── Global pipeline runner (initialized in app lifespan) ─────────────────────

_pipeline_runner = None


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


# ── Helpers ──────────────────────────────────────────────────────────────────


def _build_source_key(body: PipelineRunRequest) -> str | None:
    """Build the dedup source key, including extraction target scope when present.

    Appending the target scope makes duplicate-run detection target-aware:
    the same filename submitted with different targets is treated as a
    distinct run (no 409 conflict). The same document extracted for
    different hypotheses should produce separate runs.
    """
    base_key = body.filename or (body.query or "")
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
    error_dict = None
    if detail.error:
        error_dict = {
            "message": detail.error.message,
            "retryable": detail.error.retryable,
            "attempt": detail.error.attempt,
            "max_retries": detail.error.max_retries,
        }

    return PhaseStatusResponse(
        status=detail.status.value,
        started_at=detail.started_at,
        completed_at=detail.completed_at,
        duration_seconds=detail.duration_seconds,
        error=error_dict,
        summary=detail.summary,
    )


# ── Routes ───────────────────────────────────────────────────────────────────


@router.post("/run", response_model=PipelineRunResponse, status_code=202)
@limiter.limit("10/minute")
async def start_pipeline_run(request: Request, body: PipelineRunRequest, _api_key: str | None = Depends(require_api_key)):
    """Start a new pipeline run.

    Returns immediately with processing_run_id. Poll status_url for progress.
    N3 fix: Checks for duplicate in-progress runs before starting.
    """
    runner = get_pipeline_runner()

    # Phase re-run: resume from existing state for target_phase 2/3
    if body.mode == "phase" and body.processing_run_id:
        existing_state = await runner.get_last_state(body.processing_run_id)
        if existing_state is None:
            raise HTTPException(
                status_code=404,
                detail=f"Pipeline run {body.processing_run_id} not found",
            )
        initial_state = existing_state.model_copy(
            deep=True,
            update={
                "mode": PipelineMode.PHASE,
                "target_phase": body.target_phase,
                "pipeline_status": PipelineStatus.PENDING,
                "error_message": None,
                "error_phase": None,
                "completed_at": None,
            },
        )
        from sqlalchemy.exc import IntegrityError

        try:
            task = await runner.start(initial_state)
        except IntegrityError:
            raise HTTPException(
                status_code=409,
                detail="A pipeline run is already in progress for this source",
            )

        return PipelineRunResponse(
            processing_run_id=existing_state.processing_run_id,
            source_document_id=existing_state.source_document_id,
            status="accepted",
            status_url=f"/api/v1/pipeline/runs/{existing_state.processing_run_id}/status",
        )

    # N3: Duplicate run prevention — check if same source is already being processed
    source_key = _build_source_key(body)
    if source_key and await runner.is_running_for_source(source_key):
        raise HTTPException(
            status_code=409,
            detail=f"A pipeline run is already in progress for this source: {source_key}",
        )

    processing_run_id = str(uuid.uuid4())
    source_document_id = str(uuid.uuid4())

    # Decode base64 content and write to temp file if provided
    upload_file_path = None
    if body.content_base64:
        # Enforce file size limit
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
        # Sanitize filename: strip directory components to prevent path traversal
        # Normalize backslashes (Windows) before PurePosixPath extraction
        raw_fname = body.filename or f"{processing_run_id}.bin"
        fname = PurePosixPath(raw_fname.replace("\\", "/")).name
        temp_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "pipeline" / "uploads"
        temp_dir.mkdir(parents=True, exist_ok=True)
        upload_file_path = str(temp_dir / f"{processing_run_id}_{fname}")
        async with aiofiles.open(upload_file_path, "wb") as f:
            await f.write(content_bytes)

    # Determine online acquisition action
    online_action = None
    if body.source_type == "online":
        if body.identifiers:
            online_action = "fetch"
        else:
            online_action = "search"

    initial_state = PipelineGraphState(
        processing_run_id=processing_run_id,
        source_document_id=source_document_id,
        mode=PipelineMode(body.mode),
        source_type=SourceType(body.source_type),
        target_phase=body.target_phase,
        source_key=source_key or None,
        upload_file_path=upload_file_path,
        pre_parsed_markdown=body.pre_parsed_markdown,
        query=body.query,
        identifiers=body.identifiers,
        action=online_action,
        created_at=datetime.now().isoformat(),
        extraction_target=body.extraction_target,
    )

    from sqlalchemy.exc import IntegrityError

    try:
        task = await runner.start(initial_state)
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail=f"A pipeline run is already in progress for this source: {source_key}",
        )

    # Clean up temp file after pipeline completes (success or failure)
    if upload_file_path:
        def _cleanup_temp_file(t: object) -> None:
            try:
                Path(upload_file_path).unlink(missing_ok=True)
            except OSError:
                pass

        task.add_done_callback(_cleanup_temp_file)

    return PipelineRunResponse(
        processing_run_id=processing_run_id,
        source_document_id=source_document_id,
        status="accepted",
        status_url=f"/api/v1/pipeline/runs/{processing_run_id}/status",
    )


@router.get("/runs/{processing_run_id}/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(processing_run_id: str, _api_key: str | None = Depends(require_api_key)):
    """Get the current status of a pipeline run.

    Checks in-memory cache first, then falls back to PostgreSQL.
    """
    runner = get_pipeline_runner()

    state = await runner.get_last_state(processing_run_id)

    if state is None:
        raise HTTPException(
            status_code=404,
            detail=f"Pipeline run {processing_run_id} not found",
        )

    phases = {
        "phase_1": _phase_detail_to_response(state.phase_1_status),
        "phase_2": _phase_detail_to_response(state.phase_2_status),
        "phase_3": _phase_detail_to_response(state.phase_3_status),
    }

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
    )


class PipelineFinalizeResponse(BaseModel):
    """Response from finalizing a pipeline run."""

    processing_run_id: str
    pipeline_status: str
    completed_at: str


@router.post("/runs/{processing_run_id}/finalize", response_model=PipelineFinalizeResponse)
async def finalize_pipeline_run(processing_run_id: str, _api_key: str | None = Depends(require_api_key)):
    """Finalize a pipeline run that is awaiting review.

    Transitions from AWAITING_REVIEW to COMPLETED. Idempotent for already-completed runs.
    """
    runner = get_pipeline_runner()
    state = await runner.get_last_state(processing_run_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=f"Pipeline run {processing_run_id} not found",
        )

    # Idempotent: already completed
    if state.pipeline_status == PipelineStatus.COMPLETED:
        return PipelineFinalizeResponse(
            processing_run_id=state.processing_run_id,
            pipeline_status=state.pipeline_status.value,
            completed_at=state.completed_at or "",
        )

    if state.pipeline_status != PipelineStatus.AWAITING_REVIEW:
        raise HTTPException(
            status_code=409,
            detail="Only awaiting_review runs can be finalized",
        )

    finalized = await runner.finalize_review(processing_run_id)
    if finalized is None:
        raise HTTPException(
            status_code=404,
            detail=f"Pipeline run {processing_run_id} not found",
        )

    return PipelineFinalizeResponse(
        processing_run_id=finalized.processing_run_id,
        pipeline_status=finalized.pipeline_status.value,
        completed_at=finalized.completed_at or "",
    )
