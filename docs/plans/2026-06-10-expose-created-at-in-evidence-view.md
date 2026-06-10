# Expose `created_at` in Evidence Fusion View

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expose the existing `created_at` timestamp from `canonical_evidence_items` through the full data pipeline — backend contracts, search index, API, frontend types, and table UI — so users can see when each evidence record was created.

**Architecture:** No new database columns on `canonical_evidence_items` (it already has `created_at` via `TimestampMixin`). We add a `created_at` column to `frontend_search_index` for the search-index path, update the `EvidenceSearchResult` / `LiteratureProfileSummary` contracts, propagate through `SearchService` and `LiteratureProfileRepository`, and display in the frontend `EvidenceResultsTable`. The `created_at` value flows as an ISO 8601 string through the API and is formatted as a locale date in the UI.

**Tech Stack:** Python, SQLAlchemy, Alembic, Pydantic, FastAPI, TypeScript, React, Next.js

---

### Task 1: Add `created_at` column to `frontend_search_index` table definition

**Files:**
- Modify: `backend/src/dao/postgresql/search_index_repo.py:38-62`

**Step 1: Write the failing test**

Open `backend/tests/dao/postgresql/test_search_index_repo.py` and add a test that asserts the `created_at` column exists on the table:

```python
def test_search_index_table_has_created_at_column():
    """The frontend_search_index table must expose a created_at column."""
    from src.dao.postgresql.search_index_repo import frontend_search_index

    col_names = [c.name for c in frontend_search_index.columns]
    assert "created_at" in col_names
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/dao/postgresql/test_search_index_repo.py::test_search_index_table_has_created_at_column -v`
Expected: FAIL with `assert 'created_at' in [...]`

**Step 3: Write minimal implementation**

In `backend/src/dao/postgresql/search_index_repo.py`, add the `created_at` column after the `active_payload` column (line 52). Import `DateTime` and `func` from SQLAlchemy:

Add `DateTime` and `func` to the existing imports (line 13-26):
```python
from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    cast,
    func,
    or_,
    select,
    text,
)
```

Add the column after `active_payload` (after line 52):
```python
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/dao/postgresql/test_search_index_repo.py::test_search_index_table_has_created_at_column -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/dao/postgresql/search_index_repo.py backend/tests/dao/postgresql/test_search_index_repo.py
git commit -m "feat: add created_at column to frontend_search_index table definition"
```

---

### Task 2: Alembic migration for `created_at` on `frontend_search_index`

**Files:**
- Create: `database/migrations/versions/2026-06-10_add_created_at_to_search_index.py`

**Step 1: Write the migration**

```python
"""Add created_at to frontend_search_index.

Revision ID: add_created_at_search_idx
Revises: <current_head>
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "add_created_at_search_idx"
down_revision = "<current_head>"  # Replace with actual head at execution time
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "frontend_search_index",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_column("frontend_search_index", "created_at")
```

> **Note:** At execution time, run `cd backend && uv run alembic heads` to find the current head revision and replace `<current_head>` accordingly.

**Step 2: Verify migration syntax**

Run: `cd backend && uv run alembic check`
Expected: No syntax errors (migration file is valid Python).

**Step 3: Commit**

```bash
git add database/migrations/versions/2026-06-10_add_created_at_to_search_index.py
git commit -m "feat: add created_at migration for frontend_search_index"
```

---

### Task 3: Update `refresh()` SQL to populate `created_at`

**Files:**
- Modify: `backend/src/dao/postgresql/search_index_repo.py:161-213`

**Step 1: Write the failing test**

In `backend/tests/dao/postgresql/test_search_index_repo.py`, add:

```python
def test_refresh_populates_created_at(monkeypatch):
    """refresh() should populate created_at from canonical_evidence_items."""
    from src.dao.postgresql.search_index_repo import frontend_search_index

    # Verify the refresh SQL includes created_at in both INSERT and SELECT.
    import src.dao.postgresql.search_index_repo as mod
    import inspect

    source = inspect.getsource(mod.SearchIndexRepository.refresh)
    assert "created_at" in source
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/dao/postgresql/test_search_index_repo.py::test_refresh_populates_created_at -v`
Expected: FAIL (the current `refresh()` method does not mention `created_at`).

**Step 3: Write minimal implementation**

In `backend/src/dao/postgresql/search_index_repo.py`, update the `refresh()` method's INSERT SQL (line 168-210):

Add `created_at` to the column list in the INSERT statement (after `active_payload`):
```sql
INSERT INTO frontend_search_index (
    canonical_evidence_id,
    pmid,
    doi,
    gene_ids,
    variant_ids,
    entity_ids,
    field_id,
    review_status,
    current_best_confidence,
    search_text,
    active_payload,
    created_at
)
```

Add `cei.created_at` to the SELECT list (after `cei.active_payload`):
```sql
    cei.active_payload,
    cei.created_at
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/dao/postgresql/test_search_index_repo.py::test_refresh_populates_created_at -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/dao/postgresql/search_index_repo.py backend/tests/dao/postgresql/test_search_index_repo.py
git commit -m "feat: populate created_at in search index refresh"
```

---

### Task 4: Add `created_at` to backend Pydantic contracts

**Files:**
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py:203-220` (EvidenceSearchResult)
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py:297-315` (LiteratureProfileSummary)

**Step 1: Write the failing test**

Create `backend/tests/core/visualize_evidence_with_expert_in_loop/test_contracts_created_at.py`:

```python
"""Tests for created_at field exposure in evidence contracts."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    EvidenceSearchResult,
    LiteratureProfileSummary,
)


def test_evidence_search_result_has_created_at():
    """EvidenceSearchResult must accept and expose a created_at field."""
    now = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
    result = EvidenceSearchResult(
        group_id="g1",
        source_document_id=uuid4(),
        created_at=now,
    )
    assert result.created_at == now


def test_evidence_search_result_created_at_optional():
    """created_at should be optional (backward compatible)."""
    result = EvidenceSearchResult(
        group_id="g1",
        source_document_id=uuid4(),
    )
    assert result.created_at is None


def test_literature_profile_summary_has_created_at():
    """LiteratureProfileSummary must accept and expose a created_at field."""
    now = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
    summary = LiteratureProfileSummary(
        literature_profile_id=uuid4(),
        source_document_id=uuid4(),
        created_at=now,
    )
    assert summary.created_at == now
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_contracts_created_at.py -v`
Expected: FAIL with `ValidationError: ... created_at ...`

**Step 3: Write minimal implementation**

In `backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py`:

Add to `EvidenceSearchResult` (after `canonical_evidence_id` on line 220):
```python
    created_at: datetime | None = None
```

Add to `LiteratureProfileSummary` (after `classification` on line 315):
```python
    created_at: datetime | None = None
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_contracts_created_at.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py backend/tests/core/visualize_evidence_with_expert_in_loop/test_contracts_created_at.py
git commit -m "feat: add created_at to EvidenceSearchResult and LiteratureProfileSummary"
```

---

### Task 5: Propagate `created_at` in `SearchService.search_evidence()`

**Files:**
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py:243-251` (SELECT clause)
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py:269-288` (group accumulator)
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py:353-369` (result construction)

**Step 1: Write the failing test**

In `backend/tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py`, add:

```python
@pytest.mark.asyncio
async def test_search_evidence_includes_created_at(session_with_data):
    """Search results must include created_at from canonical evidence."""
    from src.core.visualize_evidence_with_expert_in_loop.search_service import SearchService

    service = SearchService(session_with_data)
    response = await service.search_evidence()
    assert len(response.items) > 0
    assert response.items[0].created_at is not None
```

> **Note:** Adapt `session_with_data` to whatever fixture name the existing tests use. Check the existing test file for the fixture pattern.

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py::test_search_evidence_includes_created_at -v`
Expected: FAIL with `assert None is not None` (created_at not populated).

**Step 3: Write minimal implementation**

In `backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py`:

1. Add `CanonicalEvidenceItem.created_at` to the SELECT clause (line 246-251):
```python
        stmt = (
            select(
                CanonicalEvidenceItem.canonical_evidence_id,
                CanonicalEvidenceItem.source_document_id,
                CanonicalEvidenceItem.field_id,
                CanonicalEvidenceItem.review_status,
                CanonicalEvidenceItem.current_best_confidence,
                CanonicalEvidenceItem.active_payload,
                CanonicalEvidenceItem.created_at,
            )
        )
```

2. Store `created_at` in the group accumulator (inside the `if group_id not in groups:` block, around line 277-288):
```python
                groups[group_id] = {
                    "group_id": group_id,
                    "source_document_id": row.source_document_id,
                    "canonical_evidence_id": row.canonical_evidence_id,
                    "review_status": row.review_status,
                    "created_at": row.created_at,
                    "field_count": 0,
                    "confidences": [],
                    "gene": None,
                    "variant": None,
                    "disease": None,
                    "classification": None,
                }
```

3. Pass `created_at` to `EvidenceSearchResult` constructor (around line 353-369):
```python
            items.append(
                EvidenceSearchResult(
                    group_id=g["group_id"],
                    source_document_id=g["source_document_id"],
                    title=title_map.get(str(g["source_document_id"])),
                    pmid=doc_ident.get("pmid"),
                    doi=doc_ident.get("doi"),
                    gene=g["gene"],
                    variant=g["variant"],
                    disease=g["disease"],
                    classification=g["classification"],
                    field_count=g["field_count"],
                    avg_confidence=avg_conf,
                    review_status=g["review_status"],
                    canonical_evidence_id=g["canonical_evidence_id"],
                    created_at=g["created_at"],
                )
            )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py::test_search_evidence_includes_created_at -v`
Expected: PASS

**Step 5: Run all existing search service tests to confirm no regressions**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py -v`
Expected: All existing tests still PASS.

**Step 6: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py backend/tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py
git commit -m "feat: propagate created_at in SearchService.search_evidence()"
```

---

### Task 6: Propagate `created_at` in `LiteratureProfileRepository.search()`

**Files:**
- Modify: `backend/src/dao/postgresql/literature_profile_repo.py:406-436` (search result dict)

**Step 1: Write the failing test**

Create `backend/tests/dao/postgresql/test_literature_profile_created_at.py`:

```python
"""Tests for created_at exposure in literature profile search."""
from __future__ import annotations

import pytest


def test_literature_search_result_includes_created_at_key():
    """LiteratureProfileRepository.search() should include created_at in result dicts."""
    from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository
    import inspect

    source = inspect.getsource(LiteratureProfileRepository.search)
    assert '"created_at"' in source
```

**Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/dao/postgresql/test_literature_profile_created_at.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

In `backend/src/dao/postgresql/literature_profile_repo.py`, add `created_at` to the item dict in the `search()` method (after `"classification"` on line ~436):

```python
            items.append({
                ...existing keys...,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })
```

The full updated append block:
```python
            items.append({
                "literature_profile_id": str(row.literature_profile_id),
                "source_document_id": str(row.source_document_id),
                "pmid": row.pmid,
                "doi": row.doi,
                "title": row.title,
                "journal": row.journal,
                "publication_year": row.publication_year,
                "review_status": row.review_status,
                "overall_confidence": (
                    float(row.overall_confidence) if row.overall_confidence is not None else None
                ),
                "total_evidence_fields": row.total_evidence_fields,
                "found_count": row.found_count,
                "evidence_group_count": len(eg),
                "gene": merged["gene"],
                "variant": merged["variant"],
                "disease": merged["disease"],
                "classification": merged["classification"],
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })
```

**Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/dao/postgresql/test_literature_profile_created_at.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/dao/postgresql/literature_profile_repo.py backend/tests/dao/postgresql/test_literature_profile_created_at.py
git commit -m "feat: expose created_at in LiteratureProfileRepository.search()"
```

---

### Task 7: Add `created_at` to frontend TypeScript types

**Files:**
- Modify: `frontend/src/features/evidence-search/types/evidenceSearch.ts:15-29` (EvidenceSearchResult)

**Step 1: Write the failing test**

In `frontend/tests/evidence-search/literatureRows.test.ts`, add:

```typescript
it("propagates created_at from search result to literature row", () => {
  const results: EvidenceSearchResult[] = [
    {
      group_id: "g1",
      source_document_id: "doc-1",
      field_count: 1,
      review_status: "provisional",
      created_at: "2026-06-10T12:00:00Z",
    },
  ];
  const rows = buildLiteratureRows(results);
  expect(rows[0].createdAt).toBe("2026-06-10T12:00:00Z");
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/evidence-search/literatureRows.test.ts`
Expected: FAIL — `createdAt` not on row or result type.

**Step 3: Write minimal implementation**

In `frontend/src/features/evidence-search/types/evidenceSearch.ts`, add to `EvidenceSearchResult` (after `canonical_evidence_id` on line 29):

```typescript
  created_at?: string | null;
```

In `frontend/src/features/evidence-search/utils/literatureRows.ts`, add to `LiteratureEvidenceRow` (after `reviewStatus` on line 20):

```typescript
  createdAt?: string | null;
```

In the `buildLiteratureRows` function, propagate `created_at` when building the initial row (inside the `if (!row)` block, around line 56-74):

```typescript
      row = {
        documentId,
        representativeGroupId: item.group_id,
        title: item.title,
        pmid: item.pmid,
        doi: item.doi,
        genes: [],
        variants: [],
        diseases: [],
        classifications: [],
        fieldCount: 0,
        groupCount: 0,
        avgConfidence: null,
        reviewStatus: "unknown",
        createdAt: item.created_at ?? null,
        confidenceTotal: 0,
        confidenceWeight: 0,
        statuses: new Set<string>(),
      };
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/evidence-search/literatureRows.test.ts`
Expected: PASS (all tests including the new one).

**Step 5: Commit**

```bash
git add frontend/src/features/evidence-search/types/evidenceSearch.ts frontend/src/features/evidence-search/utils/literatureRows.ts frontend/tests/evidence-search/literatureRows.test.ts
git commit -m "feat: add created_at to frontend evidence types and row builder"
```

---

### Task 8: Display `created_at` in `EvidenceResultsTable` UI

**Files:**
- Modify: `frontend/src/features/evidence-search/components/EvidenceResultsTable.tsx`

**Step 1: Add a date formatting helper**

Add near the top of the file (after `formatPercent` on line 43):

```typescript
function formatDate(isoString?: string | null) {
  if (!isoString) {
    return "—";
  }
  try {
    return new Date(isoString).toLocaleDateString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  } catch {
    return "—";
  }
}
```

**Step 2: Add `Created` column to the desktop table**

In the `<thead>` (around line 211-218), add a new column header. Adjust widths to accommodate:

```tsx
              <th className="w-[20%] px-4 py-3">Literature</th>
              <th className="w-[18%] px-4 py-3">Evidence Focus</th>
              <th className="w-[16%] px-4 py-3">Disease</th>
              <th className="w-[14%] px-4 py-3">Classification</th>
              <th className="w-[10%] px-4 py-3">Created</th>
              <th className="w-[10%] px-4 py-3">Review</th>
              <th className="w-[8%] px-4 py-3 text-right">Fields</th>
```

Add the `<td>` cell in the table body, after the Classification cell (around line 269):

```tsx
                <td className="px-4 py-4 align-top text-xs text-gray-500">
                  {formatDate(row.createdAt)}
                </td>
```

**Step 3: Add date info to mobile card view**

In the mobile card footer grid (around line 199-203), change from 3 columns to 4 and add date:

```tsx
            <div className="mt-4 grid grid-cols-4 gap-2 border-t border-gray-100 pt-3 text-xs text-gray-500">
              <span>{row.groupCount} group{row.groupCount !== 1 ? "s" : ""}</span>
              <span>{row.fieldCount} fields</span>
              <span>{formatPercent(row.avgConfidence)}</span>
              <span>{formatDate(row.createdAt)}</span>
            </div>
```

**Step 4: Manually verify in browser**

Run: `cd frontend && npm run dev`
Navigate to the evidence search page and confirm the "Created" column displays formatted dates.

**Step 5: Commit**

```bash
git add frontend/src/features/evidence-search/components/EvidenceResultsTable.tsx
git commit -m "feat: display created_at date in evidence results table"
```

---

### Task 9: Run full test suite and verify

**Step 1: Run all backend tests**

Run: `cd backend && uv run pytest -v`
Expected: All tests PASS (no regressions).

**Step 2: Run all frontend tests**

Run: `cd frontend && npx vitest run`
Expected: All tests PASS.

**Step 3: Run linting**

Run: `cd backend && uv run ruff check`
Run: `cd frontend && npm run lint`
Expected: No errors.

**Step 4: Final commit if any fixups needed**

```bash
git add -A
git commit -m "chore: fix lint issues from created_at exposure"
```
