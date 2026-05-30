"""Pipeline orchestrator API routes."""
from __future__ import annotations

import base64
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import aiofiles
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from src.agents.contracts import (
    PhaseStatus,
    PhaseStatusDetail,
    PipelineGraphState,
    PipelineMode,
    PipelineStatus,
    SourceType,
)

router = APIRouter()


# ── Request/Response models ──────────────────────────────────────────────────


class PipelineRunRequest(BaseModel):
    """Request body for starting a pipeline run."""

    source_type: Literal["local", "online"]
    mode: Literal["full", "phase"] = "full"
    target_phase: int | None = Field(default=None, ge=1, le=3)  # N2: range validation

    # Local upload fields
    filename: str | None = None
    content_base64: str | None = None

    # Online acquisition fields
    query: str | None = None
    identifiers: list[str] | None = None

    @model_validator(mode="after")
    def validate_request(self) -> "PipelineRunRequest":
        """Validate phase mode and source-specific requirements (N1 fix)."""
        # Phase mode requires target_phase
        if self.mode == "phase" and self.target_phase is None:
            raise ValueError("target_phase is required when mode is 'phase'")

        # Source-specific validation
        if self.source_type == "local":
            if not self.content_base64 and not self.filename:
                raise ValueError(
                    "source_type='local' requires content_base64 or filename"
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
async def start_pipeline_run(request: PipelineRunRequest):
    """Start a new pipeline run.

    Returns immediately with processing_run_id. Poll status_url for progress.
    N3 fix: Checks for duplicate in-progress runs before starting.
    """
    runner = get_pipeline_runner()

    # N3: Duplicate run prevention — check if same source is already being processed
    source_key = request.filename or (request.query or "")
    if source_key and runner.is_running_for_source(source_key):
        raise HTTPException(
            status_code=409,
            detail=f"A pipeline run is already in progress for this source: {source_key}",
        )

    processing_run_id = str(uuid.uuid4())
    source_document_id = str(uuid.uuid4())

    # Decode base64 content and write to temp file if provided
    upload_file_path = None
    if request.content_base64:
        content_bytes = base64.b64decode(request.content_base64)
        if request.filename:
            temp_dir = Path("data/pipeline/uploads")
            temp_dir.mkdir(parents=True, exist_ok=True)
            upload_file_path = str(temp_dir / f"{processing_run_id}_{request.filename}")
            async with aiofiles.open(upload_file_path, "wb") as f:
                await f.write(content_bytes)

    initial_state = PipelineGraphState(
        processing_run_id=processing_run_id,
        source_document_id=source_document_id,
        mode=PipelineMode(request.mode),
        source_type=SourceType(request.source_type),
        target_phase=request.target_phase,
        source_key=source_key or None,
        upload_file_path=upload_file_path,
        created_at=datetime.now().isoformat(),
    )

    task = runner.start(initial_state)

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
async def get_pipeline_status(processing_run_id: str):
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
