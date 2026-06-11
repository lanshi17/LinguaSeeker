"""Contracts for pipeline orchestrator state, types, and error hierarchy."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ExtractionTarget,
)

# ── Enums ────────────────────────────────────────────────────────────────────


class PhaseStatus(str, Enum):
    """Phase execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class PipelineMode(str, Enum):
    """Pipeline execution mode."""

    FULL = "full"  # Run all phases
    PHASE = "phase"  # Run specific phase only


class SourceType(str, Enum):
    """Document source type."""

    LOCAL = "local"
    ONLINE = "online"


class PipelineStatus(str, Enum):
    """Overall pipeline lifecycle status."""

    PENDING = "pending"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"


class SkipPhase3Reason(str, Enum):
    """Reason for skipping Phase 3 (entity standardization)."""

    NOT_RELEVANT = "not_relevant"  # Both tracks returned NOT_RELEVANT
    NO_ENTITIES = "no_entities"  # Evidence exists but no extractable entities
    NO_CANDIDATES = "no_candidates"  # Standardization produced zero candidates


# ── Error hierarchy ──────────────────────────────────────────────────────────


class PhaseError(Exception):
    """Base exception for phase execution errors."""

    def __init__(self, message: str, phase: int):
        super().__init__(message)
        self.phase = phase


class RetryablePhaseError(PhaseError):
    """Transient error that should be retried.

    Examples: openai.APITimeoutError, httpx.TimeoutException,
    MinerUTimeoutError, openai.RateLimitError.
    """

    def __init__(self, message: str, phase: int, attempt: int = 0):
        super().__init__(message, phase)
        self.attempt = attempt


class PermanentPhaseError(PhaseError):
    """Permanent error that should NOT be retried.

    Examples: ParserExhaustedError, configuration errors, invalid input.
    """

    pass


def build_retryable_errors() -> tuple[type, ...]:
    """Build the shared tuple of retryable error types.

    Includes base transient errors plus optional project-specific ones
    (httpx, openai, MinerU) that may not be installed.
    """
    errors: tuple[type, ...] = (ConnectionError, TimeoutError, OSError)

    try:
        import httpx

        errors += (httpx.TimeoutException,)
    except ImportError:
        pass

    try:
        import openai

        errors += (openai.APITimeoutError, openai.RateLimitError)
    except ImportError:
        pass

    try:
        from src.core.ingest_and_digitize_data.parse_document.exceptions import (
            MinerUTimeoutError,
        )

        errors += (MinerUTimeoutError,)
    except ImportError:
        pass

    return errors


# ── Phase output models (typed, not bare dict) ─────────────────────────────


class Phase1Output(BaseModel):
    """Typed output from Phase 1: acquisition + parsing."""

    pdf_path: str
    md_path: str
    metadata_path: str
    output_dir: str
    images_dir: str | None = None


class Phase2Output(BaseModel):
    """Typed output from Phase 2: translation + evidence extraction."""

    output_dir: str
    original_json_path: str
    translated_json_path: str
    source_language: str
    extraction_result_path: str  # Path to DualEvidenceExtractionResult JSON


class Phase3Output(BaseModel):
    """Typed output from Phase 3: entity standardization."""

    match_count: int
    standardized_count: int
    ambiguous_count: int
    unmapped_count: int


# ── Phase status detail (per-phase timing and errors) ─────────────────────


class PhaseErrorDetail(BaseModel):
    """Structured error details for a phase."""

    message: str
    retryable: bool
    attempt: int
    max_retries: int


class PhaseStatusDetail(BaseModel):
    """Per-phase status with timing and error information."""

    status: PhaseStatus = PhaseStatus.PENDING
    started_at: str | None = None  # ISO timestamp
    completed_at: str | None = None  # ISO timestamp
    duration_seconds: float | None = None
    error: PhaseErrorDetail | None = None
    summary: dict[str, Any] | None = None


# ── Pipeline graph state (orchestration metadata only) ───────────────────────


class PipelineGraphState(BaseModel):
    """Orchestration metadata for pipeline execution.

    This is the LangGraph state shared across all phase adapter nodes.
    Phase-specific working states (translation result, evidence items, etc.)
    are NOT nested here — they remain in-memory within each adapter.

    Persisted to PostgreSQL after each phase completes for crash recovery.

    Note on UUIDs: processing_run_id and source_document_id are stored as
    UUID strings (e.g., "550e8400-e29b-41d4-a716-446655440000"). The DB
    model uses UUID(as_uuid=True) and JSON serialization preserves the
    string format for round-trip compatibility.
    """

    # Run identity (UUID strings)
    processing_run_id: str
    source_document_id: str

    # Execution mode
    mode: PipelineMode
    source_type: SourceType
    target_phase: int | None = None  # Only used when mode=PHASE

    # Dedup key for duplicate-run prevention (N3 fix)
    source_key: str | None = None  # filename for local, query for online

    # Overall pipeline status
    pipeline_status: PipelineStatus = PipelineStatus.PENDING

    # Per-phase status (structured, not flat strings)
    phase_1_status: PhaseStatusDetail = Field(default_factory=PhaseStatusDetail)
    phase_2_status: PhaseStatusDetail = Field(default_factory=PhaseStatusDetail)
    phase_3_status: PhaseStatusDetail = Field(default_factory=PhaseStatusDetail)

    # Phase outputs (typed models, not bare dicts)
    phase_1_output: Phase1Output | None = None
    phase_2_output: Phase2Output | None = None
    phase_3_output: Phase3Output | None = None

    # Error tracking
    error_message: str | None = None
    error_phase: int | None = None

    # Execution metadata
    created_at: str = ""  # ISO timestamp
    started_at: str | None = None
    completed_at: str | None = None

    # Content-based routing flags
    skip_phase_3_reason: SkipPhase3Reason | None = None

    # Upload content (base64 decoded to temp file)
    upload_file_path: str | None = None

    # Pre-parsed markdown (bypasses Phase 1 MinerU parsing)
    pre_parsed_markdown: str | None = None

    # Online acquisition fields (passed through to Phase1Adapter)
    query: str | None = None
    identifiers: list[str] | None = None
    action: str | None = None

    # Target gene-disease hypothesis for evidence extraction (Phase 2/3)
    extraction_target: ExtractionTarget | None = None
