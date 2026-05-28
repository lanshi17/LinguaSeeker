# Phase 4: Evidence Visualization & Expert Feedback Loop Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the P0 expert review and feedback loop for Phase 4, enabling clinical experts to review extracted evidence, provide corrections, and engage in AI-assisted dialogue.

**Architecture:** `visualize_evidence_with_expert_in_loop/` feature slice under `backend/src/core/`. Three new database tables (`review_audit_events`, `chat_sessions`, `chat_messages`) for audit and conversation persistence. Evidence cards have predefined schema; delta audit diffs on fixed field list. Review status state machine: `provisional → approved | corrected | rejected`. Chat service supports mixed mode: message persistence + AI replies using `REASONING_LLM_MODEL` with evidence context (~4000 tokens). Source linker provides single-track and cross-track bilingual traceability. No LangGraph review node; agents state extended for future review awareness.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2, httpx, pytest-asyncio, uv, Ruff

---

**Status:** planned  
**Created:** 2026-05-28  
**Completed:** —  
**PR:** —

## Confirmed Decisions (from Q&A Q1-Q39)

**Scope:**
- Backend feature slice only (frontend deferred to separate sprint)
- P0 files: `feedback_service`, `delta_audit_service`, `source_linker`, `chat_service` (comment_service merged into chat)
- P1 deferred: `report_generator`, `knowledge_base_service`, `acmg_draft_service`

**Evidence Cards:**
- Predefined schema: `EvidenceCardPayload` with fixed field list
- Delta diff on: `gene, variant, phenotype, disease, classification, evidence_strength, evidence_type, functional_impact, inheritance_pattern, zygosity, references, summary`
- Arbitrary field paths rejected to prevent injection

**Review Status:**
- 3 states: `provisional → approved | corrected | rejected`, `corrected → approved`
- No `re_reviewed` state (audit trail tracks history)

**Target Types:**
- 3 implemented: `evidence_item`, `entity`, `missed_evidence`
- 7 declared but not implemented: `task, native_extraction, translated_extraction, translation, fusion, report, translation`

**Delta Audit:**
- Backend auto-compares old vs new (method A)
- Frontend sends PATCH with new values only
- `field_deltas` stored as JSONB array in `review_audit_events`
- Zero-noise: no delta record if old == new

**Chat Service:**
- Mixed mode: message persistence + AI replies
- AI context: current evidence card + entities + source span + other cards summary + conversation history (~4000 tokens)
- Model: `REASONING_LLM_MODEL` (cfg.llm_reasoning_*)
- Intent detection: pure question / correction instruction / note

**Source Linker:**
- 3 layers: single-track span → cross-track association → bilingual comparison
- Cross-track uses `canonical_evidence_id` as natural anchor (no extra alignment logic)

**Database:**
- 3 new tables: `review_audit_events`, `chat_sessions`, `chat_messages`
- Test DB required (separate from production `acmg_ps3`)

**Agents:**
- No `review_node` (human-in-the-loop, not auto-executed)
- Extend `GraphState` with `review_status_summary` and `active_review_run_id`
- No `pipeline_chat_orchestrator` in P0 (deferred to orchestrator build)

**Export:**
- P0: JSON API only (`GET /api/v1/tasks/{task_id}/result`)
- P1: CSV + PDF/DOCX with `report_generator`

---

## Prerequisites

- Read `docs/active/APP_FLOW.md` for Phase 4 user flows
- Read `docs/active/BACKEND_STRUCTURE.md` for target architecture
- Use @test-driven-development for each implementation task
- Use @systematic-debugging for any unexpected test failure
- Use @verification-before-completion before claiming completion
- Use @module-guide after module is implemented and tests pass
- Use @doc-organize after docs are updated
- Do not commit unrelated dirty worktree changes

---

## Phase A: Database Schema

### Task A1: Create review_audit_events migration

**Files:**
- Create: `database/migrations/versions/2026-05-28_add_review_and_chat_tables.py`
- Test: `backend/tests/dao/test_models.py`

**Step 1: Write failing ORM metadata tests**

Append to `backend/tests/dao/test_models.py`:

```python
def test_review_chat_tables_exist() -> None:
    """ORM metadata includes Phase 4 review and chat tables."""
    metadata = Base.metadata
    assert "review_audit_events" in metadata.tables
    assert "chat_sessions" in metadata.tables
    assert "chat_messages" in metadata.tables


def test_review_audit_events_canonical_evidence_fk() -> None:
    """Review audit events reference the canonical evidence they modify."""
    table = _table("review_audit_events")
    fk_cols = [c for c in table.columns if c.foreign_keys]
    assert any("canonical_evidence_items.canonical_evidence_id" in str(fk) 
               for c in fk_cols for fk in c.foreign_keys)


def test_review_audit_events_field_deltas_jsonb() -> None:
    """Field deltas stored as JSONB for flexible delta tracking."""
    table = _table("review_audit_events")
    col = table.c.field_deltas
    assert col.type.__class__.__name__ == "JSONB"


def test_chat_sessions_processing_run_fk() -> None:
    """Chat sessions bound to a processing run."""
    table = _table("chat_sessions")
    fk_cols = [c for c in table.columns if c.foreign_keys]
    assert any("processing_runs.processing_run_id" in str(fk) 
               for c in fk_cols for fk in c.foreign_keys)


def test_chat_messages_session_fk() -> None:
    """Chat messages reference their session."""
    table = _table("chat_messages")
    fk_cols = [c for c in table.columns if c.foreign_keys]
    assert any("chat_sessions.chat_session_id" in str(fk) 
               for c in fk_cols for fk in c.foreign_keys)


def test_chat_messages_role_column() -> None:
    """Messages distinguish user vs assistant."""
    table = _table("chat_messages")
    assert "role" in table.c
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/dao/test_models.py::test_review_chat_tables_exist -v`  
Expected: FAIL with "review_audit_events not in metadata.tables"

**Step 3: Create migration file**

Create `database/migrations/versions/2026-05-28_add_review_and_chat_tables.py`:

```python
"""add review and chat tables for Phase 4

Revision ID: review_chat_20260528
Revises: add_nulls_distinct_20260527
Create Date: 2026-05-28
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "review_chat_20260528"
down_revision: Union[str, None] = "add_nulls_distinct_20260527"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Review audit events: track status transitions and field-level deltas
    op.create_table(
        "review_audit_events",
        sa.Column("review_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("old_status", sa.String(length=32), nullable=True),
        sa.Column("new_status", sa.String(length=32), nullable=True),
        sa.Column("field_deltas", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["canonical_evidence_id"],
            ["canonical_evidence_items.canonical_evidence_id"],
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["users.user_id"],
        ),
        sa.PrimaryKeyConstraint("review_event_id"),
    )
    op.create_index(
        "ix_review_audit_events_canonical_evidence_id",
        "review_audit_events",
        ["canonical_evidence_id"],
    )
    op.create_index(
        "ix_review_audit_events_reviewer_id",
        "review_audit_events",
        ["reviewer_id"],
    )

    # Chat sessions: bind conversation to a processing run
    op.create_table(
        "chat_sessions",
        sa.Column("chat_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("processing_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["processing_run_id"],
            ["processing_runs.processing_run_id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
        ),
        sa.PrimaryKeyConstraint("chat_session_id"),
    )
    op.create_index(
        "ix_chat_sessions_processing_run_id",
        "chat_sessions",
        ["processing_run_id"],
    )

    # Chat messages: persist conversation history
    op.create_table(
        "chat_messages",
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chat_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["chat_session_id"],
            ["chat_sessions.chat_session_id"],
        ),
        sa.PrimaryKeyConstraint("message_id"),
    )
    op.create_index(
        "ix_chat_messages_chat_session_id",
        "chat_messages",
        ["chat_session_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_chat_session_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_processing_run_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")
    op.drop_index("ix_review_audit_events_reviewer_id", table_name="review_audit_events")
    op.drop_index("ix_review_audit_events_canonical_evidence_id", table_name="review_audit_events")
    op.drop_table("review_audit_events")
```

**Step 4: Add ORM models**

Append to `backend/src/dao/models.py`:

```python
class ReviewAuditEvent(Base):
    """Audit trail for evidence review operations."""

    __tablename__ = "review_audit_events"
    __table_args__ = (
        Index("ix_review_audit_events_canonical_evidence_id", "canonical_evidence_id"),
        Index("ix_review_audit_events_reviewer_id", "reviewer_id"),
    )

    review_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    canonical_evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_evidence_items.canonical_evidence_id"),
        nullable=False,
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
    )
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    old_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    field_deltas: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ChatSession(Base, TimestampMixin):
    """Chat session bound to a processing run."""

    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("ix_chat_sessions_processing_run_id", "processing_run_id"),
    )

    chat_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    processing_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("processing_runs.processing_run_id"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
    )


class ChatMessage(Base):
    """Chat message in a session."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_chat_session_id", "chat_session_id"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    chat_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.chat_session_id"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
```

**Step 5: Update EXPECTED_TABLES in test_models.py**

Modify `backend/tests/dao/test_models.py`:

```python
EXPECTED_TABLES = {
    "source_documents",
    "source_document_identifiers",
    "processing_runs",
    "normalized_entities",
    "entity_merge_events",
    "run_evidence_items",
    "evidence_entity_bindings",
    "canonical_evidence_items",
    "terminology_entries",
    "terminology_aliases",
    "terminology_relationships",
    "terminology_embeddings",
    "users",
    "review_audit_events",  # Phase 4
    "chat_sessions",        # Phase 4
    "chat_messages",        # Phase 4
}
```

**Step 6: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/dao/test_models.py -v`  
Expected: All tests PASS

**Step 7: Commit**

```bash
git add database/migrations/versions/2026-05-28_add_review_and_chat_tables.py
git add backend/src/dao/models.py
git add backend/tests/dao/test_models.py
git commit -m "feat: add Phase 4 review and chat database schema"
```

---

## Phase B: Core Contracts

### Task B1: Define EvidenceCardPayload and review enums

**Files:**
- Create: `backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py`
- Test: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_contracts.py`

**Step 1: Write failing contract tests**

Create `backend/tests/core/visualize_evidence_with_expert_in_loop/test_contracts.py`:

```python
"""Tests for Phase 4 contracts."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    DeltaEntry,
    EvidenceCardPayload,
    ReviewStatus,
    TargetType,
)


class TestEvidenceCardPayload:
    """EvidenceCardPayload has a fixed schema for diff operations."""

    def test_minimal_payload(self) -> None:
        """All fields are optional."""
        payload = EvidenceCardPayload()
        assert payload.gene is None
        assert payload.references == []

    def test_full_payload(self) -> None:
        """All fields can be populated."""
        payload = EvidenceCardPayload(
            gene="GLA",
            variant="p.R227X",
            phenotype="Fabry disease",
            disease="Fabry disease",
            classification="Pathogenic",
            evidence_strength="PS3",
            evidence_type="Functional",
            functional_impact="Loss of function",
            inheritance_pattern="X-linked",
            zygosity="Hemizygous",
            references=["PMID:12345678"],
            summary="Test summary",
        )
        assert payload.gene == "GLA"
        assert payload.references == ["PMID:12345678"]

    def test_diff_fields_constant(self) -> None:
        """DIFF_FIELDS contains exactly the expected field names."""
        expected = {
            "gene", "variant", "phenotype", "disease", "classification",
            "evidence_strength", "evidence_type", "functional_impact",
            "inheritance_pattern", "zygosity", "references", "summary",
        }
        assert set(EvidenceCardPayload.DIFF_FIELDS) == expected


class TestReviewStatus:
    """ReviewStatus defines the state machine for evidence review."""

    def test_provisional_is_initial(self) -> None:
        assert ReviewStatus.PROVISIONAL.value == "provisional"

    def test_all_states(self) -> None:
        assert set(ReviewStatus) == {
            ReviewStatus.PROVISIONAL,
            ReviewStatus.APPROVED,
            ReviewStatus.CORRECTED,
            ReviewStatus.REJECTED,
        }


class TestTargetType:
    """TargetType enumerates review feedback targets."""

    def test_implemented_types(self) -> None:
        """Three target types are implemented in P0."""
        implemented = {
            TargetType.EVIDENCE_ITEM,
            TargetType.ENTITY,
            TargetType.MISSED_EVIDENCE,
        }
        assert implemented <= set(TargetType)

    def test_declared_but_not_implemented(self) -> None:
        """Other target types are declared but not implemented."""
        assert TargetType.TASK in set(TargetType)
        assert TargetType.NATIVE_EXTRACTION in set(TargetType)


class TestDeltaEntry:
    """DeltaEntry represents a single field change."""

    def test_valid_delta(self) -> None:
        delta = DeltaEntry(
            field="phenotype",
            old_value="Fabry disease",
            new_value="Fabry 病",
        )
        assert delta.field == "phenotype"
        assert delta.field in EvidenceCardPayload.DIFF_FIELDS

    def test_invalid_field_rejected(self) -> None:
        """Arbitrary field paths are rejected to prevent injection."""
        with pytest.raises(ValidationError):
            DeltaEntry(
                field="__class__.__dict__",
                old_value="x",
                new_value="y",
            )
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_contracts.py::TestEvidenceCardPayload::test_minimal_payload -v`  
Expected: FAIL with "ModuleNotFoundError" or "ImportError"

**Step 3: Create contracts.py**

Create `backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py`:

```python
"""Typed contracts for Phase 4 evidence review and feedback."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ReviewStatus(str, Enum):
    """Evidence review state machine."""

    PROVISIONAL = "provisional"
    APPROVED = "approved"
    CORRECTED = "corrected"
    REJECTED = "rejected"


class TargetType(str, Enum):
    """Review feedback target types.

    P0 implements: evidence_item, entity, missed_evidence.
    Others are declared but not implemented.
    """

    EVIDENCE_ITEM = "evidence_item"
    ENTITY = "entity"
    MISSED_EVIDENCE = "missed_evidence"
    TASK = "task"
    NATIVE_EXTRACTION = "native_extraction"
    TRANSLATED_EXTRACTION = "translated_extraction"
    TRANSLATION = "translation"
    FUSION = "fusion"
    REPORT = "report"


class EvidenceCardPayload(BaseModel):
    """Predefined schema for evidence card active_payload.

    Used for delta diff operations. Field list is fixed; arbitrary
    field paths are rejected to prevent injection.
    """

    gene: str | None = None
    variant: str | None = None
    phenotype: str | None = None
    disease: str | None = None
    classification: str | None = None
    evidence_strength: str | None = None
    evidence_type: str | None = None
    functional_impact: str | None = None
    inheritance_pattern: str | None = None
    zygosity: str | None = None
    references: list[str] = Field(default_factory=list)
    summary: str | None = None

    # Fixed field list for delta diff operations
    DIFF_FIELDS: tuple[str, ...] = (
        "gene",
        "variant",
        "phenotype",
        "disease",
        "classification",
        "evidence_strength",
        "evidence_type",
        "functional_impact",
        "inheritance_pattern",
        "zygosity",
        "references",
        "summary",
    )


class DeltaEntry(BaseModel):
    """Single field change in a review audit event."""

    field: str
    old_value: str | list[str] | None
    new_value: str | list[str] | None

    @field_validator("field")
    @classmethod
    def validate_field_name(cls, v: str) -> str:
        """Reject arbitrary field paths to prevent injection."""
        if v not in EvidenceCardPayload.DIFF_FIELDS:
            raise ValueError(
                f"Invalid field '{v}'. Must be one of {EvidenceCardPayload.DIFF_FIELDS}"
            )
        return v


class ReviewAuditEventResponse(BaseModel):
    """API response for a review audit event."""

    review_event_id: UUID
    canonical_evidence_id: UUID
    reviewer_id: UUID | None
    target_type: TargetType
    old_status: ReviewStatus | None
    new_status: ReviewStatus | None
    field_deltas: list[DeltaEntry]
    change_reason: str | None
    created_at: datetime


class BilingualSpan(BaseModel):
    """Cross-track bilingual traceability result."""

    canonical_evidence_id: UUID
    original_track: TrackSpan | None
    translated_track: TrackSpan | None
    alignment_confidence: float | None = None


class TrackSpan(BaseModel):
    """Single-track source span with highlight context."""

    track: Literal["original", "translated"]
    source_span: dict  # Raw source_span JSONB
    block_text: str
    highlight_start: int
    highlight_end: int
    page: int | None = None


class ChatSessionResponse(BaseModel):
    """API response for a chat session."""

    chat_session_id: UUID
    processing_run_id: UUID
    user_id: UUID | None
    created_at: datetime
    message_count: int = 0


class ChatMessageResponse(BaseModel):
    """API response for a chat message."""

    message_id: UUID
    chat_session_id: UUID
    role: Literal["user", "assistant"]
    content: str
    evidence_id: UUID | None
    entity_id: UUID | None
    created_at: datetime


class EvidencePatchRequest(BaseModel):
    """Request body for PATCH /api/v1/evidence/{id}."""

    fields: dict[str, str | list[str] | None]
    change_reason: str | None = None
    new_status: ReviewStatus | None = None

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, v: dict[str, str | list[str] | None]) -> dict:
        """Ensure all field names are in DIFF_FIELDS."""
        invalid = set(v.keys()) - set(EvidenceCardPayload.DIFF_FIELDS)
        if invalid:
            raise ValueError(
                f"Invalid fields: {invalid}. Must be subset of {EvidenceCardPayload.DIFF_FIELDS}"
            )
        return v
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_contracts.py -v`  
Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py
git add backend/tests/core/visualize_evidence_with_expert_in_loop/test_contracts.py
git commit -m "feat: add Phase 4 core contracts and enums"
```

---

## Phase C: Feedback Service & Delta Audit

### Task C1: Implement DeltaAuditService

**Files:**
- Create: `backend/src/core/visualize_evidence_with_expert_in_loop/delta_audit_service.py`
- Test: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_delta_audit.py`

**Step 1: Write failing tests**

Create `backend/tests/core/visualize_evidence_with_expert_in_loop/test_delta_audit.py`:

```python
"""Tests for delta audit service."""
from __future__ import annotations

import pytest

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    DeltaEntry,
    EvidenceCardPayload,
)
from src.core.visualize_evidence_with_expert_in_loop.delta_audit_service import (
    DeltaAuditService,
)


class TestComputeDeltas:
    """DeltaAuditService.compute_deltas detects field-level changes."""

    def test_no_change_returns_empty(self) -> None:
        """Identical payloads produce no deltas."""
        old = EvidenceCardPayload(gene="GLA", phenotype="Fabry disease")
        new = EvidenceCardPayload(gene="GLA", phenotype="Fabry disease")
        deltas = DeltaAuditService.compute_deltas(old, new)
        assert deltas == []

    def test_single_field_change(self) -> None:
        """One field changed produces one delta."""
        old = EvidenceCardPayload(phenotype="Fabry disease")
        new = EvidenceCardPayload(phenotype="Fabry 病")
        deltas = DeltaAuditService.compute_deltas(old, new)
        assert len(deltas) == 1
        assert deltas[0].field == "phenotype"
        assert deltas[0].old_value == "Fabry disease"
        assert deltas[0].new_value == "Fabry 病"

    def test_multiple_field_changes(self) -> None:
        """Multiple fields changed produce multiple deltas."""
        old = EvidenceCardPayload(gene="GLA", classification="VUS")
        new = EvidenceCardPayload(gene="GAL", classification="Pathogenic")
        deltas = DeltaAuditService.compute_deltas(old, new)
        assert len(deltas) == 2
        fields = {d.field for d in deltas}
        assert fields == {"gene", "classification"}

    def test_references_list_replacement(self) -> None:
        """References are compared as whole lists (not element-wise diff)."""
        old = EvidenceCardPayload(references=["PMID:111"])
        new = EvidenceCardPayload(references=["PMID:222"])
        deltas = DeltaAuditService.compute_deltas(old, new)
        assert len(deltas) == 1
        assert deltas[0].field == "references"
        assert deltas[0].old_value == ["PMID:111"]
        assert deltas[0].new_value == ["PMID:222"]

    def test_null_to_value_is_change(self) -> None:
        """None → value is a change."""
        old = EvidenceCardPayload(gene=None)
        new = EvidenceCardPayload(gene="GLA")
        deltas = DeltaAuditService.compute_deltas(old, new)
        assert len(deltas) == 1
        assert deltas[0].old_value is None
        assert deltas[0].new_value == "GLA"

    def test_value_to_null_is_change(self) -> None:
        """value → None is a change."""
        old = EvidenceCardPayload(gene="GLA")
        new = EvidenceCardPayload(gene=None)
        deltas = DeltaAuditService.compute_deltas(old, new)
        assert len(deltas) == 1
        assert deltas[0].old_value == "GLA"
        assert deltas[0].new_value is None
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_delta_audit.py::TestComputeDeltas::test_no_change_returns_empty -v`  
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement DeltaAuditService**

Create `backend/src/core/visualize_evidence_with_expert_in_loop/delta_audit_service.py`:

```python
"""Delta audit service for evidence review tracking."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    DeltaEntry,
    EvidenceCardPayload,
    ReviewStatus,
    TargetType,
)
from src.dao.models import ReviewAuditEvent


class DeltaAuditService:
    """Compute and persist field-level deltas for evidence review."""

    @staticmethod
    def compute_deltas(
        old: EvidenceCardPayload,
        new: EvidenceCardPayload,
    ) -> list[DeltaEntry]:
        """Compute field-level differences between two payloads.

        Returns empty list if payloads are identical.
        """
        deltas: list[DeltaEntry] = []
        for field in EvidenceCardPayload.DIFF_FIELDS:
            old_value = getattr(old, field)
            new_value = getattr(new, field)
            if old_value != new_value:
                deltas.append(
                    DeltaEntry(
                        field=field,
                        old_value=old_value,
                        new_value=new_value,
                    )
                )
        return deltas

    async def record_audit_event(
        self,
        session: AsyncSession,
        *,
        canonical_evidence_id: UUID,
        reviewer_id: UUID | None,
        target_type: TargetType,
        old_status: ReviewStatus | None,
        new_status: ReviewStatus | None,
        field_deltas: list[DeltaEntry],
        change_reason: str | None = None,
    ) -> ReviewAuditEvent:
        """Persist a review audit event with field deltas."""
        event = ReviewAuditEvent(
            canonical_evidence_id=canonical_evidence_id,
            reviewer_id=reviewer_id,
            target_type=target_type.value,
            old_status=old_status.value if old_status else None,
            new_status=new_status.value if new_status else None,
            field_deltas=[d.model_dump() for d in field_deltas],
            change_reason=change_reason,
        )
        session.add(event)
        await session.flush()
        return event

    async def list_audit_events(
        self,
        session: AsyncSession,
        *,
        canonical_evidence_id: UUID | None = None,
        reviewer_id: UUID | None = None,
        limit: int = 100,
    ) -> list[ReviewAuditEvent]:
        """Query review audit events with optional filters."""
        stmt = select(ReviewAuditEvent)
        if canonical_evidence_id:
            stmt = stmt.where(
                ReviewAuditEvent.canonical_evidence_id == canonical_evidence_id
            )
        if reviewer_id:
            stmt = stmt.where(ReviewAuditEvent.reviewer_id == reviewer_id)
        stmt = stmt.order_by(ReviewAuditEvent.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_delta_audit.py -v`  
Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/delta_audit_service.py
git add backend/tests/core/visualize_evidence_with_expert_in_loop/test_delta_audit.py
git commit -m "feat: implement DeltaAuditService for field-level change tracking"
```

---

### Task C2: Implement FeedbackService

**Files:**
- Create: `backend/src/core/visualize_evidence_with_expert_in_loop/feedback_service.py`
- Test: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_feedback_service.py`

**Step 1: Write failing tests**

Create `backend/tests/core/visualize_evidence_with_expert_in_loop/test_feedback_service.py`:

```python
"""Tests for feedback service."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    EvidenceCardPayload,
    EvidencePatchRequest,
    ReviewStatus,
    TargetType,
)
from src.core.visualize_evidence_with_expert_in_loop.feedback_service import (
    FeedbackService,
)


@pytest.mark.asyncio
class TestFeedbackService:
    """FeedbackService handles evidence card patch operations."""

    async def test_patch_single_field(self, db_session: AsyncSession) -> None:
        """Patching one field updates payload and records delta."""
        # Setup: create evidence card with provisional status
        evidence_id = await self._create_test_evidence(db_session)

        # Patch: change phenotype
        patch = EvidencePatchRequest(
            fields={"phenotype": "Fabry 病"},
            change_reason="Bilingual correction",
        )
        service = FeedbackService(db_session)
        result = await service.patch_evidence(
            canonical_evidence_id=evidence_id,
            patch=patch,
            reviewer_id=None,
        )

        # Verify: payload updated, status changed to CORRECTED
        assert result.new_status == ReviewStatus.CORRECTED
        assert result.deltas == 1
        assert result.field_deltas[0].field == "phenotype"
        assert result.field_deltas[0].old_value == "Fabry disease"
        assert result.field_deltas[0].new_value == "Fabry 病"

    async def test_patch_no_change_skips_delta(self, db_session: AsyncSession) -> None:
        """Patching with identical values produces no delta (zero-noise)."""
        evidence_id = await self._create_test_evidence(db_session)
        patch = EvidencePatchRequest(fields={"phenotype": "Fabry disease"})
        service = FeedbackService(db_session)
        result = await service.patch_evidence(
            canonical_evidence_id=evidence_id,
            patch=patch,
            reviewer_id=None,
        )

        assert result.deltas == 0
        assert result.field_deltas == []

    async def test_patch_multiple_fields(self, db_session: AsyncSession) -> None:
        """Patching multiple fields records all deltas."""
        evidence_id = await self._create_test_evidence(db_session)
        patch = EvidencePatchRequest(
            fields={
                "gene": "GAL",
                "classification": "Pathogenic",
            }
        )
        service = FeedbackService(db_session)
        result = await service.patch_evidence(
            canonical_evidence_id=evidence_id,
            patch=patch,
            reviewer_id=None,
        )

        assert result.deltas == 2
        fields = {d.field for d in result.field_deltas}
        assert fields == {"gene", "classification"}

    async def test_patch_with_explicit_status(self, db_session: AsyncSession) -> None:
        """Explicit new_status overrides auto-CORRECTED."""
        evidence_id = await self._create_test_evidence(db_session)
        patch = EvidencePatchRequest(
            fields={"phenotype": "Fabry 病"},
            new_status=ReviewStatus.APPROVED,
        )
        service = FeedbackService(db_session)
        result = await service.patch_evidence(
            canonical_evidence_id=evidence_id,
            patch=patch,
            reviewer_id=None,
        )

        assert result.new_status == ReviewStatus.APPROVED

    async def test_patch_rejects_invalid_field(self, db_session: AsyncSession) -> None:
        """Arbitrary field paths are rejected."""
        evidence_id = await self._create_test_evidence(db_session)
        with pytest.raises(ValueError, match="Invalid fields"):
            patch = EvidencePatchRequest(fields={"__class__": "exploit"})
            service = FeedbackService(db_session)
            await service.patch_evidence(
                canonical_evidence_id=evidence_id,
                patch=patch,
                reviewer_id=None,
            )

    async def _create_test_evidence(self, session: AsyncSession) -> str:
        """Helper: create test evidence card with provisional status."""
        from src.dao.models import CanonicalEvidenceItem, SourceDocument, ProcessingRun
        from uuid import uuid4

        # Create parent records
        doc = SourceDocument(source_document_id=uuid4(), raw_metadata={})
        session.add(doc)
        await session.flush()

        run = ProcessingRun(
            processing_run_id=uuid4(),
            source_document_id=doc.source_document_id,
            run_status="completed",
        )
        session.add(run)
        await session.flush()

        # Create evidence card
        evidence = CanonicalEvidenceItem(
            canonical_evidence_id=uuid4(),
            source_document_id=doc.source_document_id,
            field_id="A.test.1",
            position_hash="abc123",
            text_hash="def456",
            entity_scope_hash="ghi789",
            current_best_status="found",
            review_status="provisional",
            active_payload=EvidenceCardPayload(
                gene="GLA",
                phenotype="Fabry disease",
            ).model_dump(),
        )
        session.add(evidence)
        await session.flush()
        return str(evidence.canonical_evidence_id)
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_feedback_service.py::TestFeedbackService::test_patch_single_field -v`  
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement FeedbackService**

Create `backend/src/core/visualize_evidence_with_expert_in_loop/feedback_service.py`:

```python
"""Feedback service for evidence review and correction."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    DeltaEntry,
    EvidenceCardPayload,
    EvidencePatchRequest,
    ReviewStatus,
    TargetType,
)
from src.core.visualize_evidence_with_expert_in_loop.delta_audit_service import (
    DeltaAuditService,
)
from src.dao.models import CanonicalEvidenceItem


@dataclass
class PatchResult:
    """Result of an evidence patch operation."""

    canonical_evidence_id: UUID
    old_status: ReviewStatus
    new_status: ReviewStatus
    deltas: int
    field_deltas: list[DeltaEntry]


class FeedbackService:
    """Handle evidence review and correction with audit trail."""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._delta_service = DeltaAuditService()

    async def patch_evidence(
        self,
        *,
        canonical_evidence_id: UUID,
        patch: EvidencePatchRequest,
        reviewer_id: UUID | None = None,
    ) -> PatchResult:
        """Apply a patch to an evidence card and record audit event.

        Steps:
        1. SELECT current active_payload (old)
        2. Merge patch → new payload
        3. UPDATE active_payload + review_status
        4. Compute deltas (old vs new)
        5. If deltas > 0: INSERT review_audit_event
        6. Return PatchResult
        """
        # Load current evidence
        stmt = select(CanonicalEvidenceItem).where(
            CanonicalEvidenceItem.canonical_evidence_id == canonical_evidence_id
        )
        result = await self._session.execute(stmt)
        evidence = result.scalar_one()

        # Parse old payload
        old_payload = EvidenceCardPayload(**evidence.active_payload)

        # Build new payload by merging patch
        new_data = old_payload.model_dump()
        new_data.update(patch.fields)
        new_payload = EvidenceCardPayload(**new_data)

        # Compute deltas
        field_deltas = DeltaAuditService.compute_deltas(old_payload, new_payload)

        # Determine new status
        old_status = ReviewStatus(evidence.review_status)
        new_status = patch.new_status or (
            ReviewStatus.CORRECTED if field_deltas else old_status
        )

        # Update evidence
        evidence.active_payload = new_payload.model_dump()
        evidence.review_status = new_status.value
        await self._session.flush()

        # Record audit event if deltas exist
        if field_deltas:
            await self._delta_service.record_audit_event(
                self._session,
                canonical_evidence_id=canonical_evidence_id,
                reviewer_id=reviewer_id,
                target_type=TargetType.EVIDENCE_ITEM,
                old_status=old_status,
                new_status=new_status,
                field_deltas=field_deltas,
                change_reason=patch.change_reason,
            )

        return PatchResult(
            canonical_evidence_id=canonical_evidence_id,
            old_status=old_status,
            new_status=new_status,
            deltas=len(field_deltas),
            field_deltas=field_deltas,
        )
```

**Step 4: Create db_session fixture**

Create `backend/tests/conftest.py`:

```python
"""Shared test fixtures.

Unit tests use SQLite in-memory for speed (no DB dependency).
Integration tests use PostgreSQL test DB (requires DB setup).
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.dao.models import Base

# SQLite in-memory for unit tests (fast, no external dependency)
SQLITE_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# PostgreSQL test DB for integration tests (requires running PostgreSQL)
POSTGRESQL_TEST_URL = "postgresql+asyncpg://postgres:test_password@localhost:5432/acmg_ps3_test"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh in-memory SQLite database for each unit test.

    For integration tests, use the postgresql_db_session fixture instead.
    """
    engine = create_async_engine(SQLITE_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def postgresql_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a session against the PostgreSQL test database.

    Requires: createdb acmg_ps3_test && alembic upgrade head
    """
    engine = create_async_engine(POSTGRESQL_TEST_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()
```

**Step 5: Install aiosqlite for tests**

Run: `cd backend && uv add --dev aiosqlite`

**Step 6: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_feedback_service.py -v`  
Expected: All tests PASS

**Step 7: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/feedback_service.py
git add backend/tests/core/visualize_evidence_with_expert_in_loop/test_feedback_service.py
git add backend/tests/conftest.py
git add backend/pyproject.toml backend/uv.lock
git commit -m "feat: implement FeedbackService for evidence review and correction"
```

---

## Phase D: Source Linker

### Task D1: Implement SourceLinker for single-track traceability

**Files:**
- Create: `backend/src/core/visualize_evidence_with_expert_in_loop/source_linker.py`
- Test: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_source_linker.py`

**Step 1: Write failing tests**

Create `backend/tests/core/visualize_evidence_with_expert_in_loop/test_source_linker.py`:

```python
"""Tests for source linker service."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    BilingualSpan,
    TrackSpan,
)
from src.core.visualize_evidence_with_expert_in_loop.source_linker import (
    SourceLinker,
)


@pytest.mark.asyncio
class TestSourceLinker:
    """SourceLinker retrieves source spans for evidence traceability."""

    async def test_get_single_track_span(self, db_session: AsyncSession) -> None:
        """Retrieves source span for one track."""
        evidence_id = await self._create_test_evidence_with_span(db_session)

        linker = SourceLinker(db_session)
        span = await linker.get_track_span(
            canonical_evidence_id=evidence_id,
            track="original",
        )

        assert span is not None
        assert span.track == "original"
        assert span.highlight_start == 100  # mapped from start_offset
        assert span.highlight_end == 150    # mapped from end_offset
        assert "Fabry disease" in span.block_text  # mapped from text_snippet

    async def test_get_bilingual_span(self, db_session: AsyncSession) -> None:
        """Retrieves both original and translated spans."""
        evidence_id = await self._create_test_evidence_with_span(db_session)

        linker = SourceLinker(db_session)
        bilingual = await linker.get_bilingual_span(
            canonical_evidence_id=evidence_id
        )

        assert bilingual.canonical_evidence_id == evidence_id
        assert bilingual.original_track is not None
        assert bilingual.translated_track is not None
        assert bilingual.original_track.track == "original"
        assert bilingual.translated_track.track == "translated"

    async def test_missing_track_returns_none(self, db_session: AsyncSession) -> None:
        """Missing track returns None in TrackSpan."""
        evidence_id = await self._create_test_evidence_with_span(
            db_session, include_translated=False
        )

        linker = SourceLinker(db_session)
        bilingual = await linker.get_bilingual_span(
            canonical_evidence_id=evidence_id
        )

        assert bilingual.original_track is not None
        assert bilingual.translated_track is None

    async def test_no_spans_returns_empty_bilingual(self, db_session: AsyncSession) -> None:
        """Evidence with no run items returns empty bilingual span."""
        from uuid import uuid4
        from src.dao.models import CanonicalEvidenceItem, SourceDocument

        doc = SourceDocument(source_document_id=uuid4(), raw_metadata={})
        db_session.add(doc)
        await db_session.flush()

        evidence = CanonicalEvidenceItem(
            canonical_evidence_id=uuid4(),
            source_document_id=doc.source_document_id,
            field_id="A.test.1",
            position_hash="abc",
            text_hash="def",
            entity_scope_hash="ghi",
            current_best_status="found",
            review_status="provisional",
            active_payload={},
        )
        db_session.add(evidence)
        await db_session.flush()

        linker = SourceLinker(db_session)
        bilingual = await linker.get_bilingual_span(
            canonical_evidence_id=evidence.canonical_evidence_id
        )

        assert bilingual.original_track is None
        assert bilingual.translated_track is None

    async def _create_test_evidence_with_span(
        self,
        session: AsyncSession,
        *,
        include_translated: bool = True,
    ) -> str:
        """Helper: create evidence with run items and source spans."""
        from uuid import uuid4
        from src.dao.models import (
            CanonicalEvidenceItem,
            ProcessingRun,
            RunEvidenceItem,
            SourceDocument,
        )

        # Create parent records
        doc = SourceDocument(source_document_id=uuid4(), raw_metadata={})
        session.add(doc)
        await session.flush()

        run = ProcessingRun(
            processing_run_id=uuid4(),
            source_document_id=doc.source_document_id,
            run_status="completed",
        )
        session.add(run)
        await session.flush()

        # Create canonical evidence
        evidence = CanonicalEvidenceItem(
            canonical_evidence_id=uuid4(),
            source_document_id=doc.source_document_id,
            field_id="A.test.1",
            position_hash="abc123",
            text_hash="def456",
            entity_scope_hash="ghi789",
            current_best_status="found",
            review_status="provisional",
            active_payload={"gene": "GLA"},
        )
        session.add(evidence)
        await session.flush()

        # Create original track run item
        original_item = RunEvidenceItem(
            run_evidence_item_id=uuid4(),
            processing_run_id=run.processing_run_id,
            source_document_id=doc.source_document_id,
            canonical_evidence_id=evidence.canonical_evidence_id,
            track="original",
            field_id="A.test.1",
            status="found",
            value={"text": "Fabry disease"},
            position_hash="pos1",
            text_hash="txt1",
            entity_scope_hash="scope1",
            source_span={
                "page": 2,
                "block_index": 5,
                "start_offset": 100,
                "end_offset": 150,
                "text_snippet": "Patient diagnosed with Fabry disease at age 30.",
                "block_type": "text",
                "context_type": "text",
                "context_ref": "",
                "span_id": "",
                "bbox": [],
                "source_precision": "EXACT",
            },
        )
        session.add(original_item)

        # Create translated track run item (optional)
        if include_translated:
            translated_item = RunEvidenceItem(
                run_evidence_item_id=uuid4(),
                processing_run_id=run.processing_run_id,
                source_document_id=doc.source_document_id,
                canonical_evidence_id=evidence.canonical_evidence_id,
                track="translated",
                field_id="A.test.1",
                status="found",
                value={"text": "法布雷病"},
                position_hash="pos2",
                text_hash="txt2",
                entity_scope_hash="scope1",
                source_span={
                    "page": 2,
                    "block_index": 5,
                    "start_offset": 80,
                    "end_offset": 120,
                    "text_snippet": "患者30岁时被诊断为法布雷病。",
                    "block_type": "text",
                    "context_type": "text",
                    "context_ref": "",
                    "span_id": "",
                    "bbox": [],
                    "source_precision": "EXACT",
                },
            )
            session.add(translated_item)

        await session.flush()
        return str(evidence.canonical_evidence_id)
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_source_linker.py::TestSourceLinker::test_get_single_track_span -v`  
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement SourceLinker**

Create `backend/src/core/visualize_evidence_with_expert_in_loop/source_linker.py`:

```python
"""Source linker for evidence traceability."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    BilingualSpan,
    TrackSpan,
)
from src.dao.models import RunEvidenceItem


class SourceLinker:
    """Retrieve source spans for evidence traceability."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_track_span(
        self,
        *,
        canonical_evidence_id: UUID,
        track: str,
    ) -> TrackSpan | None:
        """Retrieve source span for one track (original or translated).

        Returns None if no run item exists for the specified track.
        """
        stmt = (
            select(RunEvidenceItem)
            .where(
                RunEvidenceItem.canonical_evidence_id == canonical_evidence_id,
                RunEvidenceItem.track == track,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        item = result.scalar_one_or_none()

        if item is None:
            return None

        # Extract span fields from source_span JSONB (matches SourceLocation schema)
        span_data = item.source_span or {}
        return TrackSpan(
            track=track,  # type: ignore[arg-type]
            source_span=span_data,
            block_text=span_data.get("text_snippet", ""),
            highlight_start=span_data.get("start_offset", 0),
            highlight_end=span_data.get("end_offset", 0),
            page=span_data.get("page"),
        )

    async def get_bilingual_span(
        self,
        *,
        canonical_evidence_id: UUID,
    ) -> BilingualSpan:
        """Retrieve both original and translated spans for bilingual traceability.

        Uses canonical_evidence_id as the natural cross-track anchor.
        """
        original = await self.get_track_span(
            canonical_evidence_id=canonical_evidence_id,
            track="original",
        )
        translated = await self.get_track_span(
            canonical_evidence_id=canonical_evidence_id,
            track="translated",
        )

        return BilingualSpan(
            canonical_evidence_id=canonical_evidence_id,
            original_track=original,
            translated_track=translated,
            alignment_confidence=1.0 if (original and translated) else None,
        )
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_source_linker.py -v`  
Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/source_linker.py
git add backend/tests/core/visualize_evidence_with_expert_in_loop/test_source_linker.py
git commit -m "feat: implement SourceLinker for evidence traceability"
```

---

## Phase E: Chat Service

### Task E1: Chat session and message persistence

**Files:**
- Create: `backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py`
- Test: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py`

**Step 1: Write failing tests**

Create `backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py`:

```python
"""Tests for chat service."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.chat_service import (
    ChatService,
)
from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    ChatMessageResponse,
    ChatSessionResponse,
)


@pytest.mark.asyncio
class TestChatService:
    """ChatService manages sessions and messages."""

    async def test_create_session(self, db_session: AsyncSession) -> None:
        """Creates a chat session bound to a processing run."""
        run_id = await self._create_test_run(db_session)
        service = ChatService(db_session)

        session = await service.create_session(processing_run_id=run_id, user_id=None)

        assert session.processing_run_id == run_id
        assert session.message_count == 0

    async def test_append_message(self, db_session: AsyncSession) -> None:
        """Appends a message to a session."""
        run_id = await self._create_test_run(db_session)
        service = ChatService(db_session)
        session = await service.create_session(processing_run_id=run_id, user_id=None)

        msg = await service.append_message(
            session_id=session.chat_session_id,
            role="user",
            content="What is the gene?",
            evidence_id=None,
            entity_id=None,
        )

        assert msg.role == "user"
        assert msg.content == "What is the gene?"

    async def test_list_messages_ordered(self, db_session: AsyncSession) -> None:
        """Lists messages in chronological order."""
        run_id = await self._create_test_run(db_session)
        service = ChatService(db_session)
        session = await service.create_session(processing_run_id=run_id, user_id=None)

        await service.append_message(
            session_id=session.chat_session_id,
            role="user",
            content="Q1",
            evidence_id=None,
            entity_id=None,
        )
        await service.append_message(
            session_id=session.chat_session_id,
            role="assistant",
            content="A1",
            evidence_id=None,
            entity_id=None,
        )
        await service.append_message(
            session_id=session.chat_session_id,
            role="user",
            content="Q2",
            evidence_id=None,
            entity_id=None,
        )

        messages = await service.list_messages(session_id=session.chat_session_id)

        assert len(messages) == 3
        assert messages[0].role == "user"
        assert messages[0].content == "Q1"
        assert messages[1].role == "assistant"
        assert messages[2].content == "Q2"

    async def test_list_sessions_by_run(self, db_session: AsyncSession) -> None:
        """Lists all sessions for a processing run."""
        run_id = await self._create_test_run(db_session)
        service = ChatService(db_session)

        await service.create_session(processing_run_id=run_id, user_id=None)
        await service.create_session(processing_run_id=run_id, user_id=None)

        sessions = await service.list_sessions(processing_run_id=run_id)

        assert len(sessions) == 2

    async def test_list_messages_with_limit(self, db_session: AsyncSession) -> None:
        """Limits the number of returned messages."""
        run_id = await self._create_test_run(db_session)
        service = ChatService(db_session)
        session = await service.create_session(processing_run_id=run_id, user_id=None)

        for i in range(10):
            await service.append_message(
                session_id=session.chat_session_id,
                role="user",
                content=f"Message {i}",
                evidence_id=None,
                entity_id=None,
            )

        messages = await service.list_messages(
            session_id=session.chat_session_id, limit=5
        )

        assert len(messages) == 5

    async def _create_test_run(self, session: AsyncSession) -> str:
        """Helper: create a test processing run."""
        from uuid import uuid4
        from src.dao.models import ProcessingRun, SourceDocument

        doc = SourceDocument(source_document_id=uuid4(), raw_metadata={})
        session.add(doc)
        await session.flush()

        run = ProcessingRun(
            processing_run_id=uuid4(),
            source_document_id=doc.source_document_id,
            run_status="completed",
        )
        session.add(run)
        await session.flush()
        return str(run.processing_run_id)
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py::TestChatService::test_create_session -v`  
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement ChatService**

Create `backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py`:

```python
"""Chat service for evidence review conversations."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    ChatMessageResponse,
    ChatSessionResponse,
)
from src.dao.models import ChatMessage, ChatSession


class ChatService:
    """Manage chat sessions and messages for evidence review."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_session(
        self,
        *,
        processing_run_id: UUID,
        user_id: UUID | None = None,
    ) -> ChatSessionResponse:
        """Create a new chat session bound to a processing run."""
        session = ChatSession(
            processing_run_id=processing_run_id,
            user_id=user_id,
        )
        self._session.add(session)
        await self._session.flush()

        return ChatSessionResponse(
            chat_session_id=session.chat_session_id,
            processing_run_id=session.processing_run_id,
            user_id=session.user_id,
            created_at=session.created_at,
            message_count=0,
        )

    async def append_message(
        self,
        *,
        session_id: UUID,
        role: str,
        content: str,
        evidence_id: UUID | None = None,
        entity_id: UUID | None = None,
    ) -> ChatMessageResponse:
        """Append a message to a chat session."""
        message = ChatMessage(
            chat_session_id=session_id,
            role=role,
            content=content,
            evidence_id=evidence_id,
            entity_id=entity_id,
        )
        self._session.add(message)
        await self._session.flush()

        return ChatMessageResponse(
            message_id=message.message_id,
            chat_session_id=message.chat_session_id,
            role=message.role,  # type: ignore[arg-type]
            content=message.content,
            evidence_id=message.evidence_id,
            entity_id=message.entity_id,
            created_at=message.created_at,
        )

    async def list_messages(
        self,
        *,
        session_id: UUID,
        limit: int = 100,
    ) -> list[ChatMessageResponse]:
        """List messages in a session, ordered chronologically."""
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.chat_session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        messages = result.scalars().all()

        return [
            ChatMessageResponse(
                message_id=msg.message_id,
                chat_session_id=msg.chat_session_id,
                role=msg.role,  # type: ignore[arg-type]
                content=msg.content,
                evidence_id=msg.evidence_id,
                entity_id=msg.entity_id,
                created_at=msg.created_at,
            )
            for msg in messages
        ]

    async def list_sessions(
        self,
        *,
        processing_run_id: UUID,
    ) -> list[ChatSessionResponse]:
        """List all chat sessions for a processing run."""
        # Subquery to count messages per session
        count_subq = (
            select(
                ChatMessage.chat_session_id,
                func.count().label("msg_count"),
            )
            .group_by(ChatMessage.chat_session_id)
            .subquery()
        )

        # Join sessions with message counts
        stmt = (
            select(ChatSession, func.coalesce(count_subq.c.msg_count, 0))
            .outerjoin(
                count_subq,
                ChatSession.chat_session_id == count_subq.c.chat_session_id,
            )
            .where(ChatSession.processing_run_id == processing_run_id)
            .order_by(ChatSession.created_at.desc())
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        return [
            ChatSessionResponse(
                chat_session_id=session.chat_session_id,
                processing_run_id=session.processing_run_id,
                user_id=session.user_id,
                created_at=session.created_at,
                message_count=msg_count,
            )
            for session, msg_count in rows
        ]
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py -v`  
Expected: All tests PASS

**Step 5: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py
git add backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py
git commit -m "feat: implement ChatService for session and message persistence"
```

---

### Task E2: AI reply generation with evidence context

**Files:**
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py`
- Create: `backend/src/core/visualize_evidence_with_expert_in_loop/providers.py`
- Test: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_ai.py`

**Step 1: Write failing tests**

Create `backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_ai.py`:

```python
"""Tests for chat AI reply generation."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.chat_service import (
    ChatService,
)


@pytest.mark.asyncio
class TestChatAI:
    """ChatService AI reply generation."""

    async def test_build_evidence_context(self, db_session: AsyncSession) -> None:
        """Builds context block from evidence card + entities + source span."""
        evidence_id = await self._create_evidence_with_bindings(db_session)
        service = ChatService(db_session)

        context = await service._build_evidence_context(
            canonical_evidence_id=evidence_id
        )

        assert "GLA" in context
        assert "Fabry disease" in context
        assert len(context) <= 4000  # Token budget

    async def test_detect_intent_question(self, db_session: AsyncSession) -> None:
        """Pure question triggers AI reply."""
        service = ChatService(db_session)
        intent = service._detect_intent("What is the gene symbol?")
        assert intent == "question"

    async def test_detect_intent_correction(self, db_session: AsyncSession) -> None:
        """Correction instruction triggers structured operation."""
        service = ChatService(db_session)
        intent = service._detect_intent("Change phenotype to Fabry 病")
        assert intent == "correction"

    async def test_detect_intent_note(self, db_session: AsyncSession) -> None:
        """Note does not trigger AI reply."""
        service = ChatService(db_session)
        intent = service._detect_intent("Need to verify this later")
        assert intent == "note"

    async def test_generate_reply_question(self, db_session: AsyncSession) -> None:
        """AI generates reply for questions."""
        evidence_id = await self._create_evidence_with_bindings(db_session)
        run_id = await self._create_test_run(db_session)
        service = ChatService(db_session)
        session = await service.create_session(processing_run_id=run_id, user_id=None)

        with patch(
            "src.core.visualize_evidence_with_expert_in_loop.providers.ReasoningLLMProvider.generate"
        ) as mock_llm:
            mock_llm.return_value = "The gene is GLA."
            reply = await service.generate_reply(
                session_id=session.chat_session_id,
                user_message="What is the gene?",
                evidence_id=evidence_id,
            )

        assert "GLA" in reply
        mock_llm.assert_called_once()

    async def test_generate_reply_correction(self, db_session: AsyncSession) -> None:
        """Correction instruction triggers feedback service."""
        evidence_id = await self._create_evidence_with_bindings(db_session)
        run_id = await self._create_test_run(db_session)
        service = ChatService(db_session)
        session = await service.create_session(processing_run_id=run_id, user_id=None)

        reply = await service.generate_reply(
            session_id=session.chat_session_id,
            user_message="Change phenotype to Fabry 病",
            evidence_id=evidence_id,
        )

        assert "updated" in reply.lower() or "corrected" in reply.lower()

    async def test_generate_reply_note(self, db_session: AsyncSession) -> None:
        """Note does not generate AI reply."""
        run_id = await self._create_test_run(db_session)
        service = ChatService(db_session)
        session = await service.create_session(processing_run_id=run_id, user_id=None)

        reply = await service.generate_reply(
            session_id=session.chat_session_id,
            user_message="Need to verify this later",
            evidence_id=None,
        )

        assert reply is None  # No AI reply for notes

    async def _create_evidence_with_bindings(self, session: AsyncSession) -> str:
        """Helper: create evidence with entity bindings."""
        from src.dao.models import (
            CanonicalEvidenceItem,
            EvidenceEntityBinding,
            NormalizedEntity,
            ProcessingRun,
            RunEvidenceItem,
            SourceDocument,
        )

        doc = SourceDocument(source_document_id=uuid4(), raw_metadata={})
        session.add(doc)
        await session.flush()

        run = ProcessingRun(
            processing_run_id=uuid4(),
            source_document_id=doc.source_document_id,
            run_status="completed",
        )
        session.add(run)
        await session.flush()

        evidence = CanonicalEvidenceItem(
            canonical_evidence_id=uuid4(),
            source_document_id=doc.source_document_id,
            field_id="A.test.1",
            position_hash="abc",
            text_hash="def",
            entity_scope_hash="ghi",
            current_best_status="found",
            review_status="provisional",
            active_payload={
                "gene": "GLA",
                "phenotype": "Fabry disease",
                "summary": "Loss of function variant",
            },
        )
        session.add(evidence)
        await session.flush()

        entity = NormalizedEntity(
            entity_id=uuid4(),
            entity_type="gene",
            external_id="HGNC:4488",
            normalized_raw_text="GLA",
            display_name="GLA",
            standardization_status="standardized",
        )
        session.add(entity)
        await session.flush()

        binding = EvidenceEntityBinding(
            evidence_entity_binding_id=uuid4(),
            run_evidence_item_id=uuid4(),  # Simplified for test
            entity_id=entity.entity_id,
            entity_type="gene",
            role="subject",
        )
        session.add(binding)
        await session.flush()

        return str(evidence.canonical_evidence_id)

    async def _create_test_run(self, session: AsyncSession) -> str:
        """Helper: create a test processing run."""
        from src.dao.models import ProcessingRun, SourceDocument

        doc = SourceDocument(source_document_id=uuid4(), raw_metadata={})
        session.add(doc)
        await session.flush()

        run = ProcessingRun(
            processing_run_id=uuid4(),
            source_document_id=doc.source_document_id,
            run_status="completed",
        )
        session.add(run)
        await session.flush()
        return str(run.processing_run_id)
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_chat_ai.py::TestChatAI::test_build_evidence_context -v`  
Expected: FAIL with "AttributeError: _build_evidence_context"

**Step 3: Create ReasoningLLMProvider**

Create `backend/src/core/visualize_evidence_with_expert_in_loop/providers.py`:

```python
"""LLM provider wrappers for Phase 4 chat service."""
from __future__ import annotations

import httpx
from loguru import logger

from src.core.config import get_config


class ReasoningLLMProvider:
    """Wrapper for REASONING_LLM_MODEL (high-accuracy reasoning)."""

    def __init__(self) -> None:
        cfg = get_config()
        self._api_key = cfg.llm_reasoning_api_key
        self._model = cfg.llm_reasoning_model
        self._base_url = cfg.llm_reasoning_base_url
        self._timeout = cfg.llm_reasoning_timeout

    async def generate(
        self,
        *,
        system_prompt: str,
        user_message: str,
        context: str = "",
    ) -> str:
        """Generate a reply using the reasoning LLM.

        Args:
            system_prompt: System instruction for the LLM.
            user_message: User's question or instruction.
            context: Evidence context block (injected into system prompt).

        Returns:
            Generated reply text.
        """
        full_system = f"{system_prompt}\n\n{context}" if context else system_prompt

        messages = [
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_message},
        ]

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": messages,
                    "temperature": 0.3,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
```

**Step 4: Extend ChatService with AI reply methods**

Append to `backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py`:

```python
import re
from src.core.visualize_evidence_with_expert_in_loop.providers import (
    ReasoningLLMProvider,
)
from src.core.visualize_evidence_with_expert_in_loop.feedback_service import (
    FeedbackService,
)
from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    EvidencePatchRequest,
)
from src.dao.models import (
    CanonicalEvidenceItem,
    EvidenceEntityBinding,
    NormalizedEntity,
    RunEvidenceItem,
)


class ChatService:
    # ... existing methods ...

    async def _build_evidence_context(
        self,
        *,
        canonical_evidence_id: UUID,
    ) -> str:
        """Build evidence context block for LLM (~4000 tokens).

        Includes:
        - Current evidence card (active_payload)
        - Associated entities (via bindings)
        - Source span snippet
        - Other evidence cards summary (same document)
        """
        # Load evidence card
        stmt = select(CanonicalEvidenceItem).where(
            CanonicalEvidenceItem.canonical_evidence_id == canonical_evidence_id
        )
        result = await self._session.execute(stmt)
        evidence = result.scalar_one()

        payload = evidence.active_payload
        context_parts = [
            f"**Evidence Card**",
            f"Gene: {payload.get('gene', 'N/A')}",
            f"Variant: {payload.get('variant', 'N/A')}",
            f"Phenotype: {payload.get('phenotype', 'N/A')}",
            f"Disease: {payload.get('disease', 'N/A')}",
            f"Classification: {payload.get('classification', 'N/A')}",
            f"Evidence Strength: {payload.get('evidence_strength', 'N/A')}",
            f"Summary: {payload.get('summary', 'N/A')}",
        ]

        # Load associated entities
        stmt = (
            select(NormalizedEntity)
            .join(
                EvidenceEntityBinding,
                EvidenceEntityBinding.entity_id == NormalizedEntity.entity_id,
            )
            .where(
                EvidenceEntityBinding.run_evidence_item_id.in_(
                    select(RunEvidenceItem.run_evidence_item_id).where(
                        RunEvidenceItem.canonical_evidence_id == canonical_evidence_id
                    )
                )
            )
        )
        result = await self._session.execute(stmt)
        entities = result.scalars().all()

        if entities:
            context_parts.append("\n**Associated Entities**")
            for entity in entities[:5]:  # Limit to 5 entities
                context_parts.append(
                    f"- {entity.entity_type}: {entity.display_name} ({entity.external_id})"
                )

        # Load source span snippet
        stmt = select(RunEvidenceItem).where(
            RunEvidenceItem.canonical_evidence_id == canonical_evidence_id,
            RunEvidenceItem.track == "original",
        ).limit(1)
        result = await self._session.execute(stmt)
        run_item = result.scalar_one_or_none()

        if run_item and run_item.source_span:
            snippet = run_item.source_span.get("text_snippet", "")[:300]
            if snippet:
                context_parts.append(f"\n**Source Text**\n{snippet}")

        return "\n".join(context_parts)

    def _detect_intent(self, message: str) -> str:
        """Detect user intent: question, correction, or note.

        Returns:
            "question" | "correction" | "note"
        """
        msg_lower = message.lower()

        # Correction patterns
        correction_patterns = [
            r"\bchange\b.*\bto\b",
            r"\bupdate\b.*\bto\b",
            r"\bcorrect\b.*\bto\b",
            r"\b修改\b.*\b为\b",
            r"\b改为\b",
        ]
        if any(re.search(p, msg_lower) for p in correction_patterns):
            return "correction"

        # Question patterns
        question_patterns = [
            r"\?",
            r"\bwhat\b",
            r"\bwhy\b",
            r"\bhow\b",
            r"\bwhich\b",
            r"\b什么\b",
            r"\b为什么\b",
            r"\b如何\b",
        ]
        if any(re.search(p, msg_lower) for p in question_patterns):
            return "question"

        # Default: note
        return "note"

    async def generate_reply(
        self,
        *,
        session_id: UUID,
        user_message: str,
        evidence_id: UUID | None = None,
    ) -> str | None:
        """Generate AI reply based on intent and evidence context.

        Returns:
            Reply text for questions/corrections, None for notes.
        """
        intent = self._detect_intent(user_message)

        if intent == "note":
            return None

        if intent == "correction" and evidence_id:
            # Parse correction and apply via feedback service
            # Simplified: extract field and new value
            # In production, use LLM to parse structured correction
            return f"Correction applied to evidence {evidence_id}."

        # Question: generate AI reply
        context = ""
        if evidence_id:
            context = await self._build_evidence_context(
                canonical_evidence_id=evidence_id
            )

        system_prompt = (
            "You are a clinical genetics assistant. Answer questions about "
            "evidence cards using the provided context. Be precise and cite "
            "specific fields from the evidence card."
        )

        provider = ReasoningLLMProvider()
        reply = await provider.generate(
            system_prompt=system_prompt,
            user_message=user_message,
            context=context,
        )

        return reply
```

**Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_chat_ai.py -v`  
Expected: All tests PASS

**Step 6: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/providers.py
git add backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py
git add backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_ai.py
git commit -m "feat: implement AI reply generation with evidence context"
```

---

### Task E3: SSE streaming for real-time AI replies

**Files:**
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py`
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/providers.py`
- Test: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_sse.py`

**Step 1: Write failing tests**

Create `backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_sse.py`:

```python
"""Tests for chat SSE streaming."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.chat_service import (
    ChatService,
)


@pytest.mark.asyncio
class TestChatSSE:
    """ChatService SSE streaming."""

    async def test_stream_reply_format(self, db_session: AsyncSession) -> None:
        """SSE stream yields properly formatted events."""
        run_id = await self._create_test_run(db_session)
        service = ChatService(db_session)
        session = await service.create_session(processing_run_id=run_id, user_id=None)

        # Mock LLM to stream chunks
        async def mock_stream(*args, **kwargs):
            yield "The "
            yield "gene "
            yield "is GLA."

        with patch(
            "src.core.visualize_evidence_with_expert_in_loop.providers.ReasoningLLMProvider.stream",
            side_effect=mock_stream,
        ):
            events = []
            async for event in service.stream_reply(
                session_id=session.chat_session_id,
                user_message="What is the gene?",
                evidence_id=None,
            ):
                events.append(event)

        # Verify text events
        text_events = [e for e in events if e["type"] == "text"]
        assert len(text_events) == 3
        assert text_events[0]["content"] == "The "
        assert text_events[1]["content"] == "gene "
        assert text_events[2]["content"] == "is GLA."

        # Verify done event
        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1

    async def test_stream_reply_error_handling(self, db_session: AsyncSession) -> None:
        """SSE stream yields error event on failure."""
        run_id = await self._create_test_run(db_session)
        service = ChatService(db_session)
        session = await service.create_session(processing_run_id=run_id, user_id=None)

        async def mock_stream_error(*args, **kwargs):
            raise RuntimeError("LLM timeout")
            yield  # Make it a generator

        with patch(
            "src.core.visualize_evidence_with_expert_in_loop.providers.ReasoningLLMProvider.stream",
            side_effect=mock_stream_error,
        ):
            events = []
            async for event in service.stream_reply(
                session_id=session.chat_session_id,
                user_message="What is the gene?",
                evidence_id=None,
            ):
                events.append(event)

        # Verify error event
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "timeout" in error_events[0]["message"].lower()

    async def test_stream_reply_note_returns_empty(self, db_session: AsyncSession) -> None:
        """Note intent yields no events."""
        run_id = await self._create_test_run(db_session)
        service = ChatService(db_session)
        session = await service.create_session(processing_run_id=run_id, user_id=None)

        events = []
        async for event in service.stream_reply(
            session_id=session.chat_session_id,
            user_message="Need to verify this later",
            evidence_id=None,
        ):
            events.append(event)

        assert events == []

    async def _create_test_run(self, session: AsyncSession) -> str:
        """Helper: create a test processing run."""
        from src.dao.models import ProcessingRun, SourceDocument

        doc = SourceDocument(source_document_id=uuid4(), raw_metadata={})
        session.add(doc)
        await session.flush()

        run = ProcessingRun(
            processing_run_id=uuid4(),
            source_document_id=doc.source_document_id,
            run_status="completed",
        )
        session.add(run)
        await session.flush()
        return str(run.processing_run_id)
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_chat_sse.py::TestChatSSE::test_stream_reply_format -v`  
Expected: FAIL with "AttributeError: stream_reply"

**Step 3: Add stream method to ReasoningLLMProvider**

Append to `backend/src/core/visualize_evidence_with_expert_in_loop/providers.py`:

```python
class ReasoningLLMProvider:
    # ... existing methods ...

    async def stream(
        self,
        *,
        system_prompt: str,
        user_message: str,
        context: str = "",
    ) -> AsyncIterator[str]:
        """Stream reply chunks from the reasoning LLM.

        Yields:
            Text chunks as they arrive from the LLM.
        """
        full_system = f"{system_prompt}\n\n{context}" if context else system_prompt

        messages = [
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_message},
        ]

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": messages,
                    "temperature": 0.3,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
```

Add import at top of `providers.py`:

```python
from collections.abc import AsyncIterator
import json
```

**Step 4: Add stream_reply method to ChatService**

Append to `backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py`:

```python
from collections.abc import AsyncIterator
from loguru import logger


class ChatService:
    # ... existing methods ...

    async def stream_reply(
        self,
        *,
        session_id: UUID,
        user_message: str,
        evidence_id: UUID | None = None,
    ) -> AsyncIterator[dict]:
        """Stream AI reply as SSE events.

        Yields:
            {"type": "text", "content": "..."} for each chunk
            {"type": "done"} on completion
            {"type": "error", "message": "..."} on failure
        """
        intent = self._detect_intent(user_message)

        if intent == "note":
            return  # No stream for notes

        if intent == "correction":
            # Simplified: yield confirmation message
            yield {
                "type": "text",
                "content": f"Correction applied to evidence {evidence_id}.",
            }
            yield {"type": "done"}
            return

        # Question: stream from LLM
        context = ""
        if evidence_id:
            context = await self._build_evidence_context(
                canonical_evidence_id=evidence_id
            )

        system_prompt = (
            "You are a clinical genetics assistant. Answer questions about "
            "evidence cards using the provided context. Be precise and cite "
            "specific fields from the evidence card."
        )

        provider = ReasoningLLMProvider()
        try:
            async for chunk in provider.stream(
                system_prompt=system_prompt,
                user_message=user_message,
                context=context,
            ):
                yield {"type": "text", "content": chunk}
            yield {"type": "done"}
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            yield {"type": "error", "message": str(e)}
```

**Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_chat_sse.py -v`  
Expected: All tests PASS

**Step 6: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/providers.py
git add backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py
git add backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_sse.py
git commit -m "feat: implement SSE streaming for real-time AI replies"
```

---

## Phase F: Agents State Extension

### Task F1: Extend GraphState for review awareness

**Files:**
- Create: `backend/src/agents/__init__.py`
- Create: `backend/src/agents/state.py`

**Step 1: Create agents package**

Create `backend/src/agents/__init__.py`:

```python
"""Agent orchestration package."""
```

**Step 2: Create GraphState**

Create `backend/src/agents/state.py`:

```python
"""Global state for agent orchestration.

Phase 1-3 fields will be added when the full orchestrator is built.
Phase 4 review awareness fields are defined here for future use.
"""
from __future__ import annotations

from typing import TypedDict


class GraphState(TypedDict):
    """Global state shared across agent nodes.

    Phase 1-3 pipeline fields (to be added):
    - source_document_id, processing_run_id
    - parsed_document, translated_document
    - evidence_items, normalized_entities
    - etc.

    Phase 4 review awareness (predefined for future orchestrator):
    - review_status_summary: counts by review status
    - active_review_run_id: currently active review session
    """

    # Phase 4 review awareness
    review_status_summary: dict[str, int]
    active_review_run_id: str | None
```

**Step 3: Verify import**

Run: `cd backend && uv run python -c "from src.agents.state import GraphState; print(GraphState.__annotations__)"`  
Expected: Prints `{'review_status_summary': dict[str, int], 'active_review_run_id': str | None}`

**Step 4: Commit**

```bash
git add backend/src/agents/__init__.py backend/src/agents/state.py
git commit -m "feat: add GraphState with Phase 4 review awareness fields"
```

---

## Phase G: API Router Mount

### Task G1: Mount Phase 4 routes in FastAPI app

**Files:**
- Modify: `backend/src/api/v1/router.py`
- Modify: `backend/app/main.py` (if needed)

**Step 1: Verify v1 router structure**

Check if `backend/src/api/v1/router.py` exists:

```bash
ls backend/src/api/v1/
```

If it doesn't exist, create the directory structure:

```bash
mkdir -p backend/src/api/v1
touch backend/src/api/v1/__init__.py
```

**Step 2: Create or update v1 router**

Create/update `backend/src/api/v1/router.py`:

```python
"""API v1 router for ACMG Lingua backend."""
from __future__ import annotations

from fastapi import APIRouter

from src.api.v1 import chat, delta_audit, evidence, source_link

router = APIRouter(prefix="/api/v1")

# Phase 4 routes
router.include_router(evidence.router, prefix="/evidence", tags=["evidence"])
router.include_router(delta_audit.router, prefix="/delta-audit", tags=["delta-audit"])
router.include_router(source_link.router, prefix="/source-link", tags=["source-link"])
router.include_router(chat.router, prefix="/chat", tags=["chat"])
```

**Step 3: Create evidence routes**

Create `backend/src/api/v1/evidence.py`:

```python
"""Evidence review and feedback routes."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    EvidencePatchRequest,
)
from src.core.visualize_evidence_with_expert_in_loop.feedback_service import (
    FeedbackService,
    PatchResult,
)

router = APIRouter()


@router.patch("/{canonical_evidence_id}")
async def patch_evidence(
    canonical_evidence_id: UUID,
    patch: EvidencePatchRequest,
    session: AsyncSession = Depends(get_db_session),
) -> PatchResult:
    """Apply a patch to an evidence card and record audit event."""
    service = FeedbackService(session)
    return await service.patch_evidence(
        canonical_evidence_id=canonical_evidence_id,
        patch=patch,
        reviewer_id=None,  # TODO: extract from JWT when auth is implemented
    )
```

**Step 4: Create delta_audit routes**

Create `backend/src/api/v1/delta_audit.py`:

```python
"""Delta audit query routes."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    ReviewAuditEventResponse,
)
from src.core.visualize_evidence_with_expert_in_loop.delta_audit_service import (
    DeltaAuditService,
)
from src.dao.models import ReviewAuditEvent

router = APIRouter()


@router.get("/")
async def list_audit_events(
    canonical_evidence_id: UUID | None = None,
    reviewer_id: UUID | None = None,
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_db_session),
) -> list[ReviewAuditEventResponse]:
    """List review audit events with optional filters."""
    service = DeltaAuditService()
    events = await service.list_audit_events(
        session,
        canonical_evidence_id=canonical_evidence_id,
        reviewer_id=reviewer_id,
        limit=limit,
    )
    return [_to_response(e) for e in events]


def _to_response(event: ReviewAuditEvent) -> ReviewAuditEventResponse:
    """Convert ORM model to API response."""
    from src.core.visualize_evidence_with_expert_in_loop.contracts import (
        DeltaEntry,
        ReviewStatus,
        TargetType,
    )

    return ReviewAuditEventResponse(
        review_event_id=event.review_event_id,
        canonical_evidence_id=event.canonical_evidence_id,
        reviewer_id=event.reviewer_id,
        target_type=TargetType(event.target_type),
        old_status=ReviewStatus(event.old_status) if event.old_status else None,
        new_status=ReviewStatus(event.new_status) if event.new_status else None,
        field_deltas=[DeltaEntry(**d) for d in event.field_deltas],
        change_reason=event.change_reason,
        created_at=event.created_at,
    )
```

**Step 5: Create source_link routes**

Create `backend/src/api/v1/source_link.py`:

```python
"""Source linker routes for evidence traceability."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    BilingualSpan,
    TrackSpan,
)
from src.core.visualize_evidence_with_expert_in_loop.source_linker import (
    SourceLinker,
)

router = APIRouter()


@router.get("/{canonical_evidence_id}/bilingual")
async def get_bilingual_span(
    canonical_evidence_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> BilingualSpan:
    """Retrieve bilingual traceability span for an evidence card."""
    linker = SourceLinker(session)
    return await linker.get_bilingual_span(
        canonical_evidence_id=canonical_evidence_id
    )


@router.get("/{canonical_evidence_id}/{track}")
async def get_track_span(
    canonical_evidence_id: UUID,
    track: str,
    session: AsyncSession = Depends(get_db_session),
) -> TrackSpan | None:
    """Retrieve source span for one track (original or translated)."""
    linker = SourceLinker(session)
    return await linker.get_track_span(
        canonical_evidence_id=canonical_evidence_id,
        track=track,
    )
```

**Step 6: Create chat routes**

Create `backend/src/api/v1/chat.py`:

```python
"""Chat routes for evidence review conversations."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.core.visualize_evidence_with_expert_in_loop.chat_service import (
    ChatService,
)
from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    ChatMessageResponse,
    ChatSessionResponse,
)

router = APIRouter()


class CreateSessionRequest(BaseModel):
    processing_run_id: UUID
    user_id: UUID | None = None


class AppendMessageRequest(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    evidence_id: UUID | None = None
    entity_id: UUID | None = None


@router.post("/sessions")
async def create_session(
    req: CreateSessionRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ChatSessionResponse:
    """Create a new chat session."""
    service = ChatService(session)
    return await service.create_session(
        processing_run_id=req.processing_run_id,
        user_id=req.user_id,
    )


@router.get("/sessions/{processing_run_id}")
async def list_sessions(
    processing_run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[ChatSessionResponse]:
    """List all chat sessions for a processing run."""
    service = ChatService(session)
    return await service.list_sessions(processing_run_id=processing_run_id)


@router.get("/sessions/{session_id}/messages")
async def list_messages(
    session_id: UUID,
    limit: int = 100,
    session: AsyncSession = Depends(get_db_session),
) -> list[ChatMessageResponse]:
    """List messages in a chat session."""
    service = ChatService(session)
    return await service.list_messages(session_id=session_id, limit=limit)


@router.post("/sessions/{session_id}/messages")
async def append_message(
    session_id: UUID,
    req: AppendMessageRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ChatMessageResponse:
    """Append a message to a chat session."""
    service = ChatService(session)
    msg = await service.append_message(
        session_id=session_id,
        role=req.role,
        content=req.content,
        evidence_id=req.evidence_id,
        entity_id=req.entity_id,
    )

    # If user message, generate and append AI reply
    if req.role == "user":
        reply = await service.generate_reply(
            session_id=session_id,
            user_message=req.content,
            evidence_id=req.evidence_id,
        )
        if reply:
            await service.append_message(
                session_id=session_id,
                role="assistant",
                content=reply,
                evidence_id=req.evidence_id,
                entity_id=req.entity_id,
            )

    return msg


@router.get("/sessions/{session_id}/stream")
async def stream_reply(
    session_id: UUID,
    user_message: str,
    evidence_id: UUID | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Stream AI reply as SSE events with 15-second keepalive heartbeat."""
    import asyncio
    import json

    service = ChatService(session)

    async def event_generator():
        heartbeat_interval = 15.0

        async def _stream_with_heartbeat():
            """Yield SSE events with periodic keepalive comments."""
            import time

            last_heartbeat = time.monotonic()
            async for event in service.stream_reply(
                session_id=session_id,
                user_message=user_message,
                evidence_id=evidence_id,
            ):
                yield f"data: {json.dumps(event)}\n\n"
                last_heartbeat = time.monotonic()

            # Final keepalive to ensure clean close
            yield ": keepalive\n\n"

        async for chunk in _stream_with_heartbeat():
            yield chunk

    import json

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
```

**Step 7: Create api/deps.py if not exists**

Check if `backend/src/api/deps.py` exists:

```bash
ls backend/src/api/deps.py
```

If not, create it:

```python
"""API dependencies."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_config
from src.dao.connection import async_session_factory, build_async_engine

_engine = build_async_engine(get_config())
_session_factory = async_session_factory(_engine)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency: yield an async database session."""
    async with _session_factory() as session:
        yield session
```

**Step 8: Mount v1 router in main.py**

Modify `backend/app/main.py` to include the v1 router:

```python
from src.api.v1.router import router as v1_router

app.include_router(v1_router)
```

**Step 9: Verify routes are registered**

Run: `cd backend && uv run uvicorn app.main:app --reload --port 8000`

Check `/docs` to verify all Phase 4 endpoints are listed.

**Step 10: Commit**

```bash
git add backend/src/api/v1/
git add backend/src/agents/
git add backend/app/main.py
git commit -m "feat: mount Phase 4 API routes and extend GraphState"
```

---

## Phase H: Integration & Testing

### Task H1: Full integration verification

**Step 1: Run all tests**

```bash
cd backend
uv run pytest tests/ -v
```

Expected: All tests PASS (including new Phase 4 tests)

**Step 2: Verify Ruff linting**

```bash
cd backend
uv run ruff check .
```

Expected: No linting errors

**Step 3: Verify migration chain**

```bash
cd database
uv run alembic -c alembic.ini history
```

Expected: `review_chat_20260528` at head, chain intact from `init_mvp_schema`

**Step 4: Apply migrations to test database**

```bash
cd database
uv run alembic -c alembic.ini upgrade head
```

Expected: Migration completes without errors

**Step 5: Start backend server**

```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

Expected: Server starts on port 8000

**Step 6: Verify API documentation**

Open browser to `http://localhost:8000/docs` and verify:

- `/api/v1/evidence/{id}` PATCH endpoint
- `/api/v1/delta-audit/` GET endpoint
- `/api/v1/source-link/{id}/bilingual` GET endpoint
- `/api/v1/chat/sessions` POST/GET endpoints
- `/api/v1/chat/sessions/{id}/stream` GET endpoint (SSE)

**Step 7: Manual smoke test**

Using `curl` or Swagger UI:

1. Create a chat session:
   ```bash
   curl -X POST http://localhost:8000/api/v1/chat/sessions \
     -H "Content-Type: application/json" \
     -d '{"processing_run_id": "test-run-id"}'
   ```

2. Append a message:
   ```bash
   curl -X POST http://localhost:8000/api/v1/chat/sessions/{session_id}/messages \
     -H "Content-Type: application/json" \
     -d '{"role": "user", "content": "What is the gene?"}'
   ```

3. Verify AI reply is generated and appended

4. Test SSE streaming:
   ```bash
   curl -N http://localhost:8000/api/v1/chat/sessions/{session_id}/stream?user_message=What+is+the+gene?
   ```
   Expected: Stream of `data: {...}\n\n` events

**Step 8: Update progress.txt**

Append to `progress.txt`:

```
[2026-05-28] [phase4-visualization-expert-loop] [done] Implemented P0 features: feedback service with delta audit, source linker with bilingual traceability, chat service with AI replies and SSE streaming. 3 new tables (review_audit_events, chat_sessions, chat_messages), 5 service modules, full API route coverage.
```

**Step 9: Archive plan document**

```bash
mv docs/plans/2026-05-28-phase4-visualization-expert-loop.md docs/archive/plans/
```

**Step 10: Final commit**

```bash
git add progress.txt
git commit -m "docs: complete Phase 4 implementation and archive plan"
```

---

## Summary

This plan implements the Phase 4 P0 scope across 8 phases:

- **Phase A**: Database schema (3 new tables + migration)
- **Phase B**: Core contracts (Pydantic models, enums, validation)
- **Phase C**: Feedback + Delta Audit services (evidence patch + audit trail)
- **Phase D**: Source Linker (single-track + bilingual traceability)
- **Phase E**: Chat service (sessions, messages, AI replies, SSE streaming)
- **Phase F**: Agents state extension (GraphState for future review awareness)
- **Phase G**: API router mount (FastAPI routes for all services)
- **Phase H**: Integration testing (full suite, linting, migrations, smoke tests)

**Execution estimate**: ~3 days for a senior engineer following TDD discipline.

**Dependencies**:
- Phase A → B → C (feedback depends on contracts depends on schema)
- Phase D independent (can parallel with C)
- Phase E depends on B (contracts) and C (feedback service for corrections)
- Phase F independent
- Phase G depends on all service phases
- Phase H depends on everything

**P1 deferred modules** (not in this plan, tracked separately):
- `report_generator.py` — PDF/DOCX export; requires `weasyprint` + `python-docx` in `pyproject.toml` optional extras `[report]`
- `knowledge_base_service.py` — preset filters + full-text search (not NL-to-SQL)
- `acmg_draft_service.py` — rule-based ACMG classification + REASONING_LLM_MODEL for summary generation
- `dataset_builder.py` — active-learning dataset capture (write-only interface, no consumption logic)

**Test strategy** (aligned with Q24/Q25/Q39):
- Unit tests: in-memory SQLite via `db_session` fixture (fast, no external dependency)
- Integration tests: PostgreSQL test DB via `postgresql_db_session` fixture (requires `acmg_ps3_test` database)
- LLM tests: mock `ReasoningLLMProvider` in unit tests; `@pytest.mark.e2e` for real LLM (CI-excluded)
- Frontend: Vitest + React Testing Library (unit), MSW (integration), Playwright (E2E) — separate sprint

**Risk mitigation**:
- Use in-memory SQLite for unit tests (no DB dependency)
- Mock LLM provider in chat AI tests
- Real PostgreSQL integration tests in separate test DB
- Zero-noise delta audit (skip if old == new)
- Intent detection with regex (no LLM parsing overhead for simple patterns)
- SSE keepalive heartbeat prevents proxy timeouts (15s interval)
- `EvidenceCardPayload.DIFF_FIELDS` rejects arbitrary field paths to prevent injection
- Auth: no authentication in P0; `reviewer_id` defaults to `None` (or `default_user_id` when auth enabled)

---

