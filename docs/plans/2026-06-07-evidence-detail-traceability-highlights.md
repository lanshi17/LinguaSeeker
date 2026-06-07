# Evidence Detail Traceability Highlights Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a clickable Evidence detail flow where each search result opens a detail page showing evidence-item distribution, original/translated evidence-chain traceability, and highlighted spans for each evidence item.

**Architecture:** Keep the frontend scope inside the existing Evidence module only. Backend stays in Phase 4 vertical slice: `api/v1` routes delegate to `core/visualize_evidence_with_expert_in_loop`, which queries `canonical_evidence_items`, `run_evidence_items`, `source_document_identifiers`, and optional entity bindings with typed Pydantic contracts. The detail page uses the search row `group_id` as the aggregate key and existing `canonical_evidence_id` values as drill-down anchors for source linking.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic, PostgreSQL JSONB, pytest; Next.js App Router, React 18, TypeScript, React Query, Axios, Tailwind, lucide-react.

---

## Current State Notes

- Frontend has only two product modules: Chat and Evidence. Do not add a Dashboard module.
- Evidence search rows are currently pivoted from `canonical_evidence_items.active_payload['group_id']` and paginated.
- Existing source-link endpoint works per canonical evidence item: `GET /api/v1/source-link/{canonical_evidence_id}/bilingual`.
- Existing source linker only returns one original span and one translated span for a single evidence item. Detail needs a group-level aggregate view for all evidence items under one `group_id`.
- Source span data currently comes from `run_evidence_items.source_span`, with fallback text in `text_snippet`, `start_offset`, `end_offset`, and `page`.

## Success Criteria

1. Evidence search table rows are clickable.
2. Clicking a row opens `/evidence/[groupId]` without adding a new frontend module.
3. Detail page fetches `GET /api/v1/evidence/groups/{group_id}`.
4. Backend returns a typed group detail response with summary fields, item distribution, evidence items, and bilingual trace spans.
5. Detail page shows distribution by category/field/status/track.
6. Detail page shows original and translated evidence-chain panes with highlights.
7. Each evidence item can be selected; selected item highlights in distribution, item list, and source panes.
8. Pagination on the list page remains intact.
9. No raw `dict` return annotations are introduced in backend function signatures.
10. Tests cover backend contracts, service aggregation, route wiring, and frontend type-check/build.

---

### Task 1: Add Backend Detail Contracts

**Files:**
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py`
- Test: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_contracts.py`

**Step 1: Write failing contract tests**

Append tests to `backend/tests/core/visualize_evidence_with_expert_in_loop/test_contracts.py`:

```python
from uuid import uuid4

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    EvidenceChainHighlight,
    EvidenceFieldDistribution,
    EvidenceGroupDetailResponse,
    EvidenceGroupItem,
    EvidenceTrackTrace,
)


def test_evidence_group_detail_contract_accepts_traceability_payload():
    evidence_id = uuid4()
    source_document_id = uuid4()

    detail = EvidenceGroupDetailResponse(
        group_id="gene=['BRCA1']|variant=['c.68_69delAG']",
        source_document_id=source_document_id,
        pmid="12345678",
        doi="10.1000/example",
        gene="BRCA1",
        variant="c.68_69delAG",
        disease="Hereditary breast and ovarian cancer",
        classification="Pathogenic",
        item_count=1,
        avg_confidence=0.95,
        distribution=EvidenceFieldDistribution(
            by_category={"A": 1},
            by_field={"A.gene_symbol": 1},
            by_status={"provisional": 1},
            by_track={"original": 1},
        ),
        items=[
            EvidenceGroupItem(
                canonical_evidence_id=evidence_id,
                field_id="A.gene_symbol",
                field_name="Gene symbol",
                category="A",
                value="BRCA1",
                review_status="provisional",
                confidence=0.95,
                track="original",
            )
        ],
        traces=[
            EvidenceTrackTrace(
                canonical_evidence_id=evidence_id,
                field_id="A.gene_symbol",
                field_name="Gene symbol",
                original=EvidenceChainHighlight(
                    text="BRCA1 was detected.",
                    highlight_start=0,
                    highlight_end=5,
                    page=1,
                    source_span={"text_snippet": "BRCA1 was detected."},
                ),
                translated=None,
                alignment_confidence=None,
            )
        ],
    )

    dumped = detail.model_dump()
    assert dumped["group_id"].startswith("gene=")
    assert dumped["distribution"]["by_category"] == {"A": 1}
    assert dumped["traces"][0]["original"]["highlight_start"] == 0
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_contracts.py::test_evidence_group_detail_contract_accepts_traceability_payload -v
```

Expected: FAIL with import error for missing classes.

**Step 3: Add Pydantic contracts**

Append after `EvidenceSearchResponse` in `backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py`:

```python
class EvidenceFieldDistribution(BaseModel):
    """Distribution counts for one grouped evidence row."""

    by_category: dict[str, int] = Field(default_factory=dict)
    by_field: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_track: dict[str, int] = Field(default_factory=dict)


class EvidenceGroupItem(BaseModel):
    """One field-level evidence item in a grouped evidence detail view."""

    canonical_evidence_id: UUID
    field_id: str
    field_name: str | None = None
    category: str | None = None
    value: str | None = None
    review_status: str
    confidence: float | None = None
    track: str | None = None
    page: int | None = None


class EvidenceChainHighlight(BaseModel):
    """Highlightable source text for an evidence item on one track."""

    text: str
    highlight_start: int
    highlight_end: int
    page: int | None = None
    source_span: SourceSpanDict = Field(default_factory=dict)


class EvidenceTrackTrace(BaseModel):
    """Original/translated trace pair for one evidence item."""

    canonical_evidence_id: UUID
    field_id: str
    field_name: str | None = None
    original: EvidenceChainHighlight | None = None
    translated: EvidenceChainHighlight | None = None
    alignment_confidence: float | None = None


class EvidenceGroupDetailResponse(BaseModel):
    """Detail payload for one grouped evidence row."""

    group_id: str
    source_document_id: UUID
    pmid: str | None = None
    doi: str | None = None
    gene: str | None = None
    variant: str | None = None
    disease: str | None = None
    classification: str | None = None
    item_count: int
    avg_confidence: float | None = None
    distribution: EvidenceFieldDistribution
    items: list[EvidenceGroupItem]
    traces: list[EvidenceTrackTrace]
```

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_contracts.py::test_evidence_group_detail_contract_accepts_traceability_payload -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py backend/tests/core/visualize_evidence_with_expert_in_loop/test_contracts.py
git commit -m "feat: add evidence group detail contracts"
```

---

### Task 2: Add Group Detail Service Method

**Files:**
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py`
- Test: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py`

**Step 1: Create failing service tests**

Create `backend/tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py` if missing:

```python
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.core.visualize_evidence_with_expert_in_loop.search_service import SearchService


class _FakeScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _FakeResult:
    def __init__(self, rows=None, scalars=None):
        self._rows = rows or []
        self._scalars = scalars or []

    def all(self):
        return self._rows

    def scalars(self):
        return _FakeScalarResult(self._scalars)


class _FakeSession:
    def __init__(self, results):
        self._results = list(results)

    async def execute(self, _stmt):
        return self._results.pop(0)


@pytest.mark.asyncio
async def test_get_group_detail_pivots_distribution_and_traces():
    source_document_id = uuid4()
    gene_evidence_id = uuid4()
    disease_evidence_id = uuid4()
    group_id = "gene=['BRCA1']|variant=['c.68_69delAG']"

    rows = [
        SimpleNamespace(
            canonical_evidence_id=gene_evidence_id,
            source_document_id=source_document_id,
            field_id="A.gene_symbol",
            review_status="provisional",
            current_best_confidence=Decimal("0.9500"),
            active_payload={
                "group_id": group_id,
                "field_name": "Gene symbol",
                "category": "A",
                "value": ["BRCA1"],
                "track": "original",
            },
        ),
        SimpleNamespace(
            canonical_evidence_id=disease_evidence_id,
            source_document_id=source_document_id,
            field_id="B.disease_diagnosis",
            review_status="approved",
            current_best_confidence=Decimal("0.9000"),
            active_payload={
                "group_id": group_id,
                "field_name": "Disease diagnosis",
                "category": "B",
                "value": "Hereditary breast and ovarian cancer",
                "track": "translated",
            },
        ),
    ]
    identifiers = [
        SimpleNamespace(source_document_id=source_document_id, identifier_type="pmid", identifier_value="12345678"),
        SimpleNamespace(source_document_id=source_document_id, identifier_type="doi", identifier_value="10.1000/example"),
    ]
    run_items = [
        SimpleNamespace(
            canonical_evidence_id=gene_evidence_id,
            field_id="A.gene_symbol",
            track="original",
            source_span={
                "text_snippet": "BRCA1 was detected in the proband.",
                "start_offset": 0,
                "end_offset": 5,
                "page": 1,
            },
        ),
        SimpleNamespace(
            canonical_evidence_id=disease_evidence_id,
            field_id="B.disease_diagnosis",
            track="translated",
            source_span={
                "text_snippet": "诊断为遗传性乳腺卵巢癌。",
                "start_offset": 3,
                "end_offset": 13,
                "page": 2,
            },
        ),
    ]

    service = SearchService(_FakeSession([
        _FakeResult(rows=rows),
        _FakeResult(scalars=identifiers),
        _FakeResult(scalars=run_items),
    ]))

    detail = await service.get_group_detail(group_id=group_id)

    assert detail.group_id == group_id
    assert detail.gene == "BRCA1"
    assert detail.disease == "Hereditary breast and ovarian cancer"
    assert detail.pmid == "12345678"
    assert detail.distribution.by_category == {"A": 1, "B": 1}
    assert detail.distribution.by_status == {"provisional": 1, "approved": 1}
    assert detail.item_count == 2
    assert detail.traces[0].original is not None
    assert detail.traces[1].translated is not None
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py::test_get_group_detail_pivots_distribution_and_traces -v
```

Expected: FAIL with `AttributeError: 'SearchService' object has no attribute 'get_group_detail'`.

**Step 3: Implement service helpers and method**

Modify `backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py`:

- Remove unused `func` import if still unused.
- Import contracts:

```python
from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    EvidenceChainHighlight,
    EvidenceFieldDistribution,
    EvidenceGroupDetailResponse,
    EvidenceGroupItem,
    EvidenceSearchResponse,
    EvidenceSearchResult,
    EvidenceTrackTrace,
)
from src.dao.postgresql.models import (
    CanonicalEvidenceItem,
    RunEvidenceItem,
    SourceDocumentIdentifier,
)
```

Add helper functions near `_coerce_str`:

```python
def _category_from_field_id(field_id: str) -> str | None:
    if "." not in field_id:
        return field_id or None
    return field_id.split(".", 1)[0]


def _build_highlight(source_span: dict[str, object]) -> EvidenceChainHighlight | None:  # noqa: dict-return
    if not source_span:
        return None
    text = str(source_span.get("text_snippet") or "")
    start = int(source_span.get("start_offset") or 0)
    raw_end = source_span.get("end_offset")
    end = int(raw_end) if raw_end is not None and int(raw_end) >= start else len(text)
    return EvidenceChainHighlight(
        text=text,
        highlight_start=max(start, 0),
        highlight_end=min(end, len(text)) if text else max(end, 0),
        page=source_span.get("page") if isinstance(source_span.get("page"), int) else None,
        source_span=source_span,
    )
```

Add method inside `SearchService`:

```python
    async def get_group_detail(self, *, group_id: str) -> EvidenceGroupDetailResponse:
        """Return detail payload for one grouped evidence row."""
        stmt = (
            select(
                CanonicalEvidenceItem.canonical_evidence_id,
                CanonicalEvidenceItem.source_document_id,
                CanonicalEvidenceItem.field_id,
                CanonicalEvidenceItem.review_status,
                CanonicalEvidenceItem.current_best_confidence,
                CanonicalEvidenceItem.active_payload,
            )
            .where(CanonicalEvidenceItem.active_payload["group_id"].astext == group_id)
            .order_by(CanonicalEvidenceItem.field_id)
        )
        result = await self._session.execute(stmt)
        rows = result.all()
        if not rows:
            raise NoResultFound()

        source_document_id = rows[0].source_document_id
        canonical_ids = [row.canonical_evidence_id for row in rows]

        ident_stmt = select(SourceDocumentIdentifier).where(
            SourceDocumentIdentifier.source_document_id == source_document_id
        )
        ident_result = await self._session.execute(ident_stmt)
        identifiers = {
            ident.identifier_type: ident.identifier_value
            for ident in ident_result.scalars().all()
        }

        trace_stmt = select(RunEvidenceItem).where(
            RunEvidenceItem.canonical_evidence_id.in_(canonical_ids)
        )
        trace_result = await self._session.execute(trace_stmt)
        run_items = trace_result.scalars().all()

        trace_by_evidence: dict[object, dict[str, RunEvidenceItem]] = {}
        for item in run_items:
            trace_by_evidence.setdefault(item.canonical_evidence_id, {})[item.track] = item

        distribution = EvidenceFieldDistribution()
        detail_items: list[EvidenceGroupItem] = []
        traces: list[EvidenceTrackTrace] = []
        confidences: list[float] = []
        gene = variant = disease = classification = None

        for row in rows:
            payload = row.active_payload or {}
            value = _coerce_str(payload.get("value"))
            field_id = row.field_id
            field_name = payload.get("field_name")
            category = payload.get("category") or _category_from_field_id(field_id)
            track = payload.get("track")
            confidence = float(row.current_best_confidence) if row.current_best_confidence is not None else None
            if confidence is not None:
                confidences.append(confidence)

            if category:
                distribution.by_category[category] = distribution.by_category.get(category, 0) + 1
            distribution.by_field[field_id] = distribution.by_field.get(field_id, 0) + 1
            distribution.by_status[row.review_status] = distribution.by_status.get(row.review_status, 0) + 1
            if track:
                distribution.by_track[track] = distribution.by_track.get(track, 0) + 1

            if field_id in _GENE_FIELDS and not gene:
                gene = value
            elif field_id in _VARIANT_FIELDS and not variant:
                variant = value
            elif field_id in _DISEASE_FIELDS and not disease:
                disease = value
            elif field_id in _CLASSIFICATION_FIELDS and not classification:
                classification = value

            detail_items.append(
                EvidenceGroupItem(
                    canonical_evidence_id=row.canonical_evidence_id,
                    field_id=field_id,
                    field_name=str(field_name) if field_name else None,
                    category=str(category) if category else None,
                    value=value,
                    review_status=row.review_status,
                    confidence=confidence,
                    track=str(track) if track else None,
                    page=(payload.get("source") or {}).get("page") if isinstance(payload.get("source"), dict) else None,
                )
            )

            traces_for_item = trace_by_evidence.get(row.canonical_evidence_id, {})
            original = _build_highlight(traces_for_item["original"].source_span) if "original" in traces_for_item else None
            translated = _build_highlight(traces_for_item["translated"].source_span) if "translated" in traces_for_item else None
            traces.append(
                EvidenceTrackTrace(
                    canonical_evidence_id=row.canonical_evidence_id,
                    field_id=field_id,
                    field_name=str(field_name) if field_name else None,
                    original=original,
                    translated=translated,
                    alignment_confidence=1.0 if original and translated else None,
                )
            )

        return EvidenceGroupDetailResponse(
            group_id=group_id,
            source_document_id=source_document_id,
            pmid=identifiers.get("pmid"),
            doi=identifiers.get("doi"),
            gene=gene,
            variant=variant,
            disease=disease,
            classification=classification,
            item_count=len(detail_items),
            avg_confidence=(sum(confidences) / len(confidences)) if confidences else None,
            distribution=distribution,
            items=detail_items,
            traces=traces,
        )
```

Also import `NoResultFound`:

```python
from sqlalchemy.exc import NoResultFound
```

**Step 4: Run service test**

Run:

```bash
cd backend
uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py::test_get_group_detail_pivots_distribution_and_traces -v
```

Expected: PASS.

**Step 5: Run existing source-link tests for regression**

Run:

```bash
cd backend
uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_source_linker.py tests/api/test_source_link_api.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py backend/tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py
git commit -m "feat: aggregate evidence group detail"
```

---

### Task 3: Add Group Detail API Route

**Files:**
- Modify: `backend/src/api/v1/evidence.py`
- Test: `backend/tests/api/test_evidence_api.py`

**Step 1: Write failing route tests**

Append to `backend/tests/api/test_evidence_api.py`:

```python
@pytest.mark.asyncio
async def test_get_evidence_group_detail(async_client: AsyncClient):
    """GET /api/v1/evidence/groups/{group_id} returns grouped evidence detail."""
    from src.core.visualize_evidence_with_expert_in_loop.contracts import (
        EvidenceFieldDistribution,
        EvidenceGroupDetailResponse,
    )

    source_document_id = uuid4()
    group_id = "gene=['BRCA1']|variant=['c.68_69delAG']"
    mock_response = EvidenceGroupDetailResponse(
        group_id=group_id,
        source_document_id=source_document_id,
        gene="BRCA1",
        variant="c.68_69delAG",
        disease="Hereditary breast and ovarian cancer",
        classification="Pathogenic",
        item_count=0,
        avg_confidence=None,
        distribution=EvidenceFieldDistribution(),
        items=[],
        traces=[],
    )

    with patch("src.api.v1.evidence.SearchService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.get_group_detail = AsyncMock(return_value=mock_response)
        mock_service_cls.return_value = mock_service

        response = await async_client.get(f"/api/v1/evidence/groups/{group_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["group_id"] == group_id
    assert data["gene"] == "BRCA1"


@pytest.mark.asyncio
async def test_get_evidence_group_detail_returns_404(async_client: AsyncClient):
    """GET /api/v1/evidence/groups/{group_id} returns 404 when group is missing."""
    from sqlalchemy.exc import NoResultFound

    with patch("src.api.v1.evidence.SearchService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.get_group_detail = AsyncMock(side_effect=NoResultFound())
        mock_service_cls.return_value = mock_service

        response = await async_client.get("/api/v1/evidence/groups/missing-group")

    assert response.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/api/test_evidence_api.py::test_get_evidence_group_detail tests/api/test_evidence_api.py::test_get_evidence_group_detail_returns_404 -v
```

Expected: FAIL with route not found or missing service method.

**Step 3: Add route before `/{canonical_evidence_id}` patch route**

Modify imports in `backend/src/api/v1/evidence.py`:

```python
from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    EvidenceGroupDetailResponse,
    EvidencePatchRequest,
    EvidenceSearchResponse,
    PatchResultResponse,
)
```

Add route above the `@router.patch("/{canonical_evidence_id}"...)` route to avoid path ambiguity:

```python
@router.get("/groups/{group_id}", response_model=EvidenceGroupDetailResponse)
async def get_evidence_group_detail(
    group_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> EvidenceGroupDetailResponse:
    """Return grouped evidence detail with distribution and traceability."""
    service = SearchService(session)
    try:
        return await service.get_group_detail(group_id=group_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Evidence group not found")
```

**Step 4: Run API tests**

Run:

```bash
cd backend
uv run pytest tests/api/test_evidence_api.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/api/v1/evidence.py backend/tests/api/test_evidence_api.py
git commit -m "feat: expose evidence group detail api"
```

---

### Task 4: Add Frontend Detail Types and API Client

**Files:**
- Modify: `frontend/src/features/evidence-search/types/evidenceSearch.ts`
- Modify: `frontend/src/features/evidence-search/services/evidenceSearch.ts`
- Modify: `frontend/src/features/evidence-search/index.ts`

**Step 1: Add frontend type definitions**

Modify `frontend/src/features/evidence-search/types/evidenceSearch.ts` and append:

```typescript
export interface EvidenceFieldDistribution {
  by_category: Record<string, number>;
  by_field: Record<string, number>;
  by_status: Record<string, number>;
  by_track: Record<string, number>;
}

export interface EvidenceGroupItem {
  canonical_evidence_id: string;
  field_id: string;
  field_name?: string | null;
  category?: string | null;
  value?: string | null;
  review_status: string;
  confidence?: number | null;
  track?: string | null;
  page?: number | null;
}

export interface EvidenceChainHighlight {
  text: string;
  highlight_start: number;
  highlight_end: number;
  page?: number | null;
  source_span: Record<string, unknown>;
}

export interface EvidenceTrackTrace {
  canonical_evidence_id: string;
  field_id: string;
  field_name?: string | null;
  original?: EvidenceChainHighlight | null;
  translated?: EvidenceChainHighlight | null;
  alignment_confidence?: number | null;
}

export interface EvidenceGroupDetailResponse {
  group_id: string;
  source_document_id: string;
  pmid?: string | null;
  doi?: string | null;
  gene?: string | null;
  variant?: string | null;
  disease?: string | null;
  classification?: string | null;
  item_count: number;
  avg_confidence?: number | null;
  distribution: EvidenceFieldDistribution;
  items: EvidenceGroupItem[];
  traces: EvidenceTrackTrace[];
}
```

**Step 2: Add API client function**

Modify `frontend/src/features/evidence-search/services/evidenceSearch.ts`:

```typescript
import type {
  EvidenceGroupDetailResponse,
  EvidenceSearchQuery,
  EvidenceSearchResponse,
} from "../types/evidenceSearch";

export async function getEvidenceGroupDetail(
  groupId: string,
): Promise<EvidenceGroupDetailResponse> {
  const { data } = await apiClient.get<EvidenceGroupDetailResponse>(
    `/evidence/groups/${encodeURIComponent(groupId)}`,
  );
  return data;
}
```

**Step 3: Export types**

Modify `frontend/src/features/evidence-search/index.ts` to export the new types:

```typescript
export type {
  EvidenceChainHighlight,
  EvidenceFieldDistribution,
  EvidenceGroupDetailResponse,
  EvidenceGroupItem,
  EvidenceSearchQuery,
  EvidenceSearchResult,
  EvidenceSearchResponse,
  EvidenceTrackTrace,
} from "./types/evidenceSearch";
```

**Step 4: Run type check**

Run:

```bash
cd frontend
npm run type-check
```

Expected: PASS except any unrelated pre-existing `ChatView.tsx` duplicate identifier error. If that unrelated error exists, run:

```bash
cd frontend
npx tsc --noEmit -p tsconfig.json 2>&1 | grep -v "ChatView.tsx"
```

Expected: no output.

**Step 5: Commit**

```bash
git add frontend/src/features/evidence-search/types/evidenceSearch.ts frontend/src/features/evidence-search/services/evidenceSearch.ts frontend/src/features/evidence-search/index.ts
git commit -m "feat: add evidence detail frontend contracts"
```

---

### Task 5: Add Detail Hook

**Files:**
- Create: `frontend/src/features/evidence-search/hooks/useEvidenceGroupDetail.ts`
- Modify: `frontend/src/features/evidence-search/index.ts`

**Step 1: Create hook**

Create `frontend/src/features/evidence-search/hooks/useEvidenceGroupDetail.ts`:

```typescript
"use client";

import { useQuery } from "@tanstack/react-query";
import { getEvidenceGroupDetail } from "../services/evidenceSearch";

export function useEvidenceGroupDetail(groupId: string) {
  const query = useQuery({
    queryKey: ["evidence", "group-detail", groupId],
    queryFn: () => getEvidenceGroupDetail(groupId),
    enabled: !!groupId,
  });

  return {
    detail: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    refetch: query.refetch,
  };
}
```

**Step 2: Export hook**

Modify `frontend/src/features/evidence-search/index.ts`:

```typescript
export { useEvidenceGroupDetail } from "./hooks/useEvidenceGroupDetail";
```

**Step 3: Type check**

Run:

```bash
cd frontend
npx tsc --noEmit -p tsconfig.json 2>&1 | grep -v "ChatView.tsx"
```

Expected: no output.

**Step 4: Commit**

```bash
git add frontend/src/features/evidence-search/hooks/useEvidenceGroupDetail.ts frontend/src/features/evidence-search/index.ts
git commit -m "feat: add evidence group detail hook"
```

---

### Task 6: Make Search Rows Navigate to Detail Page

**Files:**
- Modify: `frontend/src/features/evidence-search/components/EvidenceResultsTable.tsx`

**Step 1: Add navigation prop**

Modify props:

```typescript
interface EvidenceResultsTableProps {
  results: EvidenceSearchResult[];
  total: number;
  page: number;
  pageSize: number;
  isLoading?: boolean;
  onPageChange?: (page: number) => void;
  onRowClick?: (item: EvidenceSearchResult) => void;
}
```

Destructure `onRowClick` and update `<tr>`:

```tsx
<tr
  key={item.group_id}
  onClick={() => onRowClick?.(item)}
  className="cursor-pointer transition-colors hover:bg-gray-50"
>
```

**Step 2: Wire router in `EvidenceSearchView`**

Modify `frontend/src/features/evidence-search/components/EvidenceSearchView.tsx`:

```typescript
import { useRouter } from "next/navigation";
```

Inside component:

```typescript
const router = useRouter();
```

Pass callback:

```tsx
onRowClick={(item) => {
  router.push(`/evidence/${encodeURIComponent(item.group_id)}`);
}}
```

**Step 3: Type check**

Run:

```bash
cd frontend
npx tsc --noEmit -p tsconfig.json 2>&1 | grep -v "ChatView.tsx"
```

Expected: no output.

**Step 4: Manual browser check**

Run frontend dev server if needed:

```bash
cd frontend
nvm use
npm run dev
```

Open `/evidence`, click a row. Expected: browser navigates to `/evidence/<encoded-group-id>` and shows Next.js 404 until Task 9 creates the page.

**Step 5: Commit**

```bash
git add frontend/src/features/evidence-search/components/EvidenceResultsTable.tsx frontend/src/features/evidence-search/components/EvidenceSearchView.tsx
git commit -m "feat: make evidence rows navigable"
```

---

### Task 7: Add Highlight Renderer Component

**Files:**
- Create: `frontend/src/features/evidence-search/components/EvidenceHighlightText.tsx`
- Modify: `frontend/src/features/evidence-search/index.ts`

**Step 1: Create component**

Create `frontend/src/features/evidence-search/components/EvidenceHighlightText.tsx`:

```tsx
"use client";

import type { EvidenceChainHighlight } from "../types/evidenceSearch";

interface EvidenceHighlightTextProps {
  highlight?: EvidenceChainHighlight | null;
  active?: boolean;
}

export function EvidenceHighlightText({
  highlight,
  active = false,
}: EvidenceHighlightTextProps) {
  if (!highlight || !highlight.text) {
    return <p className="text-sm text-gray-400">No source span available.</p>;
  }

  const start = Math.max(0, Math.min(highlight.highlight_start, highlight.text.length));
  const end = Math.max(start, Math.min(highlight.highlight_end, highlight.text.length));
  const before = highlight.text.slice(0, start);
  const marked = highlight.text.slice(start, end);
  const after = highlight.text.slice(end);

  return (
    <div className="rounded-md border border-gray-200 bg-white p-3 text-sm leading-6 text-gray-700">
      <div className="mb-2 text-xs text-gray-400">
        Page {highlight.page ?? "—"}
      </div>
      <p className="whitespace-pre-wrap">
        {before}
        <mark
          className={
            active
              ? "rounded bg-amber-200 px-0.5 text-gray-950"
              : "rounded bg-yellow-100 px-0.5 text-gray-900"
          }
        >
          {marked || highlight.text}
        </mark>
        {after}
      </p>
    </div>
  );
}
```

**Step 2: Export component**

Modify `frontend/src/features/evidence-search/index.ts`:

```typescript
export { EvidenceHighlightText } from "./components/EvidenceHighlightText";
```

**Step 3: Type check**

Run:

```bash
cd frontend
npx tsc --noEmit -p tsconfig.json 2>&1 | grep -v "ChatView.tsx"
```

Expected: no output.

**Step 4: Commit**

```bash
git add frontend/src/features/evidence-search/components/EvidenceHighlightText.tsx frontend/src/features/evidence-search/index.ts
git commit -m "feat: add evidence highlight renderer"
```

---

### Task 8: Add Detail View Component

**Files:**
- Create: `frontend/src/features/evidence-search/components/EvidenceDetailView.tsx`
- Modify: `frontend/src/features/evidence-search/index.ts`

**Step 1: Create detail view**

Create `frontend/src/features/evidence-search/components/EvidenceDetailView.tsx`:

```tsx
"use client";

import { useMemo, useState } from "react";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { useEvidenceGroupDetail } from "../hooks/useEvidenceGroupDetail";
import { EvidenceHighlightText } from "./EvidenceHighlightText";

interface EvidenceDetailViewProps {
  groupId: string;
}

const STATUS_VARIANT: Record<string, "default" | "success" | "warning" | "error" | "info"> = {
  provisional: "default",
  approved: "success",
  corrected: "warning",
  rejected: "error",
};

function countEntries(record: Record<string, number>) {
  return Object.entries(record).sort(([a], [b]) => a.localeCompare(b));
}

export function EvidenceDetailView({ groupId }: EvidenceDetailViewProps) {
  const decodedGroupId = decodeURIComponent(groupId);
  const { detail, isLoading, error } = useEvidenceGroupDetail(decodedGroupId);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);

  const selectedTrace = useMemo(() => {
    if (!detail) return null;
    return detail.traces.find((trace) => trace.canonical_evidence_id === selectedEvidenceId) ?? detail.traces[0] ?? null;
  }, [detail, selectedEvidenceId]);

  if (isLoading) {
    return <div className="flex justify-center py-12"><Spinner /></div>;
  }

  if (error || !detail) {
    return (
      <Card className="py-10 text-center">
        <p className="text-sm text-red-600">Failed to load evidence detail.</p>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Link href="/evidence" className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900">
        <ArrowLeft className="h-4 w-4" />
        Back to evidence
      </Link>

      <Card>
        <div className="grid gap-4 md:grid-cols-4">
          <div>
            <p className="text-xs font-medium uppercase text-gray-400">Gene</p>
            <p className="mt-1 text-sm font-medium text-gray-900">{detail.gene ?? "—"}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase text-gray-400">Variant</p>
            <p className="mt-1 text-sm text-gray-700">{detail.variant ?? "—"}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase text-gray-400">Disease</p>
            <p className="mt-1 text-sm text-gray-700">{detail.disease ?? "—"}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase text-gray-400">Classification</p>
            <p className="mt-1 text-sm text-gray-700">{detail.classification ?? "—"}</p>
          </div>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <div className="space-y-6">
          <Card>
            <h3 className="text-sm font-medium text-gray-900">Evidence Distribution</h3>
            <div className="mt-4 space-y-4">
              <section>
                <p className="mb-2 text-xs font-medium uppercase text-gray-400">Category</p>
                <div className="flex flex-wrap gap-2">
                  {countEntries(detail.distribution.by_category).map(([key, count]) => (
                    <Badge key={key} variant="info">{key}: {count}</Badge>
                  ))}
                </div>
              </section>
              <section>
                <p className="mb-2 text-xs font-medium uppercase text-gray-400">Status</p>
                <div className="flex flex-wrap gap-2">
                  {countEntries(detail.distribution.by_status).map(([key, count]) => (
                    <Badge key={key} variant={STATUS_VARIANT[key] ?? "default"}>{key}: {count}</Badge>
                  ))}
                </div>
              </section>
              <section>
                <p className="mb-2 text-xs font-medium uppercase text-gray-400">Track</p>
                <div className="flex flex-wrap gap-2">
                  {countEntries(detail.distribution.by_track).map(([key, count]) => (
                    <Badge key={key} variant="default">{key}: {count}</Badge>
                  ))}
                </div>
              </section>
            </div>
          </Card>

          <Card>
            <h3 className="text-sm font-medium text-gray-900">Evidence Items</h3>
            <div className="mt-3 max-h-[520px] space-y-2 overflow-y-auto pr-1">
              {detail.items.map((item) => {
                const active = item.canonical_evidence_id === (selectedTrace?.canonical_evidence_id ?? selectedEvidenceId);
                return (
                  <button
                    key={item.canonical_evidence_id}
                    onClick={() => setSelectedEvidenceId(item.canonical_evidence_id)}
                    className={
                      active
                        ? "w-full rounded-md border border-primary-200 bg-primary-50 p-3 text-left"
                        : "w-full rounded-md border border-gray-200 bg-white p-3 text-left hover:bg-gray-50"
                    }
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-medium text-gray-500">{item.field_id}</span>
                      <Badge variant={STATUS_VARIANT[item.review_status] ?? "default"}>{item.review_status}</Badge>
                    </div>
                    <p className="mt-1 line-clamp-2 text-sm text-gray-800">{item.value ?? "—"}</p>
                  </button>
                );
              })}
            </div>
          </Card>
        </div>

        <Card>
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-gray-900">Evidence Chain Traceability</h3>
              <p className="mt-1 text-xs text-gray-500">{selectedTrace?.field_id ?? "No evidence selected"}</p>
            </div>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <section>
              <h4 className="mb-2 text-xs font-medium uppercase text-gray-400">Original</h4>
              <EvidenceHighlightText highlight={selectedTrace?.original} active />
            </section>
            <section>
              <h4 className="mb-2 text-xs font-medium uppercase text-gray-400">Translated</h4>
              <EvidenceHighlightText highlight={selectedTrace?.translated} active />
            </section>
          </div>
        </Card>
      </div>
    </div>
  );
}
```

**Step 2: Export component**

Modify `frontend/src/features/evidence-search/index.ts`:

```typescript
export { EvidenceDetailView } from "./components/EvidenceDetailView";
```

**Step 3: Type check**

Run:

```bash
cd frontend
npx tsc --noEmit -p tsconfig.json 2>&1 | grep -v "ChatView.tsx"
```

Expected: no output.

**Step 4: Commit**

```bash
git add frontend/src/features/evidence-search/components/EvidenceDetailView.tsx frontend/src/features/evidence-search/index.ts
git commit -m "feat: add evidence detail view"
```

---

### Task 9: Add Detail Page Route

**Files:**
- Create: `frontend/app/(dashboard)/evidence/[groupId]/page.tsx`

**Step 1: Create page**

Create `frontend/app/(dashboard)/evidence/[groupId]/page.tsx`:

```tsx
import { EvidenceDetailView } from "@/features/evidence-search";
import { PageHeader } from "@/components/layout/PageHeader";

interface EvidenceDetailPageProps {
  params: Promise<{ groupId: string }>;
}

export default async function EvidenceDetailPage({ params }: EvidenceDetailPageProps) {
  const { groupId } = await params;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Evidence Detail"
        description="Review evidence distribution and bilingual traceability for this group."
      />
      <EvidenceDetailView groupId={groupId} />
    </div>
  );
}
```

If the project’s Next.js version expects non-Promise params, adjust only this signature:

```tsx
interface EvidenceDetailPageProps {
  params: { groupId: string };
}

export default function EvidenceDetailPage({ params }: EvidenceDetailPageProps) {
  return <EvidenceDetailView groupId={params.groupId} />;
}
```

Use whichever pattern matches existing dynamic pages in `frontend/app/(dashboard)/chat/[sessionId]/page.tsx`.

**Step 2: Type check**

Run:

```bash
cd frontend
npx tsc --noEmit -p tsconfig.json 2>&1 | grep -v "ChatView.tsx"
```

Expected: no output.

**Step 3: Manual browser check**

Run:

```bash
cd frontend
nvm use
npm run dev
```

Open `/evidence`, click a row. Expected:
- URL changes to `/evidence/<encoded-group-id>`
- Detail page renders summary card, distribution panel, item list, and traceability panes
- Missing spans render “No source span available.” instead of crashing

**Step 4: Commit**

```bash
git add frontend/app/'(dashboard)'/evidence/'[groupId]'/page.tsx
git commit -m "feat: add evidence detail route"
```

---

### Task 10: Add Backend Integration Coverage for Real Query Shape

**Files:**
- Modify: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py`

**Step 1: Add helper-level tests for span clamping and list conversion**

Add tests:

```python
from src.core.visualize_evidence_with_expert_in_loop.search_service import (
    _build_highlight,
    _coerce_str,
)


def test_coerce_str_joins_list_values():
    assert _coerce_str(["BRCA1", "BRCA2"]) == "BRCA1, BRCA2"


def test_build_highlight_clamps_invalid_offsets():
    highlight = _build_highlight({
        "text_snippet": "BRCA1 was detected.",
        "start_offset": 0,
        "end_offset": 200,
        "page": 3,
    })

    assert highlight is not None
    assert highlight.highlight_end == len("BRCA1 was detected.")
    assert highlight.page == 3
```

**Step 2: Run tests**

Run:

```bash
cd backend
uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py -v
```

Expected: PASS.

**Step 3: Commit**

```bash
git add backend/tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py
git commit -m "test: cover evidence trace helpers"
```

---

### Task 11: Update Documentation

**Files:**
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/README.md`
- Modify: `frontend/src/features/evidence-search/README.md`
- Modify: `progress.txt`

**Step 1: Update backend module README**

Add a section to `backend/src/core/visualize_evidence_with_expert_in_loop/README.md`:

```markdown
## Evidence Group Detail

`GET /api/v1/evidence/groups/{group_id}` returns a group-level detail payload. It joins field-level rows by `active_payload.group_id`, pivots summary values, computes distribution counts, and attaches original/translated source highlights from `run_evidence_items.source_span`.

The endpoint is used by the Evidence frontend detail page for:
- evidence item distribution by category, field, status, and track
- selectable field-level evidence items
- original/translated traceability panes
- highlighted source snippets
```

**Step 2: Update frontend feature README**

Add a section to `frontend/src/features/evidence-search/README.md`:

```markdown
## Detail View

The evidence list routes each row to `/evidence/[groupId]`. The detail page calls `GET /api/v1/evidence/groups/{group_id}` and renders summary metadata, evidence distribution, item list, and bilingual traceability highlights.

The frontend remains inside the existing Evidence module. No Dashboard module is introduced.
```

**Step 3: Record progress**

Append to `progress.txt`:

```text
[2026-06-07] [Evidence detail traceability highlights] [Completed]
- Added clickable evidence row detail route under existing Evidence module
- Added group-level detail API with distribution and original/translated traceability
- Added source highlight rendering for evidence-chain review
```

**Step 4: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/README.md frontend/src/features/evidence-search/README.md progress.txt
git commit -m "docs: document evidence detail traceability"
```

---

### Task 12: Final Verification

**Files:**
- No code changes unless verification finds defects.

**Step 1: Backend targeted tests**

Run:

```bash
cd backend
uv run pytest \
  tests/core/visualize_evidence_with_expert_in_loop/test_contracts.py \
  tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py \
  tests/api/test_evidence_api.py \
  tests/api/test_source_link_api.py \
  -v
```

Expected: PASS.

**Step 2: Backend lint**

Run:

```bash
cd backend
uv run ruff check src/core/visualize_evidence_with_expert_in_loop src/api/v1/evidence.py tests/core/visualize_evidence_with_expert_in_loop tests/api/test_evidence_api.py
```

Expected: PASS.

**Step 3: Frontend type check**

Run:

```bash
cd frontend
npm run type-check
```

Expected: PASS. If a pre-existing unrelated `ChatView.tsx` duplicate identifier error remains, record it in final notes and run:

```bash
cd frontend
npx tsc --noEmit -p tsconfig.json 2>&1 | grep -v "ChatView.tsx"
```

Expected: no output.

**Step 4: Frontend lint**

Run:

```bash
cd frontend
npm run lint
```

Expected: PASS.

**Step 5: Manual API check**

Use a real `group_id` from search results:

```bash
curl -s "http://localhost:8000/api/v1/evidence/search?page=1&page_size=1" | python -m json.tool
```

Copy `.items[0].group_id`, then:

```bash
curl -s "http://localhost:8000/api/v1/evidence/groups/<url-encoded-group-id>" | python -m json.tool
```

Expected:
- `items` is non-empty
- `distribution.by_category` is non-empty
- `traces` length equals `items` length or includes every item with nullable spans

**Step 6: Manual UI check**

Run:

```bash
cd frontend
nvm use
npm run dev
```

Open `/evidence`:
- Search rows have non-empty gene/disease data where present
- Pagination controls still work
- Clicking a row opens detail page
- Detail page shows distribution badges
- Selecting evidence items updates highlighted source panes
- Missing original/translated span does not crash the page

**Step 7: Final commit if fixes were needed**

If verification required fixes:

```bash
git add <changed-files>
git commit -m "fix: stabilize evidence detail traceability"
```

---

## Risks and Guardrails

- **Group IDs are long and contain punctuation.** Always `encodeURIComponent` on navigation and `decodeURIComponent` in the page before API calls.
- **Some source documents have no PMID/DOI identifiers.** UI must show `—`, not fail.
- **Some evidence items have only original or only translated spans.** Trace panes must allow nulls.
- **`active_payload` is heterogeneous JSONB.** Use typed response models at API boundary; keep raw JSON handling local to service internals.
- **Frontend scope is only Chat and Evidence.** Do not add Dashboard or Pipeline navigation while implementing this feature.
- **Existing workspace may be dirty.** Do not revert unrelated files.
