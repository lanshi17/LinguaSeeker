"""Pydantic request/response models for pipeline and phase API routes."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ExtractionTarget,
)


class PipelineRunRequest(BaseModel):
    """Request body for starting a pipeline run."""

    source_type: Literal["local", "online"]
    mode: Literal["full", "phase"] = "full"
    target_phase: int | None = Field(default=None, ge=1, le=3)
    processing_run_id: str | None = None

    # Local upload fields
    filename: str | None = None
    content_base64: str | None = None

    # Pre-parsed markdown: bypasses Phase 1 MinerU parsing entirely.
    pre_parsed_markdown: str | None = None

    # Online acquisition fields
    query: str | None = None
    identifiers: list[str] | None = None
    relevance_gate: bool = True
    literature_types: list[str] | None = None

    # Target gene-disease hypothesis (Phase 2/3 evidence extraction)
    extraction_target: ExtractionTarget | None = Field(default=None, alias="target")

    # Extraction field profile — controls which catalog fields are sent to the
    # LLM.  ``"none"`` (default) extracts all non-curation fields.
    extraction_profile: str = "none"

    # Extraction workflow mode: "broad" (default) or "catalog" (rollback baseline).
    extraction_mode: str = "broad"

    # Ablation switches for benchmarking experiments.
    ablation_disable_review: bool = False
    ablation_disable_target_guard: bool = False
    ablation_disable_grounding: bool = False
    ablation_original_only: bool = False
    review_reject_policy: Literal["hard_veto", "soft_veto", "tristate_review"] = "tristate_review"
    extraction_track_mode: Literal["dual", "original_only", "english_pivot"] = "dual"

    @model_validator(mode="after")
    def validate_request(self) -> PipelineRunRequest:
        """Validate phase mode and source-specific requirements."""
        if self.mode == "phase" and self.target_phase is None:
            raise ValueError("target_phase is required when mode is 'phase'")

        if self.mode == "phase" and self.target_phase is not None and self.target_phase > 1:
            if not self.processing_run_id:
                raise ValueError("processing_run_id is required when mode='phase' and target_phase > 1")

        # Source-specific validation (skip for phase re-run)
        if not (self.mode == "phase" and self.processing_run_id):
            if self.source_type == "local":
                if not self.content_base64 and not self.pre_parsed_markdown:
                    raise ValueError("source_type='local' requires content_base64 or pre_parsed_markdown")
            elif self.source_type == "online":
                if not self.query and not self.identifiers:
                    raise ValueError("source_type='online' requires query or identifiers")

        return self


class PhaseErrorResponse(BaseModel):
    """Structured phase error returned by pipeline status API."""

    message: str
    retryable: bool
    attempt: int
    max_retries: int


class PhaseSummaryResponse(BaseModel):
    """Flexible phase summary payload with a named API type."""

    model_config = ConfigDict(extra="allow")


class PhaseNodeMetricsResponse(BaseModel):
    """Flexible per-node metrics payload with a named API type."""

    model_config = ConfigDict(extra="allow")


class PhaseNodeResponse(BaseModel):
    """Fine-grained phase sub-node status for UI progress rendering."""

    node_id: str
    label: str
    status: str
    progress: float | None = None
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    count: int | None = None
    metrics: PhaseNodeMetricsResponse | None = None
    error: PhaseErrorResponse | str | None = None


class PhaseStatusResponse(BaseModel):
    """Per-phase status detail for API response."""

    status: str
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    error: PhaseErrorResponse | None = None
    summary: PhaseSummaryResponse | None = None
    nodes: list[PhaseNodeResponse] = Field(default_factory=list)
    count: int | None = None


class PipelinePhasesResponse(BaseModel):
    """Pipeline phases keyed by stable phase id."""

    phase_1: PhaseStatusResponse
    phase_2: PhaseStatusResponse
    phase_3: PhaseStatusResponse


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
    phases: PipelinePhasesResponse
    error_message: str | None = None
    error_phase: int | None = None
    started_at: str | None = None
    completed_at: str | None = None
    elapsed_seconds: float | None = None
    title: str | None = None


class PipelineRunSummaryResponse(BaseModel):
    """Compact summary for pipeline run list views."""

    processing_run_id: str
    pipeline_status: str
    title: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    elapsed_seconds: float | None = None
    current_phase: str | None = None
    completed_phases: int = 0
    total_phases: int = 3


class PipelineRunListResponse(BaseModel):
    """Paginated list of pipeline run summaries."""

    items: list[PipelineRunSummaryResponse]
    total: int


class LoginRequest(BaseModel):
    """Login request body.

    ``email`` is optional to preserve the legacy password-only API-key login.
    New personal accounts must submit both email and password.
    """

    email: str | None = None
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, email: str | None) -> str | None:
        """Normalize an email address for local account lookup."""
        if email is None:
            return None
        normalized = email.strip().lower()
        if not normalized:
            return None
        if "@" not in normalized or "." not in normalized.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address")
        return normalized


class RegisterRequest(BaseModel):
    """Register request body for local email accounts."""

    email: str
    password: str = Field(min_length=8)
    display_name: str | None = Field(default=None, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, email: str) -> str:
        """Normalize and validate an email address."""
        normalized = email.strip().lower()
        if "@" not in normalized or "." not in normalized.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address")
        return normalized

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, display_name: str | None) -> str | None:
        """Trim optional display names."""
        if display_name is None:
            return None
        stripped = display_name.strip()
        return stripped or None


class LogoutResponse(BaseModel):
    """Logout success response."""

    success: bool


class AuthMeResponse(BaseModel):
    """Current authentication status."""

    authenticated: bool
    account_type: Literal["public", "user"]
    user_id: UUID | None = None
    email: str | None = None
    display_name: str | None = None


class AuthResponse(BaseModel):
    """Login/register success response."""

    success: bool
    account: AuthMeResponse
