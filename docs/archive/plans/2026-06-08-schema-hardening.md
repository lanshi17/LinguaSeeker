# Schema Hardening: Circular FK, Search Sync, and Index Fixes

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the circular FK between run/canonical evidence tables (including a functional bug where source_linker and chat_service always return empty results), wire up the stale frontend_search_index, and harden two other schema issues found during architectural review.

**Architecture:** Five independent fixes ordered by severity. Tasks 1-3 fix the critical circular FK and dead read-path bug. Task 4 wires the search index sync. Tasks 5-7 are schema hardening (documentation, status enum, column extraction). Each task is self-contained with its own migration where needed.

**Tech Stack:** SQLAlchemy ORM (async), Alembic migration, FastAPI, pytest.

---

## Task 1: Remove Dead `canonical_evidence_id` Column from `RunEvidenceItem`

**Problem:** `RunEvidenceItem.canonical_evidence_id` is never written to (always NULL), yet `source_linker.py` and `chat_service.py` query on it — meaning those queries always return empty results. This is a functional bug disguised as a design smell.

**Files:**
- Modify: `backend/src/dao/postgresql/models.py:244-280` — remove column and index
- Create: `database/migrations/versions/2026-06-08_remove_run_evidence_canonical_fk.py`
- Test: `backend/tests/dao/postgresql/test_models.py` — update if any test references the column

**Step 1: Write the failing test**

Add to `backend/tests/dao/postgresql/test_models.py`:

```python
def test_run_evidence_item_has_no_canonical_evidence_id() -> None:
    """RunEvidenceItem no longer has canonical_evidence_id (dead FK removed)."""
    from src.dao.postgresql.models import RunEvidenceItem

    column_names = {c.name for c in RunEvidenceItem.__table__.columns}
    assert "canonical_evidence_id" not in column_names
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/dao/postgresql/test_models.py::test_run_evidence_item_has_no_canonical_evidence_id -v`
Expected: FAIL — `canonical_evidence_id` still exists

**Step 3: Remove the column from the ORM model**

In `backend/src/dao/postgresql/models.py`, remove:

1. The `canonical_evidence_id` column definition (lines 276-280):
```python
    canonical_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_evidence_items.canonical_evidence_id", use_alter=True),
        nullable=True,
    )
```

2. The index on this column (line 252):
```python
        Index("ix_run_evidence_items_canonical_evidence_id", "canonical_evidence_id"),
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/dao/postgresql/test_models.py -v`
Expected: PASS

**Step 5: Create the Alembic migration**

Create `database/migrations/versions/2026-06-08_remove_run_evidence_canonical_fk.py`:

```python
"""Remove dead canonical_evidence_id FK from run_evidence_items.

Revision ID: rm_canonical_fk_20260608
Revises: lit_profiles_20260608
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "rm_canonical_fk_20260608"
down_revision = "lit_profiles_20260608"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(
        "ix_run_evidence_items_canonical_evidence_id",
        table_name="run_evidence_items",
    )
    op.drop_column("run_evidence_items", "canonical_evidence_id")


def downgrade() -> None:
    op.add_column(
        "run_evidence_items",
        sa.Column("canonical_evidence_id", sa.UUID(), nullable=True),
    )
    op.create_index(
        "ix_run_evidence_items_canonical_evidence_id",
        "run_evidence_items",
        ["canonical_evidence_id"],
    )
    op.create_foreign_key(
        "fk_run_evidence_items_canonical_evidence_id",
        "run_evidence_items",
        "canonical_evidence_items",
        ["canonical_evidence_id"],
        ["canonical_evidence_id"],
    )
```

**Step 6: Commit**

```bash
git add backend/src/dao/postgresql/models.py database/migrations/versions/2026-06-08_remove_run_evidence_canonical_fk.py backend/tests/dao/postgresql/test_models.py
git commit -m "fix(db): remove dead canonical_evidence_id FK from run_evidence_items"
```

---

## Task 2: Refactor `source_linker.py` to Use `current_best_run_evidence_id`

**Problem:** `source_linker.py` queries `RunEvidenceItem.canonical_evidence_id` which is always NULL (removed in Task 1). Must use the canonical item's `current_best_run_evidence_id` instead.

**Files:**
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/source_linker.py:28-45`
- Test: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_source_linker.py` (create if not exists)

**Step 1: Read the current implementation**

Read `backend/src/core/visualize_evidence_with_expert_in_loop/source_linker.py` to understand the full `get_track_span` and `get_bilingual_span` methods.

**Step 2: Write the failing test**

Create `backend/tests/core/visualize_evidence_with_expert_in_loop/test_source_linker.py`:

```python
"""Tests for SourceLinker read path."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_get_track_span_loads_canonical_then_fetches_run() -> None:
    """SourceLinker.get_track_span loads canonical item first, then fetches the best run via current_best_run_evidence_id."""
    from src.core.visualize_evidence_with_expert_in_loop.source_linker import SourceLinker

    session = MagicMock()
    canonical_id = uuid4()
    best_run_id = uuid4()

    # Mock canonical item with current_best_run_evidence_id
    mock_canonical = MagicMock()
    mock_canonical.current_best_run_evidence_id = best_run_id

    # Mock the best run evidence item
    mock_run = MagicMock()
    mock_run.source_span = {"text_snippet": "test", "start_offset": 0, "end_offset": 4}
    mock_run.track = "original"

    # First execute returns canonical, second returns run
    canonical_result = MagicMock()
    canonical_result.scalar_one_or_none.return_value = mock_canonical
    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = mock_run
    session.execute = AsyncMock(side_effect=[canonical_result, run_result])

    linker = SourceLinker(session)
    span = await linker.get_track_span(canonical_evidence_id=canonical_id, track="original")

    assert span is not None
    assert session.execute.await_count == 2
```

**Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_source_linker.py -v`
Expected: FAIL

**Step 4: Refactor `get_track_span`**

The current logic (line 28-45):
```python
async def get_track_span(self, *, canonical_evidence_id: UUID, track: str) -> TrackSpan | None:
    stmt = (
        select(RunEvidenceItem)
        .where(
            RunEvidenceItem.canonical_evidence_id == canonical_evidence_id,  # BUG: always NULL
            RunEvidenceItem.track == track,
        )
        .limit(1)
    )
    ...
```

Replace with:
```python
async def get_track_span(self, *, canonical_evidence_id: UUID, track: str) -> TrackSpan | None:
    """Load the best run evidence item for a canonical item on the given track.

    Resolution: CanonicalEvidenceItem.current_best_run_evidence_id → RunEvidenceItem.
    Falls back to identity-tuple lookup if current_best_run_evidence_id is NULL.
    """
    # Step 1: Load canonical item to get current_best_run_evidence_id
    canonical_stmt = (
        select(CanonicalEvidenceItem.current_best_run_evidence_id)
        .where(CanonicalEvidenceItem.canonical_evidence_id == canonical_evidence_id)
    )
    canonical_result = await self._session.execute(canonical_stmt)
    best_run_id = canonical_result.scalar_one_or_none()

    if best_run_id is None:
        return None

    # Step 2: Load the best run item
    run_stmt = (
        select(RunEvidenceItem)
        .where(RunEvidenceItem.run_evidence_item_id == best_run_id)
    )
    run_result = await self._session.execute(run_stmt)
    run_item = run_result.scalar_one_or_none()

    if run_item is None:
        return None

    # Step 3: Build TrackSpan from the run item
    return self._build_track_span(run_item, track)
```

Extract the span-building logic into a helper `_build_track_span(self, run_item, track) -> TrackSpan | None`.

**Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_source_linker.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/source_linker.py backend/tests/core/visualize_evidence_with_expert_in_loop/test_source_linker.py
git commit -m "fix(source_linker): use current_best_run_evidence_id instead of dead canonical FK"
```

---

## Task 3: Refactor `chat_service.py` to Use `current_best_run_evidence_id`

**Problem:** `chat_service.py` has 3 query sites using the dead `canonical_evidence_id` FK on `RunEvidenceItem`.

**Files:**
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py:217-248`
- Test: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py` (create if not exists)

**Step 1: Read the current implementation**

Read `backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py` — focus on `_build_evidence_context` (line 187+).

**Step 2: Write the failing test**

Create `backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py`:

```python
"""Tests for ChatService._build_evidence_context read path."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_build_evidence_context_uses_current_best_run_id() -> None:
    """_build_evidence_context resolves canonical → current_best_run_evidence_id → RunEvidenceItem."""
    from src.core.visualize_evidence_with_expert_in_loop.chat_service import ChatService

    session = MagicMock()
    canonical_id = uuid4()
    best_run_id = uuid4()

    # Mock canonical item
    mock_canonical = MagicMock()
    mock_canonical.canonical_evidence_id = canonical_id
    mock_canonical.active_payload = {"value": "BRCA1", "field_name": "Gene Symbol"}
    mock_canonical.current_best_run_evidence_id = best_run_id

    # Mock best run item (for source_span)
    mock_run = MagicMock()
    mock_run.source_span = {"text_snippet": "BRCA1 variant"}
    mock_run.run_evidence_item_id = best_run_id

    canonical_result = MagicMock()
    canonical_result.scalar_one_or_none.return_value = mock_canonical

    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = mock_run

    entity_result = MagicMock()
    entity_result.scalars.return_value.all.return_value = []

    session.execute = AsyncMock(side_effect=[canonical_result, run_result, entity_result])

    chat_svc = ChatService(session)
    context = await chat_svc._build_evidence_context(canonical_evidence_id=canonical_id)

    assert isinstance(context, str)
    assert "BRCA1" in context
```

**Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py -v`
Expected: FAIL

**Step 4: Refactor the 3 query sites in `_build_evidence_context`**

**Site A (entity lookup, lines 217-230):** Change from querying `RunEvidenceItem.canonical_evidence_id` to loading the canonical item first, then finding bindings through `current_best_run_evidence_id`:

```python
# Load canonical item
canonical_stmt = select(CanonicalEvidenceItem).where(
    CanonicalEvidenceItem.canonical_evidence_id == canonical_evidence_id
)
canonical_result = await self._session.execute(canonical_stmt)
canonical_item = canonical_result.scalar_one_or_none()
if canonical_item is None:
    return ""

best_run_id = canonical_item.current_best_run_evidence_id

# Entity lookup via best run item
if best_run_id:
    entity_stmt = (
        select(NormalizedEntity)
        .join(EvidenceEntityBinding, EvidenceEntityBinding.entity_id == NormalizedEntity.entity_id)
        .where(EvidenceEntityBinding.run_evidence_item_id == best_run_id)
    )
    entity_result = await self._session.execute(entity_stmt)
    entities = entity_result.scalars().all()
```

**Site B (source snippet, lines 241-248):** Use `best_run_id` directly:

```python
if best_run_id:
    run_stmt = select(RunEvidenceItem).where(
        RunEvidenceItem.run_evidence_item_id == best_run_id
    )
    run_result = await self._session.execute(run_stmt)
    best_run = run_result.scalar_one_or_none()
```

**Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py
git commit -m "fix(chat_service): use current_best_run_evidence_id instead of dead canonical FK"
```

---

## Task 4: Wire `frontend_search_index` Sync Into Write Paths

**Problem:** `SearchIndexRepository.refresh()` exists but is never called from production code. Both Phase 3 and Phase 4 feedback modify `canonical_evidence_items` without refreshing the search index, leaving it permanently stale.

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/repositories.py:882-887` — add `refresh_search_index` method
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/core.py:40` — call search index refresh
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/feedback_service.py:95` — call search index refresh after `_refresh_literature_profile`

**Step 1: Write the failing tests**

Add to `backend/tests/core/standardize_entities_and_align_knowledge/test_literature_profile_refresh.py`:

```python
@pytest.mark.asyncio
async def test_standardization_service_refreshes_search_index() -> None:
    """StandardizationService.run() triggers search index refresh."""
    # Same setup as existing test_standardization_service_refreshes_literature_profile
    from src.core.standardize_entities_and_align_knowledge.contracts import (
        MatchStatus, StandardizationInput, TerminologyMatch,
    )
    from src.core.standardize_entities_and_align_knowledge.core import StandardizationService

    matcher = AsyncMock()
    repository = AsyncMock()
    repository.ensure_run_parents = AsyncMock()
    repository.upsert_normalized_entity = AsyncMock(return_value=uuid4())
    repository.persist_run_evidence = AsyncMock()
    repository.persist_bindings = AsyncMock()
    repository.upsert_canonical_evidence = AsyncMock()
    repository.refresh_literature_profile = AsyncMock()
    repository.refresh_search_index = AsyncMock()
    matcher.match.return_value = TerminologyMatch(
        candidate_id="c1", status=MatchStatus.UNMAPPED, matched_entry=None, similarity_score=0.0,
    )

    service = StandardizationService(matcher=matcher, repository=repository)
    input_data = StandardizationInput(
        source_document_id=uuid4(), processing_run_id=uuid4(),
        document_id=uuid4(), candidates=[], track_payloads={},
    )
    await service.run(input_data)
    repository.refresh_search_index.assert_awaited_once()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/test_literature_profile_refresh.py -v`
Expected: FAIL — `refresh_search_index` not called

**Step 3: Add `refresh_search_index` to `StandardizationRepository`**

Add after `refresh_literature_profile` in `repositories.py`:

```python
async def refresh_search_index(self) -> None:
    """Refresh the frontend_search_index read model."""
    from src.dao.postgresql.search_index_repo import SearchIndexRepository

    index_repo = SearchIndexRepository(self._session)
    await index_repo.refresh()
```

**Step 4: Add call in `StandardizationService.run()`**

In `core.py`, add after line 40 (`refresh_literature_profile`):

```python
await self._repository.refresh_search_index()
```

**Step 5: Add search index refresh to `FeedbackService`**

In `feedback_service.py`, add after line 95 (`_refresh_literature_profile`):

```python
await self._refresh_search_index()
```

Add the method:

```python
async def _refresh_search_index(self) -> None:
    """Rebuild the frontend search index."""
    from src.dao.postgresql.search_index_repo import SearchIndexRepository

    index_repo = SearchIndexRepository(self._session)
    await index_repo.refresh()
```

**Step 6: Update FakeRepository stubs in existing tests**

Add `refresh_search_index = AsyncMock()` (or no-op stub) to `FakeRepository` in:
- `backend/tests/core/standardize_entities_and_align_knowledge/test_core.py`
- `backend/tests/core/standardize_entities_and_align_knowledge/test_integration.py`

**Step 7: Run all tests**

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/ tests/core/visualize_evidence_with_expert_in_loop/test_feedback_profile_refresh.py -v`
Expected: All PASS

**Step 8: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/repositories.py backend/src/core/standardize_entities_and_align_knowledge/core.py backend/src/core/visualize_evidence_with_expert_in_loop/feedback_service.py backend/tests/
git commit -m "fix(sync): wire frontend_search_index refresh into Phase 3 and Phase 4 feedback paths"
```

---

## Task 5: Document `evidence_groups` JSONB Schema in Model

**Problem:** `literature_profiles.evidence_groups` is a JSONB column with no documented schema. Its internal structure (produced by `_build_evidence_groups`) is implicit and will drift over time.

**Files:**
- Modify: `backend/src/dao/postgresql/models.py:120-123` — add schema docstring to `evidence_groups` field

**Step 1: Add schema documentation**

Replace the `evidence_groups` field definition with:

```python
    evidence_groups: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'")
    )
    # evidence_groups schema (produced by LiteratureProfileRepository._build_evidence_groups):
    # [
    #   {
    #     "group_id": str,           # Corresponds to active_payload.group_id
    #     "summary": {
    #       "gene": str | null,      # From A.gene_symbol / A.gene_aliases
    #       "variant": str | null,   # From A.variant_hgvs_c/p/g / A.variant_legacy_name
    #       "disease": str | null,   # From B.disease_diagnosis / B.clinical_diagnosis / B.hpo_terms
    #       "classification": str | null,  # From J.authority_classification / J.clinvar_assertion
    #     },
    #     "avg_confidence": float | null,
    #     "field_count": int,
    #     "review_status": str,      # "provisional" | "approved" | "corrected" | "rejected"
    #     "fields": [
    #       {
    #         "canonical_evidence_id": str,
    #         "field_id": str,
    #         "field_name": str | null,
    #         "category": str | null,
    #         "value": str | null,
    #         "confidence": float | null,
    #         "status": str | null,
    #         "track": str | null,   # "original" | "translated"
    #       }
    #     ]
    #   }
    # ]
```

**Step 2: Commit**

```bash
git add backend/src/dao/postgresql/models.py
git commit -m "docs(db): document evidence_groups JSONB schema on LiteratureProfile model"
```

---

## Task 6: Add `reviewed_unmappable` Status to `normalized_entities`

**Problem:** `standardization_status` only has `standardized` / `unmapped`. There's no way to distinguish "not yet processed" from "reviewed but genuinely unmappable" (e.g., novel variant not yet in ClinVar).

**Files:**
- Modify: `backend/src/dao/postgresql/models.py:205` — update default comment
- Create: `database/migrations/versions/2026-06-08_add_reviewed_unmappable_status.py`
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/contracts.py` — add status enum value

**Step 1: Create the Alembic migration**

```python
"""Add reviewed_unmappable to normalized_entities.standardization_status.

Revision ID: reviewed_unmappable_20260608
Revises: rm_canonical_fk_20260608
"""
from __future__ import annotations

from alembic import op

revision = "reviewed_unmappable_20260608"
down_revision = "rm_canonical_fk_20260608"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add the new value to the existing status column.
    # PostgreSQL allows adding enum values to VARCHAR columns without migration issues
    # since standardization_status is a plain String(32), not a PostgreSQL ENUM type.
    # No DDL change needed — the column already accepts any string.
    # Update the partial unique index to exclude reviewed_unmappable from the unmapped constraint.
    op.drop_index(
        "uq_normalized_entities_unmapped_raw_text",
        table_name="normalized_entities",
    )
    op.create_index(
        "uq_normalized_entities_unmapped_raw_text",
        "normalized_entities",
        ["entity_type", "normalized_raw_text"],
        unique=True,
        postgresql_where="standardization_status = 'unmapped'",
    )
    # Add a new partial unique index for reviewed_unmappable
    op.create_index(
        "uq_normalized_entities_reviewed_unmappable_raw_text",
        "normalized_entities",
        ["entity_type", "normalized_raw_text"],
        unique=True,
        postgresql_where="standardization_status = 'reviewed_unmappable'",
    )


def downgrade() -> None:
    op.drop_index(
        "uq_normalized_entities_reviewed_unmappable_raw_text",
        table_name="normalized_entities",
    )
```

**Step 2: Update the contracts if there's a MatchStatus enum**

Read `backend/src/core/standardize_entities_and_align_knowledge/contracts.py` to check if `MatchStatus` needs a new value. If `standardization_status` is just a string field (not an enum), no contract change is needed — just document the valid values.

**Step 3: Commit**

```bash
git add database/migrations/versions/2026-06-08_add_reviewed_unmappable_status.py backend/src/dao/postgresql/models.py
git commit -m "feat(db): add reviewed_unmappable status to normalized_entities"
```

---

## Task 7: Extract `pipeline_status` Column from `pipeline_run_states.state_json`

**Problem:** The expression index `(state_json ->> 'pipeline_status')` queries a JSON path inside a potentially large JSONB blob. Extracting `pipeline_status` as a dedicated column makes the crash-recovery query faster and more reliable.

**Files:**
- Modify: `backend/src/dao/postgresql/models.py:595-632` — add `pipeline_status` column
- Create: `database/migrations/versions/2026-06-08_extract_pipeline_status_column.py`
- Modify: `backend/src/agents/state_persistence.py` — sync `pipeline_status` on save

**Step 1: Create the Alembic migration**

```python
"""Extract pipeline_status as a dedicated column on pipeline_run_states.

Revision ID: extract_pipeline_status_20260608
Revises: reviewed_unmappable_20260608
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "extract_pipeline_status_20260608"
down_revision = "reviewed_unmappable_20260608"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pipeline_run_states",
        sa.Column("pipeline_status", sa.String(32), nullable=False, server_default="pending"),
    )
    op.add_column(
        "pipeline_run_states",
        sa.Column("last_completed_stage", sa.String(64), nullable=True),
    )
    # Backfill from existing state_json
    op.execute("""
        UPDATE pipeline_run_states
        SET pipeline_status = COALESCE(state_json ->> 'pipeline_status', 'pending')
    """)
    # Add a regular B-tree index
    op.create_index(
        "ix_pipeline_run_states_pipeline_status",
        "pipeline_run_states",
        ["pipeline_status"],
    )
    # Drop the old expression index
    op.drop_index(
        "ix_pipeline_run_states_pipeline_status_expr",
        table_name="pipeline_run_states",
    )


def downgrade() -> None:
    op.drop_index("ix_pipeline_run_states_pipeline_status", table_name="pipeline_run_states")
    op.drop_column("pipeline_run_states", "last_completed_stage")
    op.drop_column("pipeline_run_states", "pipeline_status")
```

**Step 2: Add `pipeline_status` column to the ORM model**

Add to `PipelineRunState` in `models.py`:

```python
    pipeline_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default=text("'pending'")
    )
    last_completed_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

Remove the old expression index from `__table_args__`:
```python
    # Remove this:
    Index(
        "ix_pipeline_run_states_pipeline_status",
        text("(state_json ->> 'pipeline_status')"),
    ),
```

Add a regular index:
```python
    Index("ix_pipeline_run_states_pipeline_status", "pipeline_status"),
```

**Step 3: Update `state_persistence.py` to sync `pipeline_status` on save**

Read `backend/src/agents/state_persistence.py` to find where `PipelineRunState` is created/updated. Add `pipeline_status=state.pipeline_status` and `last_completed_stage=...` to the save logic.

**Step 4: Commit**

```bash
git add backend/src/dao/postgresql/models.py database/migrations/versions/2026-06-08_extract_pipeline_status_column.py backend/src/agents/state_persistence.py
git commit -m "feat(db): extract pipeline_status as dedicated column on pipeline_run_states"
```

---

## Task 8: Update progress.txt

**Step 1: Append progress**

```
[2026-06-08] [Schema hardening: circular FK fix, search sync, status enum, column extraction] [done]
```

**Step 2: Commit**

```bash
git add progress.txt
git commit -m "docs: record schema hardening progress"
```

---

## File Change Summary

| Action | File | Task |
|--------|------|------|
| Modify | `backend/src/dao/postgresql/models.py` | 1, 5, 6, 7 |
| Create | `database/migrations/versions/2026-06-08_remove_run_evidence_canonical_fk.py` | 1 |
| Modify | `backend/src/core/visualize_evidence_with_expert_in_loop/source_linker.py` | 2 |
| Modify | `backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py` | 3 |
| Modify | `backend/src/core/standardize_entities_and_align_knowledge/repositories.py` | 4 |
| Modify | `backend/src/core/standardize_entities_and_align_knowledge/core.py` | 4 |
| Modify | `backend/src/core/visualize_evidence_with_expert_in_loop/feedback_service.py` | 4 |
| Create | `database/migrations/versions/2026-06-08_add_reviewed_unmappable_status.py` | 6 |
| Create | `database/migrations/versions/2026-06-08_extract_pipeline_status_column.py` | 7 |
| Modify | `backend/src/agents/state_persistence.py` | 7 |
| Create | `backend/tests/core/visualize_evidence_with_expert_in_loop/test_source_linker.py` | 2 |
| Create | `backend/tests/core/visualize_evidence_with_expert_in_loop/test_chat_service.py` | 3 |
| Modify | `backend/tests/core/standardize_entities_and_align_knowledge/test_literature_profile_refresh.py` | 4 |
| Modify | `backend/tests/core/standardize_entities_and_align_knowledge/test_core.py` | 4 |
| Modify | `backend/tests/core/standardize_entities_and_align_knowledge/test_integration.py` | 4 |
| Modify | `backend/tests/dao/postgresql/test_models.py` | 1 |

## Migration Chain

```
lit_profiles_20260608
  → rm_canonical_fk_20260608          (Task 1)
    → reviewed_unmappable_20260608    (Task 6)
      → extract_pipeline_status_20260608  (Task 7)
```

## Design Decisions

1. **Option A for circular FK** — Remove the dead column rather than populate it. The reverse pointer (`current_best_run_evidence_id`) already provides the needed linkage, and the dead FK was causing a real functional bug in source_linker and chat_service.

2. **Search index uses TRUNCATE+rebuild** — Same strategy as existing `SearchIndexRepository.refresh()`. This is correct for current scale. When data grows, switch to incremental upserts per document.

3. **`reviewed_unmappable` is a string value, not a PostgreSQL ENUM** — The column is already `String(32)`. Adding a new valid value doesn't require DDL changes, only documentation and a partial unique index.

4. **`pipeline_status` is backfilled from `state_json`** — The migration runs an UPDATE to populate the new column from existing data. No data loss.
