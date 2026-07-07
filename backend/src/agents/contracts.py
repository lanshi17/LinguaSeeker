"""Contracts for pipeline orchestrator state, types, and error hierarchy."""

from __future__ import annotations

import functools
from datetime import datetime

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


class InvalidStateTransitionError(Exception):
    """Raised when an invalid pipeline or phase status transition is attempted.

    This is a programming / data-corruption guard: it should never be raised
    in normal operation. If it is, either the orchestrator logic is broken or
    the database state has been corrupted.
    """

    def __init__(self, from_status: str, to_status: str, context: str = ""):
        msg = f"Invalid state transition: {from_status} -> {to_status}"
        if context:
            msg += f" ({context})"
        super().__init__(msg)
        self.from_status = from_status
        self.to_status = to_status
        self.context = context


# ── State transition guards ──────────────────────────────────────────────────

# Valid transitions for PipelineStatus.
# Phase reruns allow any terminal state to return to PENDING.
_VALID_PIPELINE_TRANSITIONS: dict[PipelineStatus, frozenset[PipelineStatus]] = {
    PipelineStatus.PENDING: frozenset(
        {
            PipelineStatus.RUNNING,
            PipelineStatus.FAILED,
        }
    ),
    PipelineStatus.RUNNING: frozenset(
        {
            PipelineStatus.COMPLETED,
            PipelineStatus.FAILED,
        }
    ),
    PipelineStatus.FAILED: frozenset(
        {
            PipelineStatus.PENDING,  # phase rerun / retry
        }
    ),
    PipelineStatus.COMPLETED: frozenset(
        {
            PipelineStatus.PENDING,  # phase rerun (unusual but allowed)
        }
    ),
}

# Valid transitions for PhaseStatus.
# Phase reruns allow terminal states to return to PENDING.
_VALID_PHASE_TRANSITIONS: dict[PhaseStatus, frozenset[PhaseStatus]] = {
    PhaseStatus.PENDING: frozenset(
        {
            PhaseStatus.RUNNING,
            PhaseStatus.SKIPPED,
            PhaseStatus.FAILED,
        }
    ),
    PhaseStatus.RUNNING: frozenset(
        {
            PhaseStatus.COMPLETED,
            PhaseStatus.FAILED,
            PhaseStatus.SKIPPED,
        }
    ),
    PhaseStatus.COMPLETED: frozenset(
        {
            PhaseStatus.PENDING,  # phase rerun
        }
    ),
    PhaseStatus.SKIPPED: frozenset(
        {
            PhaseStatus.PENDING,  # phase rerun
        }
    ),
    PhaseStatus.FAILED: frozenset(
        {
            PhaseStatus.PENDING,  # phase rerun / retry
        }
    ),
}


def validate_pipeline_status_transition(
    from_status: PipelineStatus,
    to_status: PipelineStatus,
    *,
    context: str = "",
) -> None:
    """Validate that a pipeline status transition is allowed.

    Raises InvalidStateTransitionError if the transition is not in the
    valid transition table. No-op (identity transition) is always allowed
    so that saves which only update metadata (not status) pass through.

    Args:
        from_status: Current pipeline status.
        to_status: Target pipeline status.
        context: Optional context string for error messages (e.g. run_id).

    Raises:
        InvalidStateTransitionError: If the transition is invalid.
    """
    if from_status == to_status:
        return
    allowed = _VALID_PIPELINE_TRANSITIONS.get(from_status, frozenset())
    if to_status not in allowed:
        raise InvalidStateTransitionError(
            from_status=from_status.value,
            to_status=to_status.value,
            context=context,
        )


def validate_phase_status_transition(
    from_status: PhaseStatus,
    to_status: PhaseStatus,
    *,
    context: str = "",
) -> None:
    """Validate that a per-phase status transition is allowed.

    Identity transition is always allowed (metadata-only saves).

    Args:
        from_status: Current phase status.
        to_status: Target phase status.
        context: Optional context string for error messages (e.g. "phase_1").

    Raises:
        InvalidStateTransitionError: If the transition is invalid.
    """
    if from_status == to_status:
        return
    allowed = _VALID_PHASE_TRANSITIONS.get(from_status, frozenset())
    if to_status not in allowed:
        raise InvalidStateTransitionError(
            from_status=from_status.value,
            to_status=to_status.value,
            context=context,
        )


def validate_all_phase_transitions(
    old_state: "PipelineGraphState",
    new_state: "PipelineGraphState",
    *,
    context: str = "",
) -> None:
    """Validate all per-phase status transitions between two states.

    Checks all three phases and raises on the first invalid transition.

    Args:
        old_state: Previous pipeline state.
        new_state: New pipeline state being saved.
        context: Optional context for error messages.

    Raises:
        InvalidStateTransitionError: If any phase has an invalid transition.
    """
    for phase_num in (1, 2, 3):
        old_detail = getattr(old_state, f"phase_{phase_num}_status")
        new_detail = getattr(new_state, f"phase_{phase_num}_status")
        if old_detail.status != new_detail.status:
            ctx = f"phase_{phase_num}"
            if context:
                ctx = f"{context}, phase {phase_num}"
            validate_phase_status_transition(
                old_detail.status,
                new_detail.status,
                context=ctx,
            )


@functools.lru_cache(maxsize=1)
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


# Shared across all phase adapters: permanent OS errors that must NOT be retried.
PERMANENT_OS_ERRORS: tuple[type, ...] = (FileNotFoundError, PermissionError, IsADirectoryError)


def classify_phase_error(
    phase_num: int,
    error: Exception,
    retryable_errors: tuple[type, ...],
) -> None:
    """Classify and re-raise an error as RetryablePhaseError or PermanentPhaseError.

    Call this in a phase adapter's ``except Exception`` block to convert
    unclassified errors into the correct PhaseError subclass.  Already-
    classified PhaseErrors pass through unchanged.

    Raises:
        RetryablePhaseError: If *error* matches a retryable type.
        PermanentPhaseError: If *error* is a permanent OS error or unknown.
        PhaseError: If *error* is already a RetryablePhaseError or PermanentPhaseError.
    """
    if isinstance(error, (PermanentPhaseError, RetryablePhaseError)):
        raise error
    if isinstance(error, PERMANENT_OS_ERRORS):
        raise PermanentPhaseError(
            f"Phase {phase_num} permanent file error: {error}",
            phase=phase_num,
        ) from error
    if isinstance(error, retryable_errors):
        raise RetryablePhaseError(
            f"Phase {phase_num} transient error: {error}",
            phase=phase_num,
        ) from error
    raise PermanentPhaseError(
        f"Phase {phase_num} unexpected error: {error}",
        phase=phase_num,
    ) from error


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
    original_text: str | None = None  # Persisted document text (avoid re-reading from disk)
    translated_text: str | None = None  # Persisted translated text
    original_blocks: list[dict] | None = None  # Structured ContentBlock dicts for rendering
    translated_blocks: list[dict] | None = None


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

    @classmethod
    def complete(
        cls,
        started_at: str | None,
        summary: dict[str, Any] | None = None,
    ) -> PhaseStatusDetail:
        """Build a COMPLETED status detail, computing duration from started_at."""
        now = datetime.now().isoformat()
        duration = (datetime.now() - datetime.fromisoformat(started_at)).total_seconds() if started_at else None
        return cls(
            status=PhaseStatus.COMPLETED,
            started_at=started_at,
            completed_at=now,
            duration_seconds=duration,
            summary=summary,
        )


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
    # Content hash for L1/L2 processing cache (deduplication of identical docs)
    content_hash: str | None = None

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
    # Optional online-acquisition gate controls
    relevance_gate: bool = True
    literature_types: list[str] | None = None

    # Target gene-disease hypothesis for evidence extraction (Phase 2/3)
    extraction_target: ExtractionTarget | None = None

    # Extraction field profile name (passed through to EvidenceExtractionService).
    # ``"none"`` = all non-curation fields (production default).
    # ``"dataset_d_publication"`` = 20-field BIBM evaluation profile.
    extraction_profile: str = "none"

    # Extraction workflow mode (passed through to EvidenceExtractionWorkflow).
    # ``"broad"`` = business default (primary_broad_extraction -> review_validation two-pass).
    # ``"catalog"`` = rollback / historical baseline (catalog_extraction -> special_evidence -> ...).
    extraction_mode: str = "broad"

    # Ablation switches for BIBM N=50 comparison experiment.
    # When True, the corresponding workflow node is skipped.
    # See docs/active/2026-06-29-bibm-n50-comparison-ablation-design.md.
    ablation_disable_review: bool = False
    ablation_disable_target_guard: bool = False
    ablation_disable_grounding: bool = False
    ablation_original_only: bool = False
    review_reject_policy: str = "tristate_review"
    extraction_track_mode: str = "dual"

    @classmethod
    def from_request_data(cls, rd: dict[str, Any]) -> PipelineGraphState:
        """Build initial state from a dispatcher job's request_data dict.

        Centralizes the field mapping so callers don't repeat 20+ lines.
        """
        return cls(
            processing_run_id=rd["processing_run_id"],
            source_document_id=rd["source_document_id"],
            mode=PipelineMode(rd.get("mode", "full")),
            source_type=SourceType(rd.get("source_type", "local")),
            target_phase=rd.get("target_phase"),
            source_key=rd.get("source_key"),
            upload_file_path=rd.get("upload_file_path"),
            pre_parsed_markdown=rd.get("pre_parsed_markdown"),
            query=rd.get("query"),
            identifiers=rd.get("identifiers"),
            action=rd.get("action"),
            relevance_gate=rd.get("relevance_gate", True),
            literature_types=rd.get("literature_types"),
            created_at=rd.get("created_at", ""),
            extraction_target=(ExtractionTarget(**rd["extraction_target"]) if rd.get("extraction_target") else None),
            extraction_profile=rd.get("extraction_profile", "none"),
            extraction_mode=rd.get("extraction_mode", "broad"),
            ablation_disable_review=rd.get("ablation_disable_review", False),
            ablation_disable_target_guard=rd.get("ablation_disable_target_guard", False),
            ablation_disable_grounding=rd.get("ablation_disable_grounding", False),
            ablation_original_only=rd.get("ablation_original_only", False),
            review_reject_policy=rd.get("review_reject_policy", "tristate_review"),
            extraction_track_mode=rd.get("extraction_track_mode", "dual"),
        )
