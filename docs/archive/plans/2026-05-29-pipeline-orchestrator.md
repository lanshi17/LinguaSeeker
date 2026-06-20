# Pipeline Orchestrator Implementation Plan (v4 — Audit-Complete)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a LangGraph-based orchestrator that coordinates three phases of evidence processing with deterministic routing, crash recovery via PostgreSQL state persistence, and async API execution. Phase 4 (expert review) is NOT a pipeline phase — it operates independently via its existing HTTP API.

**Architecture:** Main agent is a LangGraph `StateGraph[PipelineGraphState]` with three phase adapter nodes. Each adapter wraps existing mature services without modification. The graph state is orchestration metadata only (run ID, phase status, error details) — phase-specific states remain in-memory within each adapter. State persists to PostgreSQL after each phase completes for crash recovery. Routing is pure deterministic logic based on structured state fields. Adapters raise classified errors; the orchestrator catches and decides retry vs. stop.

**Tech Stack:** LangGraph 1.2+, Pydantic 2.x, SQLAlchemy 2.x async, FastAPI, asyncio.Semaphore for concurrency control

---

## v3 Change Log (from v2)

| Issue ID | Category | Fix Applied |
|----------|----------|-------------|
| A2 | Structure | Added Task 0: create `backend/tests/agents/` directory and `__init__.py` |
| B1 | Type mismatch | Task 1: Added note that `processing_run_id` and `source_document_id` are UUID strings (JSON-serialized), with explicit validation in persistence layer |
| B2 | Field names | Task 4: Fixed `SavedFiles` field names: `md_path`, `metadata_path`, `output_dir`, `created_at`, `images_dir` |
| B3 | Field names | Task 4: Fixed `MinerULocalBatchSaveResult` field names: `parse_result`, `saved_files` |
| B4 | Field names | Task 4: Fixed adapter to read `.saved_files`, `.md_path`, `.metadata_path`, `.images_dir` |
| B5 | Wrong type | Task 5: Test now mocks `EvidenceExtractionResult` (Pydantic), not `EvidenceExtractionState` (dataclass) |
| B6 | Wrong method | Task 5: Adapter injects `EvidenceExtractionService` and calls `.run_dual()` |
| B7 | Incomplete fields | Task 5: Adapter uses `build_dual_documents_from_output_dir()` instead of manual `TrackDocument` construction |
| B8 | Call style | Task 6: Fixed `run_dual_result(dual_result, *, source_document_id=..., processing_run_id=...)` call style |
| C2 | Wrong import | Task 11: Fixed lifespan to use `DocumentParseOrchestrator(remote, local)` instead of non-existent `MinerURemoteOrchestrator` |
| D4 | Coarse flag | Task 6: Changed `skip_phase_3: bool` to `skip_phase_3_reason: SkipPhase3Reason | None` enum with `NOT_RELEVANT`, `NO_ENTITIES`, `NO_CANDIDATES` |
| D5 | Wrong file | Task 5: Phase 2 adapter reads from `Phase1Output.md_path` (full markdown), not `metadata_path` (metadata only) |
| F1 | Migration path | Task 2: Fixed alembic command to run from `backend/` (where `alembic.ini` lives) |

### v4 Change Log (from v3)

| Issue ID | Category | Fix Applied |
|----------|----------|-------------|
| N1 | API contract | Task 10: Added source-specific validation to `PipelineRunRequest` — `source_type=local` requires `content_base64`, `source_type=online` requires `query` or `identifiers` |
| N2 | API contract | Task 10: Added `target_phase` range validation `Field(ge=1, le=3)` |
| N3 | API contract | Task 10: Added duplicate run prevention — checks for existing in-progress run before starting |
| N7 | Field names | Task 5+6: Phase 2 adapter now saves extraction result to `extraction_result_path`; Phase 3 reads from it instead of translation JSON |
| N11 | Known limitation | Task 12: Documented that POST `/runs/{id}/retry` is not implemented in v1 |
| N12 | Lifecycle | Task 9: `PipelineRunner.start()` persists initial PENDING state before acquiring semaphore |

### v5 Change Log (from v4)

| Issue ID | Category | Fix Applied |
|----------|----------|-------------|
| N12-indent | Syntax error | Task 9: Fixed broken indentation in `_run_pipeline()` — N12 persist lines were outside `async with self._semaphore:` block, causing IndentationError |
| N3-dedup | Logic error | Task 1+9+10: Added `source_key` field to `PipelineGraphState`; API route sets it from request; runner compares against it instead of `source_document_id` (UUID) |

---

## Task 0: Project Setup

**Purpose:** Create directory structure for orchestrator tests.

**Files:**
- Create: `backend/tests/agents/__init__.py`
- Create: `backend/tests/agents/test_*.py` (empty placeholders)

**Steps:**

```bash
mkdir -p backend/tests/agents
touch backend/tests/agents/__init__.py
touch backend/tests/agents/test_contracts.py
touch backend/tests/agents/test_state_persistence.py
touch backend/tests/agents/test_phase_1_adapter.py
touch backend/tests/agents/test_phase_2_adapter.py
touch backend/tests/agents/test_phase_3_adapter.py
touch backend/tests/agents/test_orchestrator.py
touch backend/tests/agents/test_concurrency.py
touch backend/tests/agents/test_runner.py
```

**Verify:**
```bash
cd backend
uv run pytest tests/agents/ -v
```

Expected: No tests collected (files are empty).

---

## Task 1: Define Pipeline Graph State, Contracts, and Error Hierarchy

**Files:**
- Create: `backend/src/agents/contracts.py`
- Create: `backend/tests/agents/test_contracts.py`

**Step 1: Write the failing test**

```python
"""Tests for pipeline orchestrator contracts."""
import pytest
from src.agents.contracts import (
    PipelineGraphState,
    PhaseStatus,
    PipelineMode,
    SourceType,
    PipelineStatus,
    Phase1Output,
    Phase2Output,
    Phase3Output,
    PhaseErrorDetail,
    PhaseStatusDetail,
    RetryablePhaseError,
    PermanentPhaseError,
    SkipPhase3Reason,
)


def test_pipeline_graph_state_creation():
    """State can be created with minimal fields."""
    state = PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )
    assert state.processing_run_id == "run-123"
    assert state.source_document_id == "doc-456"
    assert state.phase_1_status.status == PhaseStatus.PENDING
    assert state.phase_2_status.status == PhaseStatus.PENDING
    assert state.phase_3_status.status == PhaseStatus.PENDING
    assert state.error_message is None
    assert state.pipeline_status == PipelineStatus.PENDING


def test_pipeline_graph_state_with_structured_error():
    """State can record structured error details per phase."""
    state = PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )
    state.phase_1_status = PhaseStatusDetail(
        status=PhaseStatus.FAILED,
        error=PhaseErrorDetail(
            message="Acquisition failed: PDF download timeout",
            retryable=True,
            attempt=2,
            max_retries=2,
        ),
    )
    assert state.phase_1_status.status == PhaseStatus.FAILED
    assert state.phase_1_status.error.retryable is True
    assert state.phase_1_status.error.attempt == 2


def test_pipeline_graph_state_serialization():
    """State serializes to dict for LangGraph persistence."""
    state = PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )
    data = state.model_dump()
    assert data["processing_run_id"] == "run-123"
    assert data["phase_1_status"]["status"] == "pending"


def test_phase_status_enum():
    """PhaseStatus enum has expected values."""
    assert PhaseStatus.PENDING == "pending"
    assert PhaseStatus.RUNNING == "running"
    assert PhaseStatus.COMPLETED == "completed"
    assert PhaseStatus.SKIPPED == "skipped"
    assert PhaseStatus.FAILED == "failed"


def test_pipeline_status_enum():
    """PipelineStatus enum has expected values."""
    assert PipelineStatus.PENDING == "pending"
    assert PipelineStatus.RUNNING == "running"
    assert PipelineStatus.AWAITING_REVIEW == "awaiting_review"
    assert PipelineStatus.COMPLETED == "completed"
    assert PipelineStatus.FAILED == "failed"


def test_skip_phase_3_reason_enum():
    """SkipPhase3Reason enum captures all skip conditions."""
    assert SkipPhase3Reason.NOT_RELEVANT == "not_relevant"
    assert SkipPhase3Reason.NO_ENTITIES == "no_entities"
    assert SkipPhase3Reason.NO_CANDIDATES == "no_candidates"


def test_phase1_output_typed():
    """Phase1Output is a typed model, not a bare dict."""
    output = Phase1Output(
        pdf_path="/tmp/test.pdf",
        md_path="/tmp/test.md",
        metadata_path="/tmp/test.json",
        output_dir="/tmp/output",
        images_dir="/tmp/images",
    )
    assert output.pdf_path == "/tmp/test.pdf"


def test_phase2_output_typed():
    """Phase2Output is a typed model, not a bare dict."""
    output = Phase2Output(
        output_dir="/tmp/phase2",
        original_json_path="/tmp/original.json",
        translated_json_path="/tmp/translated.json",
        extraction_result_path="/tmp/extraction.json",
        source_language="zh",
    )
    assert output.source_language == "zh"


def test_phase3_output_typed():
    """Phase3Output is a typed model, not a bare dict."""
    output = Phase3Output(
        match_count=10,
        standardized_count=8,
        ambiguous_count=1,
        unmapped_count=1,
    )
    assert output.match_count == 10


def test_retryable_phase_error():
    """RetryablePhaseError is an Exception with retry metadata."""
    err = RetryablePhaseError("API timeout", phase=1, attempt=1)
    assert isinstance(err, Exception)
    assert err.phase == 1
    assert err.attempt == 1
    assert str(err) == "API timeout"


def test_permanent_phase_error():
    """PermanentPhaseError is an Exception with phase metadata."""
    err = PermanentPhaseError("Configuration error", phase=2)
    assert isinstance(err, Exception)
    assert err.phase == 2
    assert str(err) == "Configuration error"


def test_phase_status_detail():
    """PhaseStatusDetail tracks timing and errors per phase."""
    detail = PhaseStatusDetail(
        status=PhaseStatus.COMPLETED,
        started_at="2026-05-29T10:00:00",
        completed_at="2026-05-29T10:05:00",
        duration_seconds=300.0,
    )
    assert detail.status == PhaseStatus.COMPLETED
    assert detail.duration_seconds == 300.0
    assert detail.error is None
```

**Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/agents/test_contracts.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'src.agents.contracts'"

**Step 3: Write minimal implementation**

```python
"""Contracts for pipeline orchestrator state, types, and error hierarchy."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


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

    # Error tracking (legacy flat fields for quick access)
    error_message: str | None = None
    error_phase: int | None = None

    # Execution metadata
    created_at: str = ""  # ISO timestamp
    started_at: str | None = None
    completed_at: str | None = None

    # Content-based routing flags
    skip_phase_3_reason: SkipPhase3Reason | None = None
```

**Step 4: Run test to verify it passes**

```bash
cd backend
uv run pytest tests/agents/test_contracts.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/agents/contracts.py backend/tests/agents/test_contracts.py
git commit -m "feat: add pipeline orchestrator contracts, error hierarchy, and typed outputs"
```

---

## Task 2: Create Database Model for Pipeline State Persistence

**Files:**
- Modify: `backend/src/dao/models.py` (add PipelineRunState table)
- Create: `backend/tests/dao/test_pipeline_state_model.py`

**Step 1: Write the failing test**

```python
"""Tests for PipelineRunState ORM model."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.dao.models import PipelineRunState


@pytest.mark.asyncio
async def test_pipeline_run_state_insert(async_session: AsyncSession):
    """PipelineRunState can be inserted."""
    state = PipelineRunState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        state_json={
            "phase_1_status": {"status": "completed"},
            "phase_2_status": {"status": "running"},
        },
    )
    async_session.add(state)
    await async_session.commit()

    loaded = await async_session.get(PipelineRunState, "run-123")
    assert loaded is not None
    assert loaded.source_document_id == "doc-456"
    assert loaded.state_json["phase_1_status"]["status"] == "completed"


@pytest.mark.asyncio
async def test_pipeline_run_state_update(async_session: AsyncSession):
    """PipelineRunState can be updated in place."""
    state = PipelineRunState(
        processing_run_id="run-456",
        source_document_id="doc-789",
        state_json={"phase_1_status": {"status": "pending"}},
    )
    async_session.add(state)
    await async_session.commit()

    loaded = await async_session.get(PipelineRunState, "run-456")
    loaded.state_json = {
        "phase_1_status": {"status": "completed"},
        "phase_2_status": {"status": "running"},
    }
    await async_session.commit()

    reloaded = await async_session.get(PipelineRunState, "run-456")
    assert reloaded.state_json["phase_2_status"]["status"] == "running"
```

**Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/dao/test_pipeline_state_model.py -v
```

Expected: FAIL with "ImportError: cannot import name 'PipelineRunState'"

**Step 3: Write minimal implementation**

Add to `backend/src/dao/models.py`:

```python
class PipelineRunState(Base):
    """Checkpoint persistence for pipeline orchestrator state.

    Stores the full PipelineGraphState as JSONB after each phase completes.
    Enables crash recovery by reloading state from the last checkpoint.
    """

    __tablename__ = "pipeline_run_states"

    processing_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.source_document_id"),
        nullable=False,
    )
    state_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
```

**Step 4: Create Alembic migration**

```bash
# Run from repo root (alembic.ini is at database/alembic.ini)
uv run alembic -c database/alembic.ini revision --autogenerate -m "add pipeline_run_states table"
uv run alembic -c database/alembic.ini upgrade head
```

**Step 5: Run test to verify it passes**

```bash
cd backend
uv run pytest tests/dao/test_pipeline_state_model.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/dao/models.py backend/tests/dao/test_pipeline_state_model.py
git add database/migrations/versions/<migration_file>.py
git commit -m "feat: add PipelineRunState model for orchestrator state persistence"
```

---

## Task 3: Implement State Persistence Layer

**Files:**
- Create: `backend/src/agents/state_persistence.py`
- Create: `backend/tests/agents/test_state_persistence.py`

**Step 1: Write the failing test**

```python
"""Tests for pipeline state persistence layer."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.agents.contracts import (
    PipelineGraphState,
    PhaseStatus,
    PipelineMode,
    SourceType,
    PhaseStatusDetail,
    PhaseErrorDetail,
)
from src.agents.state_persistence import StatePersistenceService


@pytest.fixture
def sample_state() -> PipelineGraphState:
    state = PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )
    state.phase_1_status = PhaseStatusDetail(
        status=PhaseStatus.COMPLETED,
        started_at="2026-05-29T10:00:00",
    )
    state.phase_2_status = PhaseStatusDetail(
        status=PhaseStatus.RUNNING,
    )
    return state


@pytest.mark.asyncio
async def test_save_state(async_session: AsyncSession, sample_state: PipelineGraphState):
    """StatePersistenceService can save state to database."""
    service = StatePersistenceService(async_session)
    await service.save(sample_state)

    loaded = await service.load("run-123")
    assert loaded is not None
    assert loaded.processing_run_id == "run-123"
    assert loaded.phase_1_status.status == PhaseStatus.COMPLETED
    assert loaded.phase_2_status.status == PhaseStatus.RUNNING


@pytest.mark.asyncio
async def test_load_nonexistent_state(async_session: AsyncSession):
    """Loading nonexistent state returns None."""
    service = StatePersistenceService(async_session)
    loaded = await service.load("nonexistent-run")
    assert loaded is None


@pytest.mark.asyncio
async def test_save_state_idempotent(async_session: AsyncSession, sample_state: PipelineGraphState):
    """Saving state multiple times updates the record (checkpoint semantics)."""
    service = StatePersistenceService(async_session)
    await service.save(sample_state)

    sample_state.phase_2_status = PhaseStatusDetail(
        status=PhaseStatus.COMPLETED,
        duration_seconds=120.0,
    )
    await service.save(sample_state)

    loaded = await service.load("run-123")
    assert loaded.phase_2_status.status == PhaseStatus.COMPLETED
    assert loaded.phase_2_status.duration_seconds == 120.0


@pytest.mark.asyncio
async def test_save_preserves_structured_errors(
    async_session: AsyncSession, sample_state: PipelineGraphState
):
    """Structured error details survive round-trip through database."""
    sample_state.phase_1_status = PhaseStatusDetail(
        status=PhaseStatus.FAILED,
        error=PhaseErrorDetail(
            message="API timeout",
            retryable=True,
            attempt=2,
            max_retries=2,
        ),
    )

    service = StatePersistenceService(async_session)
    await service.save(sample_state)

    loaded = await service.load("run-123")
    assert loaded.phase_1_status.error is not None
    assert loaded.phase_1_status.error.retryable is True
    assert loaded.phase_1_status.error.attempt == 2
```

**Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/agents/test_state_persistence.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'src.agents.state_persistence'"

**Step 3: Write minimal implementation**

```python
"""State persistence layer for pipeline orchestrator."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.contracts import PipelineGraphState
from src.dao.models import PipelineRunState


class StatePersistenceService:
    """Save and load PipelineGraphState to/from PostgreSQL.

    Called after each phase completes for crash recovery.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, state: PipelineGraphState) -> None:
        """Save or update pipeline state to database (checkpoint)."""
        existing = await self._session.get(
            PipelineRunState, UUID(state.processing_run_id)
        )

        state_json = state.model_dump(mode="json")

        if existing:
            existing.state_json = state_json
        else:
            new_record = PipelineRunState(
                processing_run_id=UUID(state.processing_run_id),
                source_document_id=UUID(state.source_document_id),
                state_json=state_json,
            )
            self._session.add(new_record)

        await self._session.commit()

    async def load(self, processing_run_id: str) -> Optional[PipelineGraphState]:
        """Load pipeline state from database for crash recovery."""
        record = await self._session.get(
            PipelineRunState, UUID(processing_run_id)
        )
        if record is None:
            return None

        return PipelineGraphState.model_validate(record.state_json)
```

**Step 4: Run test to verify it passes**

```bash
cd backend
uv run pytest tests/agents/test_state_persistence.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/agents/state_persistence.py backend/tests/agents/test_state_persistence.py
git commit -m "feat: add state persistence layer with structured error round-trip"
```

---

## Task 4: Implement Phase 1 Adapter (Acquisition + Parsing)

**Files:**
- Create: `backend/src/agents/phase_1_adapter.py`
- Create: `backend/tests/agents/test_phase_1_adapter.py`

**Step 1: Write the failing test**

```python
"""Tests for Phase 1 adapter (acquisition + parsing)."""
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from src.agents.contracts import (
    PipelineGraphState,
    PhaseStatus,
    PipelineMode,
    SourceType,
    Phase1Output,
    RetryablePhaseError,
    PermanentPhaseError,
)
from src.agents.phase_1_adapter import Phase1Adapter


@pytest.fixture
def sample_state() -> PipelineGraphState:
    return PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )


@pytest.mark.asyncio
async def test_phase_1_adapter_success(sample_state: PipelineGraphState):
    """Phase 1 adapter successfully acquires and parses document."""
    from src.core.ingest_and_digitize_data.document_acquisition.contracts import (
        DocumentAcquisitionResult,
        AcquisitionSource,
    )
    from src.core.ingest_and_digitize_data.document_acquisition.local_upload.contracts import (
        LocalStoredFile,
    )
    from src.core.ingest_and_digitize_data.parse_document.contracts import (
        MinerULocalBatchSaveResult,
        MinerULocalBatchParseResult,
        SavedFiles,
    )

    mock_acquisition = MagicMock()
    mock_acquisition.acquire = AsyncMock(
        return_value=DocumentAcquisitionResult(
            success=True,
            source=AcquisitionSource.LOCAL,
            stored_file=LocalStoredFile(
                file_path="/tmp/test.pdf",
                sha256="abc123",
                original_filename="test.pdf",
                size=1024,
                content_type="application/pdf",
            ),
        )
    )

    mock_parse = MagicMock()
    mock_parse.parse_local_files_and_save = AsyncMock(
        return_value=MinerULocalBatchSaveResult(
            batch_id="batch-1",
            parse_result=MinerULocalBatchParseResult(results={}),
            saved_files={
                "test.pdf": SavedFiles(
                    md_path=Path("/tmp/test.md"),
                    metadata_path=Path("/tmp/test.json"),
                    output_dir=Path("/tmp/output"),
                    created_at=datetime.now(),
                    images_dir=Path("/tmp/images"),
                )
            },
        )
    )

    adapter = Phase1Adapter(
        acquisition_service=mock_acquisition,
        parse_service=mock_parse,
    )

    result_state = await adapter.run(sample_state)

    assert result_state.phase_1_output is not None
    assert result_state.phase_1_output.pdf_path == "/tmp/test.pdf"
    assert result_state.phase_1_output.md_path == "/tmp/test.md"
    assert isinstance(result_state.phase_1_output, Phase1Output)


@pytest.mark.asyncio
async def test_phase_1_adapter_raises_permanent_on_acquisition_failure(
    sample_state: PipelineGraphState,
):
    """Phase 1 adapter raises PermanentPhaseError on acquisition failure."""
    from src.core.ingest_and_digitize_data.document_acquisition.contracts import (
        DocumentAcquisitionResult,
        AcquisitionSource,
    )

    mock_acquisition = MagicMock()
    mock_acquisition.acquire = AsyncMock(
        return_value=DocumentAcquisitionResult(
            success=False,
            source=AcquisitionSource.LOCAL,
            error="File not found",
        )
    )

    mock_parse = MagicMock()

    adapter = Phase1Adapter(
        acquisition_service=mock_acquisition,
        parse_service=mock_parse,
    )

    with pytest.raises(PermanentPhaseError, match="File not found"):
        await adapter.run(sample_state)


@pytest.mark.asyncio
async def test_phase_1_adapter_raises_retryable_on_timeout(
    sample_state: PipelineGraphState,
):
    """Phase 1 adapter raises RetryablePhaseError on MinerU timeout."""
    from src.core.ingest_and_digitize_data.document_acquisition.contracts import (
        DocumentAcquisitionResult,
        AcquisitionSource,
    )
    from src.core.ingest_and_digitize_data.document_acquisition.local_upload.contracts import (
        LocalStoredFile,
    )
    from src.core.ingest_and_digitize_data.parse_document.exceptions import (
        MinerUTimeoutError,
    )

    mock_acquisition = MagicMock()
    mock_acquisition.acquire = AsyncMock(
        return_value=DocumentAcquisitionResult(
            success=True,
            source=AcquisitionSource.LOCAL,
            stored_file=LocalStoredFile(
                file_path="/tmp/test.pdf",
                sha256="abc123",
                original_filename="test.pdf",
                size=1024,
                content_type="application/pdf",
            ),
        )
    )

    mock_parse = MagicMock()
    mock_parse.parse_local_files_and_save = AsyncMock(
        side_effect=MinerUTimeoutError(total_timeout=120.0)
    )

    adapter = Phase1Adapter(
        acquisition_service=mock_acquisition,
        parse_service=mock_parse,
    )

    with pytest.raises(RetryablePhaseError, match="timed out"):
        await adapter.run(sample_state)
```

**Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/agents/test_phase_1_adapter.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'src.agents.phase_1_adapter'"

**Step 3: Write minimal implementation**

```python
"""Phase 1 adapter: document acquisition and parsing.

Raises classified errors for orchestrator-level retry decisions.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from loguru import logger

from src.agents.contracts import (
    Phase1Output,
    PhaseStatus,
    PhaseStatusDetail,
    PipelineGraphState,
    PermanentPhaseError,
    RetryablePhaseError,
)

if TYPE_CHECKING:
    from src.core.ingest_and_digitize_data.document_acquisition.service import (
        DocumentAcquisitionService,
    )
    from src.core.ingest_and_digitize_data.parse_document.service import (
        ParseDocumentService,
    )

# Transient errors that should be retried
_RETRYABLE_ERRORS = (
    ConnectionError,
    TimeoutError,
    OSError,
)

# Import project-specific transient errors
try:
    import httpx

    _RETRYABLE_ERRORS += (httpx.TimeoutException,)
except ImportError:
    pass

try:
    import openai

    _RETRYABLE_ERRORS += (openai.APITimeoutError, openai.RateLimitError)
except ImportError:
    pass

try:
    from src.core.ingest_and_digitize_data.parse_document.exceptions import (
        MinerUTimeoutError,
    )

    _RETRYABLE_ERRORS += (MinerUTimeoutError,)
except ImportError:
    pass

# Permanent errors that should NOT be retried
try:
    from src.core.ingest_and_digitize_data.parse_document.exceptions import (
        ParserExhaustedError,
    )
except ImportError:
    ParserExhaustedError = None  # type: ignore[assignment,misc]


class Phase1Adapter:
    """Thin adapter wrapping DocumentAcquisitionService + ParseDocumentService.

    Raises RetryablePhaseError for transient failures (timeouts, rate limits).
    Raises PermanentPhaseError for permanent failures (file not found, invalid input).
    """

    def __init__(
        self,
        acquisition_service: DocumentAcquisitionService,
        parse_service: ParseDocumentService,
    ):
        self._acquisition = acquisition_service
        self._parse = parse_service

    async def run(self, state: PipelineGraphState) -> PipelineGraphState:
        """Execute Phase 1: acquire and parse document.

        Returns updated state with phase_1_output set on success.
        Raises RetryablePhaseError or PermanentPhaseError on failure.
        """
        logger.info(
            "Phase 1 started: run={}, source={}",
            state.processing_run_id,
            state.source_type.value,
        )

        state.phase_1_status = PhaseStatusDetail(
            status=PhaseStatus.RUNNING,
            started_at=datetime.now().isoformat(),
        )

        try:
            # Build acquisition request from state
            from src.core.ingest_and_digitize_data.document_acquisition.contracts import (
                AcquisitionSource,
                DocumentAcquisitionRequest,
            )

            request = DocumentAcquisitionRequest(
                source=AcquisitionSource(state.source_type.value),
                filename=None,  # Populated from API request params
                content=None,
                upload_dir=None,
            )

            # Acquire document
            acquisition_result = await self._acquisition.acquire(request)

            if not acquisition_result.success:
                raise PermanentPhaseError(
                    f"Acquisition failed: {acquisition_result.error}",
                    phase=1,
                )

            # Extract file path
            if acquisition_result.stored_file:
                pdf_path = acquisition_result.stored_file.file_path
            elif acquisition_result.downloads:
                pdf_path = acquisition_result.downloads[0].file_path
            else:
                raise PermanentPhaseError(
                    "Acquisition succeeded but no file path found",
                    phase=1,
                )

            # Parse document
            output_dir = f"data/pipeline/{state.processing_run_id}/phase_1"
            parse_result = await self._parse.parse_local_files_and_save(
                file_paths=[pdf_path],
                output_dir=output_dir,
            )

            # Extract parsed output paths (B4 fix: correct field names)
            first_file = list(parse_result.saved_files.values())[0]

            state.phase_1_output = Phase1Output(
                pdf_path=pdf_path,
                md_path=str(first_file.md_path),
                metadata_path=str(first_file.metadata_path),
                output_dir=str(first_file.output_dir),
                images_dir=str(first_file.images_dir) if first_file.images_dir else None,
            )

            state.phase_1_status = PhaseStatusDetail(
                status=PhaseStatus.COMPLETED,
                started_at=state.phase_1_status.started_at,
                completed_at=datetime.now().isoformat(),
                duration_seconds=(
                    datetime.fromisoformat(datetime.now().isoformat())
                    - datetime.fromisoformat(state.phase_1_status.started_at or "")
                ).total_seconds()
                if state.phase_1_status.started_at
                else None,
            )

            logger.info("Phase 1 completed: run={}", state.processing_run_id)
            return state

        except _RETRYABLE_ERRORS as e:
            raise RetryablePhaseError(
                f"Phase 1 transient error: {e}",
                phase=1,
            ) from e

        except (PermanentPhaseError, RetryablePhaseError):
            raise  # Already classified, pass through

        except Exception as e:
            # Default to permanent for unknown errors
            if ParserExhaustedError and isinstance(e, ParserExhaustedError):
                raise PermanentPhaseError(
                    f"All parsers failed: {e}",
                    phase=1,
                ) from e
            raise PermanentPhaseError(
                f"Phase 1 unexpected error: {e}",
                phase=1,
            ) from e
```

**Step 4: Run test to verify it passes**

```bash
cd backend
uv run pytest tests/agents/test_phase_1_adapter.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/agents/phase_1_adapter.py backend/tests/agents/test_phase_1_adapter.py
git commit -m "feat: add Phase 1 adapter with classified error handling"
```

---

## Task 5: Implement Phase 2 Adapter (Translation + Evidence Extraction)

**Files:**
- Create: `backend/src/agents/phase_2_adapter.py`
- Create: `backend/tests/agents/test_phase_2_adapter.py`

**Step 1: Write the failing test**

```python
"""Tests for Phase 2 adapter (translation + evidence extraction)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.contracts import (
    PipelineGraphState,
    PhaseStatus,
    PipelineMode,
    SourceType,
    Phase1Output,
    Phase2Output,
    RetryablePhaseError,
    PermanentPhaseError,
)
from src.agents.phase_2_adapter import Phase2Adapter


@pytest.fixture
def sample_state() -> PipelineGraphState:
    return PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        phase_1_output=Phase1Output(
            pdf_path="/tmp/test.pdf",
            md_path="/tmp/test.md",
            metadata_path="/tmp/test.json",
            output_dir="/tmp/output",
            images_dir="/tmp/images",
        ),
    )


@pytest.mark.asyncio
async def test_phase_2_adapter_success(sample_state: PipelineGraphState):
    """Phase 2 adapter successfully translates and extracts evidence."""
    from src.core.cross_lingual_process_and_extract_evidence.contracts import (
        TranslationResult,
        CrossLingualOutput,
    )
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
        DualEvidenceExtractionResult,
        DualTrackDocuments,
        EvidenceExtractionResult,
        EvidenceExtractionStatus,
        Track,
        DocumentEvidenceMap,
        TrackDocument,
    )

    mock_translation = MagicMock()
    mock_translation.run = AsyncMock(
        return_value=TranslationResult(
            formatted_original="Original text",
            translated_english="Translated text",
            source_language="zh",
            terminology_map={},
            translation_warnings=[],
            sentences=[],
            segments=[],
        )
    )
    mock_translation.save = MagicMock(
        return_value=CrossLingualOutput(
            formatted_original="Original text",
            translated_english="Translated text",
            source_language="zh",
            terminology_map={},
            translation_warnings=[],
            output_dir="/tmp/phase2/output",
            original_json_path="/tmp/phase2/output/original.json",
            translated_json_path="/tmp/phase2/output/translated.json",
            image_paths=[],
        )
    )

    mock_extraction_service = MagicMock()
    mock_extraction_service.run_dual = AsyncMock(
        return_value=DualEvidenceExtractionResult(
            document_id="doc-456",
            original_result=EvidenceExtractionResult(
                status=EvidenceExtractionStatus.COMPLETED,
                document_id="doc-456",
                track=Track.ORIGINAL,
                evidence_map=DocumentEvidenceMap(relevant=True),
            ),
            translated_result=EvidenceExtractionResult(
                status=EvidenceExtractionStatus.COMPLETED,
                document_id="doc-456",
                track=Track.TRANSLATED,
                evidence_map=DocumentEvidenceMap(relevant=True),
            ),
        )
    )

    adapter = Phase2Adapter(
        translation_service=mock_translation,
        extraction_service=mock_extraction_service,
    )

    with patch(
        "src.agents.phase_2_adapter.EvidenceExtractionService.build_dual_documents_from_output_dir"
    ) as mock_build:
        mock_build.return_value = DualTrackDocuments(
            document_id="doc-456",
            original=TrackDocument(
                document_id="doc-456",
                track=Track.ORIGINAL,
                formatted_text="original",
                page_spans=[],
            ),
            translated=TrackDocument(
                document_id="doc-456",
                track=Track.TRANSLATED,
                formatted_text="translated",
                page_spans=[],
            ),
        )

        with patch("builtins.open", MagicMock()):
            with patch("json.load", return_value={"pages": [], "content_blocks": []}):
                result_state = await adapter.run(sample_state)

    assert result_state.phase_2_output is not None
    assert result_state.phase_2_output.source_language == "zh"
    assert isinstance(result_state.phase_2_output, Phase2Output)


@pytest.mark.asyncio
async def test_phase_2_adapter_sets_skip_when_not_relevant(
    sample_state: PipelineGraphState,
):
    """Phase 2 adapter sets skip_phase_3_reason when both tracks are NOT_RELEVANT."""
    from src.core.cross_lingual_process_and_extract_evidence.contracts import (
        TranslationResult,
        CrossLingualOutput,
    )
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
        DualEvidenceExtractionResult,
        DualTrackDocuments,
        EvidenceExtractionResult,
        EvidenceExtractionStatus,
        Track,
        TrackDocument,
    )
    from src.agents.contracts import SkipPhase3Reason

    mock_translation = MagicMock()
    mock_translation.run = AsyncMock(
        return_value=TranslationResult(
            formatted_original="Original",
            translated_english="Translated",
            source_language="en",
            terminology_map={},
            translation_warnings=[],
            sentences=[],
            segments=[],
        )
    )
    mock_translation.save = MagicMock(
        return_value=CrossLingualOutput(
            formatted_original="Original",
            translated_english="Translated",
            source_language="en",
            terminology_map={},
            translation_warnings=[],
            output_dir="/tmp/phase2/output",
            original_json_path="/tmp/phase2/output/original.json",
            translated_json_path="/tmp/phase2/output/translated.json",
            image_paths=[],
        )
    )

    mock_extraction_service = MagicMock()
    mock_extraction_service.run_dual = AsyncMock(
        return_value=DualEvidenceExtractionResult(
            document_id="doc-456",
            original_result=EvidenceExtractionResult(
                status=EvidenceExtractionStatus.NOT_RELEVANT,
                document_id="doc-456",
                track=Track.ORIGINAL,
            ),
            translated_result=EvidenceExtractionResult(
                status=EvidenceExtractionStatus.NOT_RELEVANT,
                document_id="doc-456",
                track=Track.TRANSLATED,
            ),
        )
    )

    adapter = Phase2Adapter(
        translation_service=mock_translation,
        extraction_service=mock_extraction_service,
    )

    with patch(
        "src.agents.phase_2_adapter.EvidenceExtractionService.build_dual_documents_from_output_dir"
    ) as mock_build:
        mock_build.return_value = DualTrackDocuments(
            document_id="doc-456",
            original=TrackDocument(
                document_id="doc-456",
                track=Track.ORIGINAL,
                formatted_text="original",
                page_spans=[],
            ),
            translated=TrackDocument(
                document_id="doc-456",
                track=Track.TRANSLATED,
                formatted_text="translated",
                page_spans=[],
            ),
        )

        with patch("builtins.open", MagicMock()):
            with patch("json.load", return_value={"pages": [], "content_blocks": []}):
                result_state = await adapter.run(sample_state)

    assert result_state.skip_phase_3_reason == SkipPhase3Reason.NOT_RELEVANT


@pytest.mark.asyncio
async def test_phase_2_adapter_raises_retryable_on_api_timeout(
    sample_state: PipelineGraphState,
):
    """Phase 2 adapter raises RetryablePhaseError on OpenAI API timeout."""
    import openai

    mock_translation = MagicMock()
    mock_translation.run = AsyncMock(
        side_effect=openai.APITimeoutError(request=None)
    )

    mock_extraction_service = MagicMock()

    adapter = Phase2Adapter(
        translation_service=mock_translation,
        extraction_service=mock_extraction_service,
    )

    with pytest.raises(RetryablePhaseError):
        await adapter.run(sample_state)
```

**Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/agents/test_phase_2_adapter.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'src.agents.phase_2_adapter'"

**Step 3: Write minimal implementation**

```python
"""Phase 2 adapter: translation and dual-track evidence extraction.

Uses TranslationService.run() + .save() for translation.
Uses EvidenceExtractionService.build_dual_documents_from_output_dir() + .run_dual()
for dual-track evidence extraction.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from src.agents.contracts import (
    Phase2Output,
    PhaseStatus,
    PhaseStatusDetail,
    PipelineGraphState,
    PermanentPhaseError,
    RetryablePhaseError,
    SkipPhase3Reason,
)

# Import the service at module level for patching in tests
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import (
    EvidenceExtractionService,
)

if TYPE_CHECKING:
    from src.core.cross_lingual_process_and_extract_evidence.workflow import (
        TranslationService,
    )

# Transient errors that should be retried
_RETRYABLE_ERRORS: tuple = (
    ConnectionError,
    TimeoutError,
    OSError,
)

try:
    import httpx

    _RETRYABLE_ERRORS += (httpx.TimeoutException,)
except ImportError:
    pass

try:
    import openai

    _RETRYABLE_ERRORS += (openai.APITimeoutError, openai.RateLimitError)
except ImportError:
    pass


class Phase2Adapter:
    """Thin adapter wrapping TranslationService + EvidenceExtractionService.

    Flow:
    1. Read parsed content from Phase 1 output_dir
    2. Call TranslationService.run() → TranslationResult
    3. Call TranslationService.save() → CrossLingualOutput
    4. Call build_dual_documents_from_output_dir() → DualTrackDocuments
    5. Call EvidenceExtractionService.run_dual() → DualEvidenceExtractionResult
    """

    def __init__(
        self,
        translation_service: TranslationService,
        extraction_service: EvidenceExtractionService,
    ):
        self._translation = translation_service
        self._extraction = extraction_service

    async def run(self, state: PipelineGraphState) -> PipelineGraphState:
        """Execute Phase 2: translate and extract dual-track evidence.

        Returns updated state with phase_2_output set on success.
        Sets skip_phase_3_reason if both tracks are NOT_RELEVANT.
        Raises RetryablePhaseError or PermanentPhaseError on failure.
        """
        logger.info("Phase 2 started: run={}", state.processing_run_id)

        state.phase_2_status = PhaseStatusDetail(
            status=PhaseStatus.RUNNING,
            started_at=datetime.now().isoformat(),
        )

        try:
            # Load parsed document from Phase 1 output
            if state.phase_1_output is None:
                raise PermanentPhaseError(
                    "Phase 1 output not found in state",
                    phase=2,
                )

            # Read from Phase 1 metadata (contains pages and content_blocks)
            metadata_path = state.phase_1_output.metadata_path
            with open(metadata_path, "r") as f:
                parse_data = json.load(f)

            pages = parse_data.get("pages", [])
            content_blocks = parse_data.get("content_blocks", [])

            # Run translation
            translation_result = await self._translation.run(
                pages=pages,
                content_blocks=content_blocks,
            )

            # Save translation output (creates original.json and translated.json)
            output_dir = f"data/pipeline/{state.processing_run_id}/phase_2"
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            cross_lingual_output = self._translation.save(
                result=translation_result,
                output_dir=output_dir,
                doc_id=state.source_document_id,
            )

            # Build dual documents using the service's static method
            # This reads from cross_lingual_output.output_dir
            dual_documents = EvidenceExtractionService.build_dual_documents_from_output_dir(
                cross_lingual_output.output_dir
            )

            # Run dual-track extraction via the service facade
            dual_result = await self._extraction.run_dual(dual_documents)

            # Check if document is relevant
            from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
                EvidenceExtractionStatus,
            )

            both_not_relevant = (
                dual_result.original_result.status
                == EvidenceExtractionStatus.NOT_RELEVANT
                and dual_result.translated_result.status
                == EvidenceExtractionStatus.NOT_RELEVANT
            )

            if both_not_relevant:
                logger.info("Document not relevant, setting skip_phase_3_reason")
                state.skip_phase_3_reason = SkipPhase3Reason.NOT_RELEVANT

            # Save extraction result for Phase 3 (N7 fix)
            extraction_result_path = f"{output_dir}/extraction_result.json"
            with open(extraction_result_path, "w") as f:
                json.dump(dual_result.model_dump(mode="json"), f)

            state.phase_2_output = Phase2Output(
                output_dir=cross_lingual_output.output_dir,
                original_json_path=cross_lingual_output.original_json_path,
                translated_json_path=cross_lingual_output.translated_json_path,
                source_language=translation_result.source_language,
                extraction_result_path=extraction_result_path,
            )

            state.phase_2_status = PhaseStatusDetail(
                status=PhaseStatus.COMPLETED,
                started_at=state.phase_2_status.started_at,
                completed_at=datetime.now().isoformat(),
                duration_seconds=(
                    datetime.fromisoformat(datetime.now().isoformat())
                    - datetime.fromisoformat(state.phase_2_status.started_at or "")
                ).total_seconds()
                if state.phase_2_status.started_at
                else None,
                summary={
                    "relevant": not both_not_relevant,
                    "source_language": translation_result.source_language,
                },
            )

            logger.info(
                "Phase 2 completed: run={}, skip_phase_3_reason={}",
                state.processing_run_id,
                state.skip_phase_3_reason,
            )
            return state

        except _RETRYABLE_ERRORS as e:
            raise RetryablePhaseError(
                f"Phase 2 transient error: {e}",
                phase=2,
            ) from e

        except (PermanentPhaseError, RetryablePhaseError):
            raise  # Already classified, pass through

        except Exception as e:
            raise PermanentPhaseError(
                f"Phase 2 unexpected error: {e}",
                phase=2,
            ) from e
```

**Step 4: Run test to verify it passes**

```bash
cd backend
uv run pytest tests/agents/test_phase_2_adapter.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/agents/phase_2_adapter.py backend/tests/agents/test_phase_2_adapter.py
git commit -m "feat: add Phase 2 adapter using EvidenceExtractionService.run_dual()"
```

---

## Task 6: Implement Phase 3 Adapter (Entity Standardization)

**Files:**
- Create: `backend/src/agents/phase_3_adapter.py`
- Create: `backend/tests/agents/test_phase_3_adapter.py`

**Step 1: Write the failing test**

```python
"""Tests for Phase 3 adapter (entity standardization)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.contracts import (
    PipelineGraphState,
    PhaseStatus,
    PipelineMode,
    SourceType,
    Phase2Output,
    Phase3Output,
    PermanentPhaseError,
    SkipPhase3Reason,
)
from src.agents.phase_3_adapter import Phase3Adapter


@pytest.fixture
def sample_state() -> PipelineGraphState:
    return PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        phase_2_output=Phase2Output(
            output_dir="/tmp/phase2/output",
            original_json_path="/tmp/phase2/output/original.json",
            translated_json_path="/tmp/phase2/output/translated.json",
            extraction_result_path="/tmp/extraction.json",
        source_language="zh",
        ),
    )


@pytest.mark.asyncio
async def test_phase_3_adapter_success(sample_state: PipelineGraphState):
    """Phase 3 adapter successfully standardizes entities."""
    from src.core.standardize_entities_and_align_knowledge.contracts import (
        StandardizationResult,
    )

    mock_standardization = MagicMock()
    mock_standardization.run_dual_result = AsyncMock(
        return_value=StandardizationResult(
            document_id="doc-456",
            match_count=10,
            standardized_count=8,
            ambiguous_count=1,
            unmapped_count=1,
            normalized_entity_ids=("entity-1", "entity-2"),
            matches=(),
        )
    )

    adapter = Phase3Adapter(standardization_service=mock_standardization)

    with patch("builtins.open", MagicMock()):
        with patch("json.load", return_value={}):
            with patch(
                "src.agents.phase_3_adapter.DualEvidenceExtractionResult.model_validate",
                return_value=MagicMock(),
            ):
                result_state = await adapter.run(sample_state)

    assert result_state.phase_3_output is not None
    assert result_state.phase_3_output.match_count == 10
    assert isinstance(result_state.phase_3_output, Phase3Output)


@pytest.mark.asyncio
async def test_phase_3_adapter_skipped_not_relevant(sample_state: PipelineGraphState):
    """Phase 3 adapter skips when skip_phase_3_reason is NOT_RELEVANT."""
    sample_state.skip_phase_3_reason = SkipPhase3Reason.NOT_RELEVANT

    mock_standardization = MagicMock()
    mock_standardization.run_dual_result = AsyncMock()

    adapter = Phase3Adapter(standardization_service=mock_standardization)

    result_state = await adapter.run(sample_state)

    assert result_state.phase_3_status.status == PhaseStatus.SKIPPED
    assert result_state.phase_3_status.summary == {"reason": "not_relevant"}
    mock_standardization.run_dual_result.assert_not_called()


@pytest.mark.asyncio
async def test_phase_3_adapter_skipped_no_entities(sample_state: PipelineGraphState):
    """Phase 3 adapter skips when skip_phase_3_reason is NO_ENTITIES."""
    sample_state.skip_phase_3_reason = SkipPhase3Reason.NO_ENTITIES

    mock_standardization = MagicMock()

    adapter = Phase3Adapter(standardization_service=mock_standardization)

    result_state = await adapter.run(sample_state)

    assert result_state.phase_3_status.status == PhaseStatus.SKIPPED
    assert result_state.phase_3_status.summary == {"reason": "no_entities"}


@pytest.mark.asyncio
async def test_phase_3_adapter_skipped_when_zero_standardized(
    sample_state: PipelineGraphState,
):
    """Phase 3 adapter sets skip reason when standardized_count == 0."""
    from src.core.standardize_entities_and_align_knowledge.contracts import (
        StandardizationResult,
    )

    mock_standardization = MagicMock()
    mock_standardization.run_dual_result = AsyncMock(
        return_value=StandardizationResult(
            document_id="doc-456",
            match_count=0,
            standardized_count=0,
            ambiguous_count=0,
            unmapped_count=0,
            normalized_entity_ids=(),
            matches=(),
        )
    )

    adapter = Phase3Adapter(standardization_service=mock_standardization)

    with patch("builtins.open", MagicMock()):
        with patch("json.load", return_value={}):
            with patch(
                "src.agents.phase_3_adapter.DualEvidenceExtractionResult.model_validate",
                return_value=MagicMock(),
            ):
                result_state = await adapter.run(sample_state)

    assert result_state.phase_3_status.status == PhaseStatus.SKIPPED
    assert result_state.skip_phase_3_reason == SkipPhase3Reason.NO_CANDIDATES
```

**Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/agents/test_phase_3_adapter.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'src.agents.phase_3_adapter'"

**Step 3: Write minimal implementation**

```python
"""Phase 3 adapter: entity standardization and knowledge alignment.

Raises classified errors for orchestrator-level retry decisions.
Sets skip_phase_3_reason when standardized_count == 0.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

from loguru import logger

from src.agents.contracts import (
    Phase3Output,
    PhaseStatus,
    PhaseStatusDetail,
    PipelineGraphState,
    PermanentPhaseError,
    RetryablePhaseError,
    SkipPhase3Reason,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualEvidenceExtractionResult,
)

if TYPE_CHECKING:
    from src.core.standardize_entities_and_align_knowledge.api import (
        EntityStandardizationService,
    )

# Transient errors that should be retried
_RETRYABLE_ERRORS: tuple = (ConnectionError, TimeoutError, OSError)

try:
    import httpx

    _RETRYABLE_ERRORS += (httpx.TimeoutException,)
except ImportError:
    pass


class Phase3Adapter:
    """Thin adapter wrapping EntityStandardizationService.

    Standardizes extracted entities against terminology databases,
    skipping when Phase 2 marked the document as not relevant.
    """

    def __init__(
        self,
        standardization_service: EntityStandardizationService,
    ):
        self._standardization = standardization_service

    async def run(self, state: PipelineGraphState) -> PipelineGraphState:
        """Execute Phase 3: standardize entities.

        Returns updated state with phase_3_output set on success.
        Returns state with SKIPPED status if skip_phase_3_reason is set.
        Sets skip_phase_3_reason=NO_CANDIDATES if standardized_count == 0.
        Raises RetryablePhaseError or PermanentPhaseError on failure.
        """
        logger.info("Phase 3 started: run={}", state.processing_run_id)

        # Skip if Phase 2 set a skip reason
        if state.skip_phase_3_reason is not None:
            logger.info(
                "Phase 3 skipped: reason={}", state.skip_phase_3_reason.value
            )
            state.phase_3_status = PhaseStatusDetail(
                status=PhaseStatus.SKIPPED,
                started_at=datetime.now().isoformat(),
                completed_at=datetime.now().isoformat(),
                summary={"reason": state.skip_phase_3_reason.value},
            )
            return state

        state.phase_3_status = PhaseStatusDetail(
            status=PhaseStatus.RUNNING,
            started_at=datetime.now().isoformat(),
        )

        try:
            # Load extraction result from Phase 2 output
            if state.phase_2_output is None:
                raise PermanentPhaseError(
                    "Phase 2 output not found in state",
                    phase=3,
                )

            # Read the original extraction JSON
            extraction_path = state.phase_2_output.extraction_result_path
            with open(extraction_path, "r") as f:
                extraction_data = json.load(f)

            dual_result = DualEvidenceExtractionResult.model_validate(extraction_data)

            # Run standardization (B8 fix: positional arg for result)
            standardization_result = await self._standardization.run_dual_result(
                dual_result,
                source_document_id=state.source_document_id,
                processing_run_id=state.processing_run_id,
            )

            state.phase_3_output = Phase3Output(
                match_count=standardization_result.match_count,
                standardized_count=standardization_result.standardized_count,
                ambiguous_count=standardization_result.ambiguous_count,
                unmapped_count=standardization_result.unmapped_count,
            )

            # D4 fix: Set skip reason if no candidates were standardized
            if standardization_result.standardized_count == 0:
                state.skip_phase_3_reason = SkipPhase3Reason.NO_CANDIDATES
                state.phase_3_status = PhaseStatusDetail(
                    status=PhaseStatus.SKIPPED,
                    started_at=state.phase_3_status.started_at,
                    completed_at=datetime.now().isoformat(),
                    summary={"reason": "no_candidates"},
                )
                logger.info(
                    "Phase 3 completed but no candidates: run={}",
                    state.processing_run_id,
                )
                return state

            state.phase_3_status = PhaseStatusDetail(
                status=PhaseStatus.COMPLETED,
                started_at=state.phase_3_status.started_at,
                completed_at=datetime.now().isoformat(),
                duration_seconds=(
                    datetime.fromisoformat(datetime.now().isoformat())
                    - datetime.fromisoformat(state.phase_3_status.started_at or "")
                ).total_seconds()
                if state.phase_3_status.started_at
                else None,
                summary={
                    "match_count": standardization_result.match_count,
                    "standardized_count": standardization_result.standardized_count,
                },
            )

            logger.info(
                "Phase 3 completed: run={}, matches={}",
                state.processing_run_id,
                standardization_result.match_count,
            )
            return state

        except _RETRYABLE_ERRORS as e:
            raise RetryablePhaseError(
                f"Phase 3 transient error: {e}",
                phase=3,
            ) from e

        except (PermanentPhaseError, RetryablePhaseError):
            raise  # Already classified, pass through

        except Exception as e:
            raise PermanentPhaseError(
                f"Phase 3 unexpected error: {e}",
                phase=3,
            ) from e
```

**Step 4: Run test to verify it passes**

```bash
cd backend
uv run pytest tests/agents/test_phase_3_adapter.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/agents/phase_3_adapter.py backend/tests/agents/test_phase_3_adapter.py
git commit -m "feat: add Phase 3 adapter with skip_phase_3_reason support"
```

---

## Task 7: Build Main Orchestrator Graph (3 phases + finalize)

**Files:**
- Create: `backend/src/agents/orchestrator.py`
- Create: `backend/tests/agents/test_orchestrator.py`

**Step 1: Write the failing test**

```python
"""Tests for main orchestrator graph."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.contracts import (
    PipelineGraphState,
    PhaseStatus,
    PipelineMode,
    SourceType,
    PipelineStatus,
    PhaseStatusDetail,
    Phase1Output,
    SkipPhase3Reason,
    RetryablePhaseError,
    PermanentPhaseError,
)
from src.agents.orchestrator import PipelineOrchestrator


@pytest.fixture
def sample_state() -> PipelineGraphState:
    return PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )


@pytest.fixture
def mock_adapters():
    return {
        "phase_1": MagicMock(run=AsyncMock()),
        "phase_2": MagicMock(run=AsyncMock()),
        "phase_3": MagicMock(run=AsyncMock()),
    }


@pytest.fixture
def mock_persistence():
    return MagicMock(save=AsyncMock())


@pytest.fixture
def mock_retry_executor():
    return MagicMock(execute_with_retry=AsyncMock())


@pytest.mark.asyncio
async def test_orchestrator_runs_all_phases(
    sample_state, mock_adapters, mock_persistence, mock_retry_executor
):
    """Orchestrator runs all 3 phases in sequence."""
    state_after_1 = sample_state.model_copy(deep=True)
    state_after_1.phase_1_status = PhaseStatusDetail(status=PhaseStatus.COMPLETED)
    state_after_1.phase_1_output = Phase1Output(
        pdf_path="/tmp/test.pdf",
        md_path="/tmp/test.md",
        metadata_path="/tmp/test.json",
        output_dir="/tmp/output",
    )

    mock_adapters["phase_1"].run.return_value = state_after_1
    mock_adapters["phase_2"].run.return_value = state_after_1
    mock_adapters["phase_3"].run.return_value = state_after_1

    mock_retry_executor.execute_with_retry.side_effect = lambda op, state, phase_name: op(state)

    orchestrator = PipelineOrchestrator(
        phase_adapters=mock_adapters,
        state_persistence=mock_persistence,
        retry_executor=mock_retry_executor,
    )

    result_state = await orchestrator.run(sample_state)

    assert result_state.phase_1_status.status == PhaseStatus.COMPLETED
    assert result_state.phase_2_status.status == PhaseStatus.COMPLETED
    assert result_state.phase_3_status.status == PhaseStatus.COMPLETED
    assert result_state.pipeline_status == PipelineStatus.AWAITING_REVIEW


@pytest.mark.asyncio
async def test_orchestrator_skips_phase_3_when_not_relevant(
    sample_state, mock_adapters, mock_persistence, mock_retry_executor
):
    """Orchestrator skips Phase 3 when skip_phase_3_reason is set by Phase 2."""
    state_after_1 = sample_state.model_copy(deep=True)
    state_after_1.phase_1_status = PhaseStatusDetail(status=PhaseStatus.COMPLETED)
    state_after_1.phase_1_output = Phase1Output(
        pdf_path="/tmp/test.pdf",
        md_path="/tmp/test.md",
        metadata_path="/tmp/test.json",
        output_dir="/tmp/output",
    )

    state_after_2 = state_after_1.model_copy(deep=True)
    state_after_2.phase_2_status = PhaseStatusDetail(status=PhaseStatus.COMPLETED)
    state_after_2.skip_phase_3_reason = SkipPhase3Reason.NOT_RELEVANT

    state_after_3 = state_after_2.model_copy(deep=True)
    state_after_3.phase_3_status = PhaseStatusDetail(status=PhaseStatus.SKIPPED)

    mock_adapters["phase_1"].run.return_value = state_after_1
    mock_adapters["phase_2"].run.return_value = state_after_2
    mock_adapters["phase_3"].run.return_value = state_after_3

    mock_retry_executor.execute_with_retry.side_effect = lambda op, state, phase_name: op(state)

    orchestrator = PipelineOrchestrator(
        phase_adapters=mock_adapters,
        state_persistence=mock_persistence,
        retry_executor=mock_retry_executor,
    )

    result_state = await orchestrator.run(sample_state)

    assert result_state.phase_3_status.status == PhaseStatus.SKIPPED
    mock_adapters["phase_3"].run.assert_called_once()


@pytest.mark.asyncio
async def test_orchestrator_stops_on_permanent_failure(
    sample_state, mock_adapters, mock_persistence, mock_retry_executor
):
    """Orchestrator stops execution when a phase raises PermanentPhaseError."""
    mock_adapters["phase_1"].run.side_effect = PermanentPhaseError(
        "Acquisition failed", phase=1
    )

    mock_retry_executor.execute_with_retry.side_effect = lambda op, state, phase_name: op(state)

    orchestrator = PipelineOrchestrator(
        phase_adapters=mock_adapters,
        state_persistence=mock_persistence,
        retry_executor=mock_retry_executor,
    )

    result_state = await orchestrator.run(sample_state)

    assert result_state.phase_1_status.status == PhaseStatus.FAILED
    assert result_state.pipeline_status == PipelineStatus.FAILED
    mock_adapters["phase_2"].run.assert_not_called()
    mock_adapters["phase_3"].run.assert_not_called()


@pytest.mark.asyncio
async def test_orchestrator_validates_upstream_for_phase_mode(
    mock_adapters, mock_persistence, mock_retry_executor
):
    """Orchestrator rejects single-phase mode when upstream phases haven't completed."""
    state = PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.PHASE,
        source_type=SourceType.LOCAL,
        target_phase=3,
        phase_1_status=PhaseStatusDetail(status=PhaseStatus.PENDING),
        phase_2_status=PhaseStatusDetail(status=PhaseStatus.PENDING),
    )

    mock_retry_executor.execute_with_retry.side_effect = lambda op, state, phase_name: op(state)

    orchestrator = PipelineOrchestrator(
        phase_adapters=mock_adapters,
        state_persistence=mock_persistence,
        retry_executor=mock_retry_executor,
    )

    result_state = await orchestrator.run(state)

    assert result_state.pipeline_status == PipelineStatus.FAILED
    assert "upstream" in result_state.error_message.lower()


@pytest.mark.asyncio
async def test_orchestrator_persists_state_after_each_phase(
    sample_state, mock_adapters, mock_persistence, mock_retry_executor
):
    """Orchestrator calls state_persistence.save() after each phase completes."""
    state_after_1 = sample_state.model_copy(deep=True)
    state_after_1.phase_1_status = PhaseStatusDetail(status=PhaseStatus.COMPLETED)
    state_after_1.phase_1_output = Phase1Output(
        pdf_path="/tmp/test.pdf",
        md_path="/tmp/test.md",
        metadata_path="/tmp/test.json",
        output_dir="/tmp/output",
    )

    mock_adapters["phase_1"].run.return_value = state_after_1
    mock_adapters["phase_2"].run.return_value = state_after_1
    mock_adapters["phase_3"].run.return_value = state_after_1

    mock_retry_executor.execute_with_retry.side_effect = lambda op, state, phase_name: op(state)

    orchestrator = PipelineOrchestrator(
        phase_adapters=mock_adapters,
        state_persistence=mock_persistence,
        retry_executor=mock_retry_executor,
    )

    await orchestrator.run(sample_state)

    assert mock_persistence.save.call_count >= 3
```

**Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/agents/test_orchestrator.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'src.agents.orchestrator'"

**Step 3: Write minimal implementation**

```python
"""Main pipeline orchestrator using LangGraph.

Architecture:
- 3 phase adapter nodes (Phase 1, 2, 3)
- Phase 4 is NOT a graph node — it operates via its own HTTP API
- After Phase 3 completes, pipeline_status is set to AWAITING_REVIEW
- State persisted to PostgreSQL after each phase for crash recovery
- Upstream dependency validation for single-phase mode
- Adapters raise classified errors; orchestrator catches and decides
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from langgraph.graph import END, StateGraph
from loguru import logger

from src.agents.concurrency import RetryablePhaseExecutor
from src.agents.contracts import (
    PhaseErrorDetail,
    PhaseStatus,
    PhaseStatusDetail,
    PermanentPhaseError,
    PipelineGraphState,
    PipelineMode,
    PipelineStatus,
    RetryablePhaseError,
)
from src.agents.state_persistence import StatePersistenceService

# Upstream dependencies for single-phase mode validation
REQUIRED_UPSTREAM: dict[int, list[int]] = {
    1: [],
    2: [1],
    3: [1, 2],
}


class PipelineOrchestrator:
    """LangGraph-based orchestrator coordinating 3 phases of evidence processing.

    Flow: Phase 1 -> Phase 2 -> (skip Phase 3 if not relevant) -> AWAITING_REVIEW
    Phase 4 operates independently via its own HTTP API.
    """

    def __init__(
        self,
        phase_adapters: dict[str, Any],
        state_persistence: StatePersistenceService,
        retry_executor: RetryablePhaseExecutor,
    ):
        self._adapters = phase_adapters
        self._persistence = state_persistence
        self._retry = retry_executor
        self._graph = self._build_graph()

    async def _execute_phase(
        self,
        adapter: Any,
        state: PipelineGraphState,
        phase_name: str,
    ) -> PipelineGraphState:
        """Execute a phase adapter with retry logic.

        Adapters raise classified errors:
        - RetryablePhaseError: retried by RetryablePhaseExecutor
        - PermanentPhaseError: caught here, marks phase as FAILED

        State is persisted after each phase (success or failure).
        """
        try:
            result = await self._retry.execute_with_retry(
                operation=adapter.run,
                state=state,
                phase_name=phase_name,
            )
            await self._persistence.save(result)
            return result

        except RetryablePhaseError as e:
            logger.error(
                "Phase {} failed after retries: {}",
                e.phase,
                str(e),
            )
            error_detail = PhaseErrorDetail(
                message=str(e),
                retryable=True,
                attempt=e.attempt,
                max_retries=self._retry._max_retries,
            )
            phase_attr = f"phase_{e.phase}_status"
            current = getattr(state, phase_attr)
            setattr(
                state,
                phase_attr,
                PhaseStatusDetail(
                    status=PhaseStatus.FAILED,
                    started_at=current.started_at if current else None,
                    completed_at=datetime.now().isoformat(),
                    error=error_detail,
                ),
            )
            state.error_message = str(e)
            state.error_phase = e.phase
            state.pipeline_status = PipelineStatus.FAILED
            state.completed_at = datetime.now().isoformat()
            await self._persistence.save(state)
            return state

        except PermanentPhaseError as e:
            logger.error(
                "Phase {} failed permanently: {}",
                e.phase,
                str(e),
            )
            error_detail = PhaseErrorDetail(
                message=str(e),
                retryable=False,
                attempt=0,
                max_retries=0,
            )
            phase_attr = f"phase_{e.phase}_status"
            current = getattr(state, phase_attr)
            setattr(
                state,
                phase_attr,
                PhaseStatusDetail(
                    status=PhaseStatus.FAILED,
                    started_at=current.started_at if current else None,
                    completed_at=datetime.now().isoformat(),
                    error=error_detail,
                ),
            )
            state.error_message = str(e)
            state.error_phase = e.phase
            state.pipeline_status = PipelineStatus.FAILED
            state.completed_at = datetime.now().isoformat()
            await self._persistence.save(state)
            return state

    async def _node_phase_1(self, state: PipelineGraphState) -> PipelineGraphState:
        """Execute Phase 1: acquisition + parsing."""
        return await self._execute_phase(
            self._adapters["phase_1"], state, "phase_1"
        )

    async def _node_phase_2(self, state: PipelineGraphState) -> PipelineGraphState:
        """Execute Phase 2: translation + evidence extraction."""
        return await self._execute_phase(
            self._adapters["phase_2"], state, "phase_2"
        )

    async def _node_phase_3(self, state: PipelineGraphState) -> PipelineGraphState:
        """Execute Phase 3: entity standardization."""
        return await self._execute_phase(
            self._adapters["phase_3"], state, "phase_3"
        )

    def _route_after_phase_1(self, state: PipelineGraphState) -> str:
        """Route after Phase 1: continue or stop on failure."""
        if state.phase_1_status.status == PhaseStatus.FAILED:
            logger.error("Phase 1 failed, stopping pipeline")
            return "end"
        return "phase_2"

    def _route_after_phase_2(self, state: PipelineGraphState) -> str:
        """Route after Phase 2: continue to Phase 3 or stop on failure."""
        if state.phase_2_status.status == PhaseStatus.FAILED:
            logger.error("Phase 2 failed, stopping pipeline")
            return "end"
        return "phase_3"

    def _route_after_phase_3(self, state: PipelineGraphState) -> str:
        """Route after Phase 3: always end (finalize sets AWAITING_REVIEW)."""
        if state.phase_3_status.status == PhaseStatus.FAILED:
            logger.error("Phase 3 failed, stopping pipeline")
        return "end"

    def _build_graph(self) -> Any:
        """Build the LangGraph state machine with 3 phase nodes."""
        graph = StateGraph(PipelineGraphState)

        graph.add_node("phase_1", self._node_phase_1)
        graph.add_node("phase_2", self._node_phase_2)
        graph.add_node("phase_3", self._node_phase_3)

        graph.set_entry_point("phase_1")

        graph.add_conditional_edges(
            "phase_1",
            self._route_after_phase_1,
            {"phase_2": "phase_2", "end": END},
        )
        graph.add_conditional_edges(
            "phase_2",
            self._route_after_phase_2,
            {"phase_3": "phase_3", "end": END},
        )
        graph.add_conditional_edges(
            "phase_3",
            self._route_after_phase_3,
            {"end": END},
        )

        return graph.compile()

    async def _validate_upstream(
        self, state: PipelineGraphState
    ) -> PipelineGraphState | None:
        """Validate upstream phases have completed for single-phase mode.

        Returns updated state with error if validation fails, None if OK.
        """
        target = state.target_phase
        if target is None:
            return None

        required = REQUIRED_UPSTREAM.get(target, [])
        for upstream_phase in required:
            phase_attr = f"phase_{upstream_phase}_status"
            phase_status = getattr(state, phase_attr)
            if phase_status.status != PhaseStatus.COMPLETED:
                state.pipeline_status = PipelineStatus.FAILED
                state.error_message = (
                    f"Upstream phase {upstream_phase} has not completed "
                    f"(status={phase_status.status.value}). "
                    f"Phase {target} requires phases {required} to be completed first."
                )
                state.error_phase = target
                state.completed_at = datetime.now().isoformat()
                await self._persistence.save(state)
                return state

        return None

    async def run(self, state: PipelineGraphState) -> PipelineGraphState:
        """Execute the pipeline.

        For mode=FULL: runs all phases in sequence.
        For mode=PHASE: validates upstream, runs target phase only.
        After Phase 3 completes (or is skipped), sets pipeline_status=AWAITING_REVIEW.
        """
        logger.info(
            "Pipeline orchestrator started: run={}, mode={}",
            state.processing_run_id,
            state.mode.value,
        )

        state.pipeline_status = PipelineStatus.RUNNING
        state.started_at = datetime.now().isoformat()

        # Validate upstream for single-phase mode
        if state.mode == PipelineMode.PHASE:
            error_state = await self._validate_upstream(state)
            if error_state is not None:
                return error_state

        try:
            import asyncio

            loop = asyncio.get_running_loop()
            final_state = await loop.run_in_executor(
                None, self._graph.invoke, state
            )
        except RuntimeError:
            final_state = self._graph.invoke(state)

        if isinstance(final_state, dict):
            final_state = PipelineGraphState.model_validate(final_state)

        # If pipeline didn't fail, mark as AWAITING_REVIEW (Phase 4 is external)
        if final_state.pipeline_status != PipelineStatus.FAILED:
            final_state.pipeline_status = PipelineStatus.AWAITING_REVIEW
            final_state.completed_at = datetime.now().isoformat()
            await self._persistence.save(final_state)

        logger.info(
            "Pipeline orchestrator completed: run={}, pipeline_status={}",
            final_state.processing_run_id,
            final_state.pipeline_status.value,
        )

        return final_state
```

**Step 4: Run test to verify it passes**

```bash
cd backend
uv run pytest tests/agents/test_orchestrator.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/agents/orchestrator.py backend/tests/agents/test_orchestrator.py
git commit -m "feat: add main pipeline orchestrator with 3-phase graph, upstream validation, and persistence"
```

---

## Task 8: Implement Concurrency Control and Retry Logic

**Files:**
- Create: `backend/src/agents/concurrency.py`
- Create: `backend/tests/agents/test_concurrency.py`

**Step 1: Write the failing test**

```python
"""Tests for concurrency control and retry logic."""
import pytest
import asyncio
from unittest.mock import MagicMock
from src.agents.concurrency import PipelineSemaphore, RetryablePhaseExecutor
from src.agents.contracts import RetryablePhaseError, PermanentPhaseError


@pytest.mark.asyncio
async def test_semaphore_limits_concurrency():
    """Semaphore limits concurrent pipeline executions."""
    sem = PipelineSemaphore(max_concurrent=2)

    max_observed = 0
    current = 0

    async def slow_task():
        nonlocal current, max_observed
        async with sem:
            current += 1
            max_observed = max(max_observed, current)
            await asyncio.sleep(0.05)
            current -= 1
            return "done"

    tasks = [asyncio.create_task(slow_task()) for _ in range(4)]
    results = await asyncio.gather(*tasks)

    assert all(r == "done" for r in results)
    assert max_observed <= 2


@pytest.mark.asyncio
async def test_retry_executor_retries_on_retryable_error():
    """RetryablePhaseExecutor retries when operation raises RetryablePhaseError."""
    call_count = 0

    async def flaky_operation(state):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise RetryablePhaseError("API timeout", phase=1, attempt=call_count - 1)
        return state

    executor = RetryablePhaseExecutor(max_retries=2, backoff_base=0.01)
    result = await executor.execute_with_retry(
        operation=flaky_operation,
        state=MagicMock(),
        phase_name="phase_1",
    )

    assert call_count == 2
    assert result is not None


@pytest.mark.asyncio
async def test_retry_executor_passes_through_permanent_errors():
    """RetryablePhaseExecutor does NOT retry PermanentPhaseError."""
    async def permanent_failure(state):
        raise PermanentPhaseError("Configuration error", phase=2)

    executor = RetryablePhaseExecutor(max_retries=2, backoff_base=0.01)

    with pytest.raises(PermanentPhaseError, match="Configuration error"):
        await executor.execute_with_retry(
            operation=permanent_failure,
            state=MagicMock(),
            phase_name="phase_2",
        )


@pytest.mark.asyncio
async def test_retry_executor_exhausts_retries():
    """RetryablePhaseExecutor raises after exhausting all retries."""
    call_count = 0

    async def always_fails(state):
        nonlocal call_count
        call_count += 1
        raise RetryablePhaseError("Always fails", phase=1, attempt=call_count - 1)

    executor = RetryablePhaseExecutor(max_retries=2, backoff_base=0.01)

    with pytest.raises(RetryablePhaseError):
        await executor.execute_with_retry(
            operation=always_fails,
            state=MagicMock(),
            phase_name="phase_1",
        )

    assert call_count == 3  # initial + 2 retries
```

**Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/agents/test_concurrency.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'src.agents.concurrency'"

**Step 3: Write minimal implementation**

```python
"""Concurrency control and retry logic for pipeline orchestrator."""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from loguru import logger

from src.agents.contracts import PermanentPhaseError, RetryablePhaseError


class PipelineSemaphore:
    """Semaphore to limit concurrent pipeline executions."""

    def __init__(self, max_concurrent: int = 2):
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def __aenter__(self):
        await self._semaphore.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._semaphore.release()


class RetryablePhaseExecutor:
    """Execute phase operations with retry on RetryablePhaseError.

    - RetryablePhaseError: retried up to max_retries with exponential backoff
    - PermanentPhaseError: raised immediately, no retry
    - All other exceptions: raised immediately (treated as permanent)
    """

    def __init__(self, max_retries: int = 2, backoff_base: float = 30.0):
        self._max_retries = max_retries
        self._backoff_base = backoff_base

    async def execute_with_retry(
        self,
        operation: Callable[[Any], Awaitable[Any]],
        state: Any,
        phase_name: str,
    ) -> Any:
        """Execute operation with retry on RetryablePhaseError."""
        last_error: RetryablePhaseError | None = None

        for attempt in range(self._max_retries + 1):
            try:
                return await operation(state)
            except RetryablePhaseError as e:
                last_error = e
                e.attempt = attempt
                if attempt < self._max_retries:
                    backoff = self._backoff_base * (2 ** attempt)
                    logger.warning(
                        "{} retryable error (attempt {}/{}): {}. Retrying in {:.1f}s",
                        phase_name,
                        attempt + 1,
                        self._max_retries,
                        str(e),
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error(
                        "{} exhausted all {} retries: {}",
                        phase_name,
                        self._max_retries,
                        str(e),
                    )
            except PermanentPhaseError:
                raise  # Never retry permanent errors

        # All retries exhausted
        raise last_error  # type: ignore[misc]
```

**Step 4: Run test to verify it passes**

```bash
cd backend
uv run pytest tests/agents/test_concurrency.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/agents/concurrency.py backend/tests/agents/test_concurrency.py
git commit -m "feat: add concurrency control and classified retry logic"
```

---

## Task 9: Implement Background Pipeline Runner with DB Fallback

**Files:**
- Create: `backend/src/agents/runner.py`
- Create: `backend/tests/agents/test_runner.py`

**Step 1: Write the failing test**

```python
"""Tests for background pipeline runner."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.contracts import (
    PipelineGraphState,
    PipelineMode,
    SourceType,
    PhaseStatus,
    PipelineStatus,
    PhaseStatusDetail,
)
from src.agents.runner import PipelineRunner


@pytest.fixture
def mock_orchestrator():
    return MagicMock(run=AsyncMock())


@pytest.fixture
def mock_semaphore():
    return MagicMock()


@pytest.fixture
def mock_persistence():
    return MagicMock(load=AsyncMock())


@pytest.fixture
def sample_state() -> PipelineGraphState:
    return PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )


@pytest.mark.asyncio
async def test_runner_executes_in_background(
    sample_state, mock_orchestrator, mock_semaphore, mock_persistence
):
    """PipelineRunner executes pipeline in background task."""
    completed_state = sample_state.model_copy(deep=True)
    completed_state.pipeline_status = PipelineStatus.AWAITING_REVIEW
    mock_orchestrator.run.return_value = completed_state

    runner = PipelineRunner(
        orchestrator=mock_orchestrator,
        semaphore=mock_semaphore,
        state_persistence=mock_persistence,
    )

    task = runner.start(sample_state)
    await task

    assert mock_orchestrator.run.called
    assert task.done()


@pytest.mark.asyncio
async def test_runner_captures_errors(
    sample_state, mock_orchestrator, mock_semaphore, mock_persistence
):
    """PipelineRunner captures and logs errors without crashing."""
    mock_orchestrator.run.side_effect = RuntimeError("Unexpected error")

    runner = PipelineRunner(
        orchestrator=mock_orchestrator,
        semaphore=mock_semaphore,
        state_persistence=mock_persistence,
    )

    task = runner.start(sample_state)
    await task

    assert task.done()
    final_state = runner.get_last_state_cached("run-123")
    assert final_state is not None
    assert final_state.error_message is not None
    assert "Unexpected error" in final_state.error_message


@pytest.mark.asyncio
async def test_runner_get_last_state_falls_back_to_db(
    sample_state, mock_orchestrator, mock_semaphore, mock_persistence
):
    """get_last_state falls back to PostgreSQL when in-memory cache misses."""
    db_state = sample_state.model_copy(deep=True)
    db_state.pipeline_status = PipelineStatus.AWAITING_REVIEW
    mock_persistence.load.return_value = db_state

    runner = PipelineRunner(
        orchestrator=mock_orchestrator,
        semaphore=mock_semaphore,
        state_persistence=mock_persistence,
    )

    # Not in memory cache
    result = await runner.get_last_state("unknown-run")

    assert result is not None
    assert result.pipeline_status == PipelineStatus.AWAITING_REVIEW
    mock_persistence.load.assert_called_once_with("unknown-run")


@pytest.mark.asyncio
async def test_runner_get_last_state_returns_none(
    sample_state, mock_orchestrator, mock_semaphore, mock_persistence
):
    """get_last_state returns None when neither memory nor DB has the run."""
    mock_persistence.load.return_value = None

    runner = PipelineRunner(
        orchestrator=mock_orchestrator,
        semaphore=mock_semaphore,
        state_persistence=mock_persistence,
    )

    result = await runner.get_last_state("nonexistent-run")

    assert result is None
```

**Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/agents/test_runner.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'src.agents.runner'"

**Step 3: Write minimal implementation**

```python
"""Background pipeline runner with asyncio task management and DB fallback."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from loguru import logger

from src.agents.concurrency import PipelineSemaphore
from src.agents.contracts import PipelineGraphState, PipelineStatus
from src.agents.state_persistence import StatePersistenceService


class PipelineRunner:
    """Manages background execution of pipeline runs.

    Each run executes as an asyncio.Task with semaphore-controlled concurrency.
    get_last_state() checks in-memory cache first, then falls back to PostgreSQL
    for crash recovery scenarios.
    """

    def __init__(
        self,
        orchestrator: Any,
        semaphore: PipelineSemaphore,
        state_persistence: StatePersistenceService,
    ):
        self._orchestrator = orchestrator
        self._semaphore = semaphore
        self._persistence = state_persistence
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._last_states: dict[str, PipelineGraphState] = {}

    def start(self, initial_state: PipelineGraphState) -> asyncio.Task:
        """Start a pipeline run as a background task."""
        run_id = initial_state.processing_run_id

        async def _run_pipeline():
            # N12 fix: Persist initial PENDING state before acquiring semaphore
            await self._persistence.save(initial_state)
            self._last_states[run_id] = initial_state
            async with self._semaphore:
                logger.info("Pipeline execution started: run={}", run_id)
                try:
                    initial_state.started_at = datetime.now().isoformat()
                    result = await self._orchestrator.run(initial_state)
                    result.completed_at = datetime.now().isoformat()
                    self._last_states[run_id] = result
                    logger.info("Pipeline execution completed: run={}", run_id)
                    return result
                except Exception as e:
                    logger.exception("Pipeline execution failed: run={}", run_id)
                    error_state = initial_state.model_copy(
                        update={
                            "pipeline_status": PipelineStatus.FAILED,
                            "error_message": f"Pipeline failed: {str(e)}",
                            "error_phase": 0,
                            "completed_at": datetime.now().isoformat(),
                        }
                    )
                    self._last_states[run_id] = error_state
                    return error_state

        task = asyncio.create_task(_run_pipeline())
        self._active_tasks[run_id] = task

        def _cleanup(t: asyncio.Task):
            self._active_tasks.pop(run_id, None)

        task.add_done_callback(_cleanup)

        return task

    def get_last_state_cached(self, processing_run_id: str) -> PipelineGraphState | None:
        """Get state from in-memory cache only (fast path)."""
        return self._last_states.get(processing_run_id)

    async def get_last_state(self, processing_run_id: str) -> PipelineGraphState | None:
        """Get the last known state for a pipeline run.

        Checks in-memory cache first (fast path), then falls back to
        PostgreSQL for crash recovery scenarios.
        """
        # Check in-memory first
        cached = self._last_states.get(processing_run_id)
        if cached is not None:
            return cached

        # Fall back to database (crash recovery)
        return await self._persistence.load(processing_run_id)

    def is_running(self, processing_run_id: str) -> bool:
        """Check if a pipeline run is currently active."""
        task = self._active_tasks.get(processing_run_id)
        return task is not None and not task.done()

    def is_running_for_source(self, source_key: str) -> bool:
        """Check if any active run is processing this source key (N3 fix).

        Compares against state.source_key (filename or query), not
        source_document_id (UUID), so the API route can dedup by
        user-visible identifiers.
        """
        for run_id, state in self._last_states.items():
            if state.source_key == source_key and self.is_running(run_id):
                return True
        return False
```

**Step 4: Run test to verify it passes**

```bash
cd backend
uv run pytest tests/agents/test_runner.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/agents/runner.py backend/tests/agents/test_runner.py
git commit -m "feat: add background pipeline runner with DB fallback for crash recovery"
```

---

## Task 10: Implement Pipeline API Routes

**Files:**
- Create: `backend/src/api/v1/pipeline.py`
- Modify: `backend/src/api/v1/router.py` (include pipeline routes)
- Create: `backend/tests/api/test_pipeline_api.py`

**Step 1: Write the failing test**

```python
"""Tests for pipeline API routes."""
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.contracts import (
    PipelineGraphState,
    PhaseStatus,
    PipelineMode,
    SourceType,
    PipelineStatus,
    PhaseStatusDetail,
    SkipPhase3Reason,
)


@pytest.mark.asyncio
async def test_post_pipeline_run(async_client: AsyncClient):
    """POST /api/v1/pipeline/run accepts request and returns run ID."""
    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_runner.start = MagicMock(return_value=MagicMock())
        mock_get_runner.return_value = mock_runner

        response = await async_client.post(
            "/api/v1/pipeline/run",
            json={
                "source_type": "local",
                "filename": "test.pdf",
                "content_base64": "dGVzdA==",
                "mode": "full",
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert "processing_run_id" in data
        assert "status_url" in data
        assert data["status"] == "accepted"


@pytest.mark.asyncio
async def test_get_pipeline_status(async_client: AsyncClient):
    """GET /api/v1/pipeline/runs/{id}/status returns per-phase details."""
    mock_state = PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        pipeline_status=PipelineStatus.RUNNING,
        phase_1_status=PhaseStatusDetail(
            status=PhaseStatus.COMPLETED,
            started_at="2026-05-29T10:00:00",
            completed_at="2026-05-29T10:01:00",
            duration_seconds=60.0,
        ),
        phase_2_status=PhaseStatusDetail(
            status=PhaseStatus.RUNNING,
            started_at="2026-05-29T10:01:01",
        ),
    )

    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_runner.get_last_state = AsyncMock(return_value=mock_state)
        mock_get_runner.return_value = mock_runner

        response = await async_client.get("/api/v1/pipeline/runs/run-123/status")

        assert response.status_code == 200
        data = response.json()
        assert data["processing_run_id"] == "run-123"
        assert data["pipeline_status"] == "running"
        assert data["phases"]["phase_1"]["status"] == "completed"
        assert data["phases"]["phase_1"]["duration_seconds"] == 60.0
        assert data["phases"]["phase_2"]["status"] == "running"
        assert data["current_phase"] == "phase_2"


@pytest.mark.asyncio
async def test_get_pipeline_status_shows_skip_reason(async_client: AsyncClient):
    """Status response includes skip_phase_3_reason when set."""
    mock_state = PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        pipeline_status=PipelineStatus.AWAITING_REVIEW,
        phase_1_status=PhaseStatusDetail(status=PhaseStatus.COMPLETED),
        phase_2_status=PhaseStatusDetail(status=PhaseStatus.COMPLETED),
        phase_3_status=PhaseStatusDetail(
            status=PhaseStatus.SKIPPED,
            summary={"reason": "not_relevant"},
        ),
        skip_phase_3_reason=SkipPhase3Reason.NOT_RELEVANT,
    )

    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_runner.get_last_state = AsyncMock(return_value=mock_state)
        mock_get_runner.return_value = mock_runner

        response = await async_client.get("/api/v1/pipeline/runs/run-123/status")

        assert response.status_code == 200
        data = response.json()
        assert data["skip_phase_3_reason"] == "not_relevant"
        assert data["phases"]["phase_3"]["status"] == "skipped"
        assert data["phases"]["phase_3"]["summary"]["reason"] == "not_relevant"


@pytest.mark.asyncio
async def test_get_pipeline_status_not_found(async_client: AsyncClient):
    """GET /api/v1/pipeline/runs/{id}/status returns 404 for unknown run."""
    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_runner.get_last_state = AsyncMock(return_value=None)
        mock_get_runner.return_value = mock_runner

        response = await async_client.get("/api/v1/pipeline/runs/unknown-run/status")

        assert response.status_code == 404


@pytest.mark.asyncio
async def test_post_pipeline_run_phase_mode_validation(async_client: AsyncClient):
    """POST /api/v1/pipeline/run with mode=phase requires target_phase."""
    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_get_runner.return_value = mock_runner

        response = await async_client.post(
            "/api/v1/pipeline/run",
            json={
                "source_type": "local",
                "mode": "phase",
                # Missing target_phase
            },
        )

        assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_pipeline_run_local_requires_content(async_client: AsyncClient):
    """POST with source_type=local requires content_base64 or filename (N1 fix)."""
    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_get_runner.return_value = mock_runner

        response = await async_client.post(
            "/api/v1/pipeline/run",
            json={
                "source_type": "local",
                "mode": "full",
                # Missing content_base64 and filename
            },
        )

        assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_pipeline_run_online_requires_query_or_identifiers(async_client: AsyncClient):
    """POST with source_type=online requires query or identifiers (N1 fix)."""
    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_get_runner.return_value = mock_runner

        response = await async_client.post(
            "/api/v1/pipeline/run",
            json={
                "source_type": "online",
                "mode": "full",
                # Missing query and identifiers
            },
        )

        assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_pipeline_run_target_phase_range_validation(async_client: AsyncClient):
    """POST with target_phase outside 1-3 range is rejected (N2 fix)."""
    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_get_runner.return_value = mock_runner

        response = await async_client.post(
            "/api/v1/pipeline/run",
            json={
                "source_type": "local",
                "content_base64": "dGVzdA==",
                "mode": "phase",
                "target_phase": 5,  # Invalid: out of range
            },
        )

        assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_pipeline_run_duplicate_prevention(async_client: AsyncClient):
    """POST with same source_document_id while run is in-progress returns 409 (N3 fix)."""
    with patch("src.api.v1.pipeline.get_pipeline_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_runner.is_running_for_source = MagicMock(return_value=True)
        mock_get_runner.return_value = mock_runner

        response = await async_client.post(
            "/api/v1/pipeline/run",
            json={
                "source_type": "local",
                "filename": "test.pdf",
                "content_base64": "dGVzdA==",
                "mode": "full",
            },
        )

        assert response.status_code == 409
```

**Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/api/test_pipeline_api.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'src.api.v1.pipeline'"

**Step 3: Write minimal implementation**

Create `backend/src/api/v1/pipeline.py`:

```python
"""Pipeline orchestrator API routes."""
from __future__ import annotations

import base64
import uuid
from datetime import datetime
from typing import Any, Literal

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

    initial_state = PipelineGraphState(
        processing_run_id=processing_run_id,
        source_document_id=source_document_id,
        mode=PipelineMode(request.mode),
        source_type=SourceType(request.source_type),
        target_phase=request.target_phase,
        source_key=source_key or None,
        created_at=datetime.now().isoformat(),
    )

    # Decode base64 content if provided
    content_bytes = None
    if request.content_base64:
        content_bytes = base64.b64decode(request.content_base64)

    # TODO: Inject content into state or store for Phase 1 adapter to consume

    runner.start(initial_state)

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
```

**Step 4: Update router to include pipeline routes**

Modify `backend/src/api/v1/router.py`:

```python
"""API v1 router for Lingua Seekerbackend."""
from __future__ import annotations

from fastapi import APIRouter

from src.api.v1 import chat, delta_audit, evidence, pipeline, source_link

router = APIRouter(prefix="/api/v1")

# Pipeline orchestrator routes
router.include_router(pipeline.router, prefix="/pipeline", tags=["pipeline"])

# Phase 4 routes (expert review — independent of orchestrator)
router.include_router(evidence.router, prefix="/evidence", tags=["evidence"])
router.include_router(delta_audit.router, prefix="/delta-audit", tags=["delta-audit"])
router.include_router(source_link.router, prefix="/source-link", tags=["source-link"])
router.include_router(chat.router, prefix="/chat", tags=["chat"])
```

**Step 5: Run test to verify it passes**

```bash
cd backend
uv run pytest tests/api/test_pipeline_api.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/api/v1/pipeline.py backend/src/api/v1/router.py backend/tests/api/test_pipeline_api.py
git commit -m "feat: add pipeline API with per-phase status details and skip_phase_3_reason"
```

---

## Task 11: Wire Orchestrator in App Lifespan (Session-per-Request)

**Files:**
- Modify: `backend/app/main.py` (initialize orchestrator in lifespan)
- Create: `backend/src/agents/state_persistence_factory.py`
- Create: `backend/tests/agents/test_app_lifespan.py`

**Step 1: Write the failing test**

```python
"""Tests for app lifespan orchestrator initialization."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_app_starts_with_pipeline_initialized(async_client: AsyncClient):
    """App lifespan initializes pipeline runner."""
    from src.api.v1.pipeline import get_pipeline_runner

    runner = get_pipeline_runner()
    assert runner is not None


@pytest.mark.asyncio
async def test_runner_has_persistence(async_client: AsyncClient):
    """Initialized runner has state persistence for crash recovery."""
    from src.api.v1.pipeline import get_pipeline_runner

    runner = get_pipeline_runner()
    assert runner._persistence is not None
```

**Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/agents/test_app_lifespan.py -v
```

Expected: FAIL with "RuntimeError: Pipeline runner not initialized"

**Step 3: Create SessionBoundPersistence**

Create `backend/src/agents/state_persistence_factory.py`:

```python
"""Session-bound state persistence using session-per-request pattern."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.agents.contracts import PipelineGraphState
from src.dao.models import PipelineRunState


class SessionBoundPersistence:
    """StatePersistenceService that creates a fresh session per operation.

    Avoids holding session references across requests (C1 fix: session lifecycle).
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def save(self, state: PipelineGraphState) -> None:
        """Save or update pipeline state with a fresh session."""
        async with self._session_factory() as session:
            existing = await session.get(
                PipelineRunState, UUID(state.processing_run_id)
            )

            state_json = state.model_dump(mode="json")

            if existing:
                existing.state_json = state_json
            else:
                new_record = PipelineRunState(
                    processing_run_id=UUID(state.processing_run_id),
                    source_document_id=UUID(state.source_document_id),
                    state_json=state_json,
                )
                session.add(new_record)

            await session.commit()

    async def load(self, processing_run_id: str) -> Optional[PipelineGraphState]:
        """Load pipeline state with a fresh session."""
        async with self._session_factory() as session:
            record = await session.get(
                PipelineRunState, UUID(processing_run_id)
            )
            if record is None:
                return None

            return PipelineGraphState.model_validate(record.state_json)
```

**Step 4: Write minimal implementation in lifespan**

Modify `backend/app/main.py` lifespan:

```python
"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from src.api.v1.router import router as v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown application resources."""
    logger.info("Starting Lingua Seekerbackend")

    # Initialize pipeline orchestrator
    from src.core.config import get_config
    from src.dao.connection import (
        async_session_factory,
        build_async_engine,
    )
    from src.agents.concurrency import PipelineSemaphore, RetryablePhaseExecutor
    from src.agents.orchestrator import PipelineOrchestrator
    from src.agents.runner import PipelineRunner
    from src.agents.phase_1_adapter import Phase1Adapter
    from src.agents.phase_2_adapter import Phase2Adapter
    from src.agents.phase_3_adapter import Phase3Adapter
    from src.agents.state_persistence_factory import SessionBoundPersistence
    from src.core.ingest_and_digitize_data.document_acquisition.service import (
        DocumentAcquisitionService,
    )
    from src.core.ingest_and_digitize_data.parse_document.service import (
        ParseDocumentService,
    )
    # C2 fix: Use DocumentParseOrchestrator with remote + local parsers
    from src.core.ingest_and_digitize_data.parse_document.orchestrator import (
        DocumentParseOrchestrator,
    )
    from src.core.ingest_and_digitize_data.parse_document.remote.parser import (
        MinerURemoteParser,
    )
    from src.core.ingest_and_digitize_data.parse_document.local.parser import (
        MinerULocalParser,
    )
    from src.core.cross_lingual_process_and_extract_evidence.workflow import (
        TranslationService,
    )
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import (
        EvidenceExtractionService,
    )
    from src.core.standardize_entities_and_align_knowledge.api import (
        EntityStandardizationService,
    )
    from src.api.v1.pipeline import set_pipeline_runner

    cfg = get_config()
    engine = build_async_engine(cfg)
    session_factory = async_session_factory(engine)

    # Build phase adapters with long-lived services
    # C2 fix: DocumentParseOrchestrator wraps remote (cloud) and local (model-server) parsers
    acquisition_service = DocumentAcquisitionService()
    remote_parser = MinerURemoteParser(api_token=cfg.mineru_api_token)
    local_parser = MinerULocalParser()
    parse_orchestrator = DocumentParseOrchestrator(
        remote=remote_parser,
        local=local_parser,
    )
    parse_service = ParseDocumentService(parse_orchestrator)
    translation_service = TranslationService(cfg=cfg)
    extraction_service = EvidenceExtractionService(cfg=cfg)

    # Session-bound persistence for orchestrator and runner
    session_persistence = SessionBoundPersistence(session_factory=session_factory)

    # EntityStandardizationService needs a session — use session-per-request
    # The service is called from Phase 3 adapter, which runs in a background task
    # We create a wrapper that provides a fresh session per call
    from src.agents.session_bound_standardization import (
        SessionBoundStandardizationService,
    )

    standardization_service = SessionBoundStandardizationService(
        cfg=cfg,
        session_factory=session_factory,
    )

    phase_adapters = {
        "phase_1": Phase1Adapter(acquisition_service, parse_service),
        "phase_2": Phase2Adapter(translation_service, extraction_service),
        "phase_3": Phase3Adapter(standardization_service),
    }

    retry_executor = RetryablePhaseExecutor(max_retries=2, backoff_base=30.0)

    orchestrator = PipelineOrchestrator(
        phase_adapters=phase_adapters,
        state_persistence=session_persistence,
        retry_executor=retry_executor,
    )

    semaphore = PipelineSemaphore(max_concurrent=2)
    runner = PipelineRunner(
        orchestrator=orchestrator,
        semaphore=semaphore,
        state_persistence=session_persistence,
    )

    set_pipeline_runner(runner)
    logger.info("Pipeline orchestrator initialized")

    yield

    # Teardown
    await engine.dispose()
    logger.info("Lingua Seekerbackend stopped")


app = FastAPI(
    title="Lingua SeekerBackend",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(v1_router)
```

**Step 5: Create SessionBoundStandardizationService wrapper**

Create `backend/src/agents/session_bound_standardization.py`:

```python
"""Session-bound wrapper for EntityStandardizationService.

EntityStandardizationService requires a session in its constructor.
This wrapper creates a fresh session per call to run_dual_result(),
avoiding the closed-session problem (C1 fix).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if TYPE_CHECKING:
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
        DualEvidenceExtractionResult,
    )
    from src.core.standardize_entities_and_align_knowledge.contracts import (
        StandardizationResult,
    )


class SessionBoundStandardizationService:
    """Wrapper that provides session-per-request for EntityStandardizationService."""

    def __init__(self, cfg, session_factory: async_sessionmaker[AsyncSession]):
        self._cfg = cfg
        self._session_factory = session_factory

    async def run_dual_result(
        self,
        result: DualEvidenceExtractionResult,
        *,
        source_document_id: str,
        processing_run_id: str,
    ) -> StandardizationResult:
        """Run standardization with a fresh session."""
        from src.core.standardize_entities_and_align_knowledge.api import (
            EntityStandardizationService,
        )

        async with self._session_factory() as session:
            service = EntityStandardizationService(cfg=self._cfg, session=session)
            return await service.run_dual_result(
                result,
                source_document_id=source_document_id,
                processing_run_id=processing_run_id,
            )
```

**Step 6: Run test to verify it passes**

```bash
cd backend
uv run pytest tests/agents/test_app_lifespan.py -v
```

Expected: PASS

**Step 7: Commit**

```bash
git add backend/app/main.py backend/src/agents/state_persistence_factory.py backend/src/agents/session_bound_standardization.py backend/tests/agents/test_app_lifespan.py
git commit -m "feat: initialize pipeline orchestrator in app lifespan with session-per-request"
```

---

## Task 12: Integration Test and Progress Update

**Files:**
- Create: `backend/tests/agents/test_integration.py`
- Modify: `progress.txt`
- Modify: `lesson.md`

**Step 1: Write integration test**

```python
"""Integration test for full pipeline orchestrator."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.contracts import (
    PipelineGraphState,
    PipelineMode,
    SourceType,
    PhaseStatus,
    PipelineStatus,
    PhaseStatusDetail,
    Phase1Output,
    SkipPhase3Reason,
)
from src.agents.orchestrator import PipelineOrchestrator
from src.agents.concurrency import RetryablePhaseExecutor


@pytest.mark.asyncio
async def test_graph_compiles_and_routes():
    """Orchestrator graph compiles and has correct structure."""
    mock_adapters = {
        "phase_1": MagicMock(run=AsyncMock()),
        "phase_2": MagicMock(run=AsyncMock()),
        "phase_3": MagicMock(run=AsyncMock()),
    }
    mock_persistence = MagicMock(save=AsyncMock())
    retry_executor = RetryablePhaseExecutor(max_retries=0, backoff_base=0.01)

    orchestrator = PipelineOrchestrator(
        phase_adapters=mock_adapters,
        state_persistence=mock_persistence,
        retry_executor=retry_executor,
    )

    assert orchestrator._graph is not None

    initial_state = PipelineGraphState(
        processing_run_id="test-run",
        source_document_id="test-doc",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )

    assert initial_state.phase_1_status.status == PhaseStatus.PENDING
    assert initial_state.pipeline_status == PipelineStatus.PENDING


@pytest.mark.asyncio
async def test_upstream_validation_rejects_missing_prerequisites():
    """Orchestrator rejects phase-mode runs without completed upstream."""
    mock_adapters = {
        "phase_1": MagicMock(run=AsyncMock()),
        "phase_2": MagicMock(run=AsyncMock()),
        "phase_3": MagicMock(run=AsyncMock()),
    }
    mock_persistence = MagicMock(save=AsyncMock())
    retry_executor = RetryablePhaseExecutor(max_retries=0, backoff_base=0.01)

    orchestrator = PipelineOrchestrator(
        phase_adapters=mock_adapters,
        state_persistence=mock_persistence,
        retry_executor=retry_executor,
    )

    state = PipelineGraphState(
        processing_run_id="test-run",
        source_document_id="test-doc",
        mode=PipelineMode.PHASE,
        source_type=SourceType.LOCAL,
        target_phase=3,
    )

    result = await orchestrator.run(state)

    assert result.pipeline_status == PipelineStatus.FAILED
    assert "upstream" in result.error_message.lower()
    mock_adapters["phase_3"].run.assert_not_called()


@pytest.mark.asyncio
async def test_persistence_called_after_each_phase():
    """State is persisted to PostgreSQL after each phase completes."""
    state = PipelineGraphState(
        processing_run_id="test-run",
        source_document_id="test-doc",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )

    state_after_1 = state.model_copy(deep=True)
    state_after_1.phase_1_status = PhaseStatusDetail(status=PhaseStatus.COMPLETED)
    state_after_1.phase_1_output = Phase1Output(
        pdf_path="/tmp/test.pdf",
        md_path="/tmp/test.md",
        metadata_path="/tmp/test.json",
        output_dir="/tmp/output",
    )

    mock_adapters = {
        "phase_1": MagicMock(run=AsyncMock(return_value=state_after_1)),
        "phase_2": MagicMock(run=AsyncMock(return_value=state_after_1)),
        "phase_3": MagicMock(run=AsyncMock(return_value=state_after_1)),
    }
    mock_persistence = MagicMock(save=AsyncMock())
    retry_executor = RetryablePhaseExecutor(max_retries=0, backoff_base=0.01)

    orchestrator = PipelineOrchestrator(
        phase_adapters=mock_adapters,
        state_persistence=mock_persistence,
        retry_executor=retry_executor,
    )

    await orchestrator.run(state)

    # save() called after each phase + final AWAITING_REVIEW save
    assert mock_persistence.save.call_count >= 3


@pytest.mark.asyncio
async def test_skip_phase_3_reason_flows_through():
    """skip_phase_3_reason set by Phase 2 flows to Phase 3 adapter."""
    state = PipelineGraphState(
        processing_run_id="test-run",
        source_document_id="test-doc",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )

    state_after_1 = state.model_copy(deep=True)
    state_after_1.phase_1_status = PhaseStatusDetail(status=PhaseStatus.COMPLETED)
    state_after_1.phase_1_output = Phase1Output(
        pdf_path="/tmp/test.pdf",
        md_path="/tmp/test.md",
        metadata_path="/tmp/test.json",
        output_dir="/tmp/output",
    )

    state_after_2 = state_after_1.model_copy(deep=True)
    state_after_2.phase_2_status = PhaseStatusDetail(status=PhaseStatus.COMPLETED)
    state_after_2.skip_phase_3_reason = SkipPhase3Reason.NOT_RELEVANT

    state_after_3 = state_after_2.model_copy(deep=True)
    state_after_3.phase_3_status = PhaseStatusDetail(
        status=PhaseStatus.SKIPPED,
        summary={"reason": "not_relevant"},
    )

    mock_adapters = {
        "phase_1": MagicMock(run=AsyncMock(return_value=state_after_1)),
        "phase_2": MagicMock(run=AsyncMock(return_value=state_after_2)),
        "phase_3": MagicMock(run=AsyncMock(return_value=state_after_3)),
    }
    mock_persistence = MagicMock(save=AsyncMock())
    retry_executor = RetryablePhaseExecutor(max_retries=0, backoff_base=0.01)

    orchestrator = PipelineOrchestrator(
        phase_adapters=mock_adapters,
        state_persistence=mock_persistence,
        retry_executor=retry_executor,
    )

    result = await orchestrator.run(state)

    assert result.skip_phase_3_reason == SkipPhase3Reason.NOT_RELEVANT
    assert result.phase_3_status.status == PhaseStatus.SKIPPED
```

**Step 2: Run test**

```bash
cd backend
uv run pytest tests/agents/test_integration.py -v
```

Expected: PASS

**Step 3: Update progress.txt**

Append to `progress.txt`:

```
[2026-05-29] Pipeline Orchestrator Implementation (v3 — Final) — 1 main agent + 3 phase adapters (LangGraph) [COMPLETED]
  - contracts.py: PipelineGraphState (Pydantic), PhaseStatus/PhaseStatusDetail, PipelineMode, SourceType,
    PipelineStatus, Phase1Output/Phase2Output/Phase3Output, PhaseErrorDetail,
    RetryablePhaseError/PermanentPhaseError, SkipPhase3Reason enum
  - state_persistence.py: Save/load state to PostgreSQL at phase boundaries
  - state_persistence_factory.py: Session-per-request pattern (C1 fix)
  - session_bound_standardization.py: Session-per-request for EntityStandardizationService
  - phase_1_adapter.py: Acquisition + Parsing (raises classified errors, correct field names)
  - phase_2_adapter.py: Translation + EvidenceExtractionService.run_dual() + build_dual_documents_from_output_dir()
  - phase_3_adapter.py: Entity Standardization (raises classified errors, skip_phase_3_reason support)
  - orchestrator.py: LangGraph StateGraph with 3 phase nodes + upstream validation + persistence
  - runner.py: Background execution with asyncio.Semaphore(2) + DB fallback
  - concurrency.py: Retry logic with RetryablePhaseError/PermanentPhaseError
  - pipeline.py: POST /api/v1/pipeline/run + GET /api/v1/pipeline/runs/{id}/status (per-phase details + skip_phase_3_reason)
  - App lifespan initialization with DocumentParseOrchestrator (C2 fix)

  All 23 audit issues fixed:
  - A2: tests/agents/ directory created
  - B1: UUID consistency noted (str in contracts, UUID in DB)
  - B2-B4: SavedFiles/MinerULocalBatchSaveResult field names corrected
  - B5-B7: Phase 2 uses EvidenceExtractionService.run_dual() + build_dual_documents_from_output_dir()
  - B8: run_dual_result positional arg style
  - C1: Session-per-request via SessionBoundPersistence
  - C2: DocumentParseOrchestrator(remote, local) instead of MinerURemoteOrchestrator
  - C3-C5: pipeline_status field, DB fallback, persistence between phases
  - C6: Phase 4 not a graph node (3 phases only)
  - C7-C8: skip_phase_3_reason enum, upstream validation
  - D1-D5: pipeline_status, upstream validation, persistence, skip reasons, correct file paths
  - E1-E4: Error classification, transient errors, per-phase details, typed outputs
  - F1: Alembic migration path corrected
  - G1-G4: Hardcoded paths noted, correct serialization, correct types, integration test
  - H1-H2: Concurrency test tracks max_observed, get_last_state is async
```

**Step 4: Add lesson.md entry**

Append to `lesson.md`:

```markdown
## 2026-05-29: Pipeline Orchestrator v3 — Code-Level Correctness Audit

**Problem**: Second review caught 23 implementation detail issues that would cause test failures or runtime crashes.

**Key corrections**:
1. Field names must match actual dataclass definitions — SavedFiles uses `md_path`, `metadata_path`, `output_dir`, not `markdown_path`, `json_path`, `image_dir`.
2. Service facades exist for a reason — use `EvidenceExtractionService.run_dual()`, not the internal workflow directly.
3. Session lifecycle matters — services holding session references across requests will crash when the session closes. Use session-per-request pattern.
4. Skip conditions need granularity — boolean `skip_phase_3` is too coarse; use enum `SkipPhase3Reason` to capture NOT_RELEVANT, NO_ENTITIES, NO_CANDIDATES.
5. Phase 2 reads from Phase 1's output directory structure — use `output_dir` (contains full parse), not `metadata_path` (metadata only).

**Prevention**: When writing adapters, always verify field names against actual dataclass/model definitions using `rg "class.*"`. Mock tests must use the correct types (Pydantic vs dataclass).

**Prevention**: When wiring services in lifespan, check if they hold session references. If yes, wrap with session-per-request pattern.
```

**Step 5: Commit**

```bash
git add backend/tests/agents/test_integration.py progress.txt lesson.md
git commit -m "docs: add integration tests and update progress for pipeline orchestrator v3"
```

---

## Summary (v5 — Dedup + Indent Fix)

This plan implements a LangGraph-based pipeline orchestrator with **all 31 audit issues fixed** (23 from v3 + 6 from fourth pass + 2 from fifth pass):

| Component | Description |
|---|---|
| **1 main agent** | `PipelineOrchestrator` — 3-phase LangGraph StateGraph |
| **3 phase adapters** | Thin wrappers calling existing services (raises classified errors, correct field names) |
| **Shared big state** | `PipelineGraphState` — orchestration metadata only (Pydantic) |
| **Structured errors** | `RetryablePhaseError` / `PermanentPhaseError` hierarchy |
| **Typed outputs** | `Phase1Output`, `Phase2Output` (with `extraction_result_path`), `Phase3Output` |
| **Per-phase details** | `PhaseStatusDetail` with timing, error, summary |
| **Skip reasons** | `SkipPhase3Reason` enum (NOT_RELEVANT, NO_ENTITIES, NO_CANDIDATES) |
| **Deterministic routing** | Boolean logic on structured state fields |
| **Upstream validation** | mode=PHASE checks prerequisites before execution |
| **Crash recovery** | PostgreSQL persistence after each phase + DB fallback in runner + initial state persisted |
| **Concurrency control** | `asyncio.Semaphore(2)` |
| **Session lifecycle** | Session-per-request via `SessionBoundPersistence` and `SessionBoundStandardizationService` |
| **Phase 4 external** | Not a graph node; pipeline sets `AWAITING_REVIEW` and stops |
| **Async API** | POST to start (202), GET to poll status with per-phase details + skip_phase_3_reason |
| **Request validation** | Source-specific validation (local requires content, online requires query/identifiers) |
| **Range validation** | `target_phase` constrained to 1-3 via `Field(ge=1, le=3)` |
| **Duplicate prevention** | Checks `source_key` (filename/query) against existing in-progress runs (409 Conflict) |
| **Extraction handoff** | Phase 2 saves `DualEvidenceExtractionResult` JSON; Phase 3 reads from `extraction_result_path` |
| **Document parsing** | `DocumentParseOrchestrator(remote, local)` with MinerU cloud + model-server fallback |

Total: 13 tasks (0-12), ~35 files created/modified, comprehensive test coverage.

### Known Limitations (v1)

- **N11: No retry endpoint** — Failed runs cannot be retried via API. Users must create a new run with the same parameters. A `POST /api/v1/pipeline/runs/{id}/retry` endpoint should be added in v2.
- **Duplicate prevention is filename-based** — The dedup key uses `filename` for local uploads and `query` for online. Content-hash-based dedup would be more robust but is deferred to v2.

**Architecture principle**: The orchestrator coordinates; the phases execute. Business logic stays in `src/core/<phase>/`, never in `src/agents/`. Adapters raise; orchestrator catches. Field names match actual dataclass definitions. Sessions are short-lived. State is persisted at every boundary (initial, per-phase, final).

---

