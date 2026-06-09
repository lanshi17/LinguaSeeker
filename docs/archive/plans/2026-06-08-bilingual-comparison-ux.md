# Bilingual Comparison UX Improvement — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the poor original/translated evidence comparison UX by (1) making the extracted evidence value the visual anchor, (2) hardening highlight offset logic for cross-lingual text, and (3) replacing the two-card layout with a compact, scan-friendly bilingual view.

**Architecture:** Keep changes inside the existing Phase 4 vertical slice (`core/visualize_evidence_with_expert_in_loop`) and the Evidence frontend module. Backend extends `EvidenceTrackTrace` with `original_value` / `translated_value` fields and tightens `_build_highlight` offset fallback. Frontend replaces the two-column Card layout in `EvidenceDetailView.tsx` with a single comparison panel that leads with the evidence value pair and renders both snippets inside a shared highlight card with a visible value anchor.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic, pytest; Next.js App Router, React 18, TypeScript, Tailwind, lucide-react, Vitest + Testing Library for frontend component tests.

**Status:** in-progress
**Created:** 2026-06-08

---

## Problem Statement

The evidence detail page at `/evidence/detail?groupId=...` renders original and translated source spans side-by-side, but the comparison is hard to use:

1. **Highlight offset unreliability.** Stored `start_offset/end_offset` are document-global while `text_snippet` is a short excerpt. `_build_highlight` falls back to substring-searching `value` in `text_snippet`, which:
   - Refuses every value shorter than 3 characters, even when the token is distinctive enough to match safely
   - Cannot locate translated values on the translated track when the value is stored as the original-language string
   - Silently falls back to `(0, 0)` — no visible highlight, no feedback

2. **No visible anchor.** The extracted `value` (the thing the user is reviewing) is not shown in the traceability panel. Users must scan each snippet to rediscover it.

3. **Layout is two disconnected cards.** Original and translated texts sit in separate cards with no visual relationship. There is no way to tell at a glance that both highlight the same evidence entity.

## Success Criteria

1. Every trace panel shows the original-side `value` and the translated-side `value` prominently above the snippets.
2. `_build_highlight` locates a highlight whenever either (a) offsets fit or can be clamped inside the snippet, or (b) an unambiguous case-normalized token match exists. Pure one-letter alphabetic values remain unhighlighted by fallback to avoid false-positive article/nucleotide/amino-acid matches. Offsets never exceed snippet bounds.
3. When highlight offsets are genuinely unknown, the UI displays the full snippet without a mark and a clear "highlight unavailable" indicator rather than an arbitrary highlight.
4. Original and translated snippets share a single comparison panel with aligned visual structure, not two disconnected cards.
5. All existing tests pass; new tests cover the offset fallback improvements and the new `original_value`/`translated_value` contract fields.
6. TypeScript build and ESLint pass.
7. No raw `dict` return annotations are introduced.

---

### Task 1: Backend — Extend `EvidenceTrackTrace` with value anchors

**Files:**
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py`
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py`
- Test: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_contracts.py`
- Test: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py`

**Step 1: Write the failing contract test**

Append to `backend/tests/core/visualize_evidence_with_expert_in_loop/test_contracts.py`:

```python
def test_evidence_track_trace_carries_value_anchors():
    from uuid import uuid4
    from src.core.visualize_evidence_with_expert_in_loop.contracts import (
        EvidenceChainHighlight,
        EvidenceTrackTrace,
    )

    trace = EvidenceTrackTrace(
        canonical_evidence_id=uuid4(),
        field_id="A.gene_symbol",
        original_value="BRCA1",
        translated_value="BRCA1 (基因符号未翻译)",
        original=EvidenceChainHighlight(
            text="BRCA1 was detected in the proband.",
            highlight_start=0,
            highlight_end=5,
        ),
        translated=EvidenceChainHighlight(
            text="在先证者中检测到 BRCA1。",
            highlight_start=7,
            highlight_end=12,
        ),
    )
    assert trace.original_value == "BRCA1"
    assert trace.translated_value == "BRCA1 (基因符号未翻译)"
```

**Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_contracts.py::test_evidence_track_trace_carries_value_anchors -v`
Expected: FAIL with `__init__() got an unexpected keyword argument 'original_value'`.

**Step 3: Add the two fields to `EvidenceTrackTrace`**

In `backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py`, replace the existing `EvidenceTrackTrace` definition:

```python
class EvidenceTrackTrace(BaseModel):
    """Original/translated trace pair for one evidence item."""

    canonical_evidence_id: UUID
    field_id: str
    field_name: str | None = None
    original_value: str | None = None
    translated_value: str | None = None
    original: EvidenceChainHighlight | None = None
    translated: EvidenceChainHighlight | None = None
    alignment_confidence: float | None = None
```

**Step 4: Re-run the contract test**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_contracts.py::test_evidence_track_trace_carries_value_anchors -v`
Expected: PASS.

**Step 5: Wire the values in `search_service.get_group_detail`**

In `backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py`, locate the trace-building block that currently calls `traces.append(EvidenceTrackTrace(...))` and add the two value fields. The `original_value` and `translated_value` variables are already computed a few lines above — just pass them through:

```python
traces.append(
    EvidenceTrackTrace(
        canonical_evidence_id=canonical_id,
        field_id=field_id,
        field_name=str(field_name) if field_name else None,
        original_value=original_value,
        translated_value=translated_value,
        original=original,
        translated=translated,
        alignment_confidence=1.0 if original and translated else None,
    )
)
```

**Step 6: Add a paired-field group-detail test for value anchors**

Do not add `assert traces[0].translated_value is not None` to the existing `test_get_group_detail_pivots_distribution_and_traces` fixture. That fixture currently has `A.gene_symbol` on the original track and `B.disease_diagnosis` on the translated track, so grouping by `field_id` intentionally produces two partial traces.

Append a targeted test to `backend/tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py` with matching `field_id` values:

```python
@pytest.mark.asyncio
async def test_get_group_detail_includes_value_anchors_for_paired_field():
    """Paired original/translated rows expose both value anchors on one trace."""
    source_document_id = uuid4()
    original_id = uuid4()
    translated_id = uuid4()
    group_id = "gene=['BRCA1']"

    rows = [
        SimpleNamespace(
            canonical_evidence_id=original_id,
            source_document_id=source_document_id,
            field_id="A.gene_symbol",
            review_status="provisional",
            current_best_confidence=Decimal("0.9500"),
            active_payload={
                "group_id": group_id,
                "field_name": "Gene symbol",
                "category": "A",
                "value": "BRCA1",
                "track": "original",
                "source": {
                    "text_snippet": "BRCA1 was detected in the proband.",
                    "start_offset": 0,
                    "end_offset": 5,
                    "page": 1,
                },
            },
        ),
        SimpleNamespace(
            canonical_evidence_id=translated_id,
            source_document_id=source_document_id,
            field_id="A.gene_symbol",
            review_status="provisional",
            current_best_confidence=Decimal("0.9300"),
            active_payload={
                "group_id": group_id,
                "field_name": "Gene symbol",
                "category": "A",
                "value": "BRCA1",
                "track": "translated",
                "source": {
                    "text_snippet": "在先证者中检测到 BRCA1。",
                    "start_offset": 7,
                    "end_offset": 12,
                    "page": 1,
                },
            },
        ),
    ]

    service = SearchService(_FakeSession([
        _FakeResult(rows=rows),
        _FakeResult(scalars=[]),
    ]))

    detail = await service.get_group_detail(group_id=group_id)

    trace = next(trace for trace in detail.traces if trace.field_id == "A.gene_symbol")
    assert trace.original_value == "BRCA1"
    assert trace.translated_value == "BRCA1"
```

**Step 7: Run all affected tests**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/ -v`
Expected: all PASS.

**Step 8: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py \
        backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py \
        backend/tests/core/visualize_evidence_with_expert_in_loop/test_contracts.py \
        backend/tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py
git commit -m "feat(evidence): expose original_value/translated_value on trace anchors"
```

---

### Task 2: Backend — Harden `_build_highlight` offset fallback

**Files:**
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py`
- Test: `backend/tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py`

**Step 1: Write focused highlight fallback tests**

Append to `backend/tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py`:

```python
def test_build_highlight_value_fallback_is_case_insensitive():
    """Value 'brca1' must still highlight inside 'BRCA1 was detected.'."""
    highlight = _build_highlight(
        {"text_snippet": "BRCA1 was detected.", "start_offset": 900, "end_offset": 905},
        value="brca1",
    )
    assert highlight is not None
    assert highlight.highlight_start == 0
    assert highlight.highlight_end == 5


def test_build_highlight_value_fallback_allows_short_distinctive_tokens():
    """Short tokens with digits/punctuation can be safe enough for value fallback."""
    highlight = _build_highlight(
        {"text_snippet": "Variant V2 was observed.", "start_offset": 900, "end_offset": 902},
        value="V2",
    )
    assert highlight is not None
    assert highlight.highlight_start == 8
    assert highlight.highlight_end == 10


def test_build_highlight_value_fallback_ignores_ambiguous_single_letter_tokens():
    """Pure single-letter values should not match common prose such as articles."""
    highlight = _build_highlight(
        {"text_snippet": "A variant was detected in BRCA1.", "start_offset": 900, "end_offset": 901},
        value="A",
    )
    assert highlight is not None
    assert highlight.highlight_start == 0
    assert highlight.highlight_end == 0


def test_build_highlight_value_fallback_marks_unknown_when_value_absent():
    """When value cannot be located, highlight_start == highlight_end (no mark)."""
    highlight = _build_highlight(
        {"text_snippet": "No relevant finding.", "start_offset": 900, "end_offset": 910},
        value="BRCA1",
    )
    assert highlight is not None
    assert highlight.highlight_start == highlight.highlight_end == 0
```

**Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py -v -k build_highlight`
Expected: 2 FAIL (`case_insensitive` and `short_distinctive_tokens`). Existing clamping behavior must still pass.

**Step 3: Add bounded value-search helpers**

In `backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py`, add `import re` near the top and add these helpers above `_build_highlight`:

```python
_TOKEN_BOUNDARY = r"A-Za-z0-9_"


def _parse_source_offset(raw: object, *, default: int, name: str) -> tuple[int, bool]:
    """Parse a source offset and report whether the stored value was valid."""
    if raw is None:
        return default, True
    try:
        return int(raw), True
    except (TypeError, ValueError):
        logger.warning("Invalid source_span {}_offset={!r}; using value fallback", name, raw)
        return default, False


def _find_value_anchor(text: str, value: str | None) -> tuple[int, int] | None:
    """Find a safe case-insensitive value anchor inside a snippet."""
    if value is None:
        return None

    needle = value.strip()
    if not needle:
        return None

    # Pure one/two-letter values are too ambiguous in prose. Keep them
    # unhighlighted unless future source metadata gives a stronger anchor.
    if len(needle) < 3 and needle.isalpha():
        return None

    pattern = re.compile(
        rf"(?<![{_TOKEN_BOUNDARY}]){re.escape(needle)}(?![{_TOKEN_BOUNDARY}])",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if match is None:
        return None
    return match.start(), match.end()
```

**Step 4: Rewrite `_build_highlight` while preserving clamping**

Replace the existing `_build_highlight` body with:

```python
def _build_highlight(
    source_span: dict[str, object],
    value: str | None = None,
) -> EvidenceChainHighlight | None:
    """Build a clamped highlight payload from a stored source span.

    Source spans store document-global offsets while text_snippet is a short
    excerpt. When offsets are malformed or start beyond the snippet, locate
    ``value`` inside the snippet using a safe token-boundary search. When the
    value cannot be located, start and end collapse to 0 (no visible highlight).
    """
    if not source_span:
        return None

    text = str(source_span.get("text_snippet") or "")
    if not text:
        return None

    text_len = len(text)
    start, start_valid = _parse_source_offset(
        source_span.get("start_offset"),
        default=0,
        name="start",
    )
    end, end_valid = _parse_source_offset(
        source_span.get("end_offset"),
        default=text_len,
        name="end",
    )
    if end < start:
        end = text_len

    # Valid starts inside the snippet should keep current behavior: clamp the
    # end to snippet bounds instead of falling through to value search.
    if start_valid and end_valid and start < text_len:
        start = max(start, 0)
        end = min(max(end, start), text_len)
    else:
        anchor = _find_value_anchor(text, value)
        if anchor is None:
            start = end = 0
        else:
            start, end = anchor

    page = source_span.get("page")
    return EvidenceChainHighlight(
        text=text,
        highlight_start=max(start, 0),
        highlight_end=min(max(end, 0), text_len),
        page=page if isinstance(page, int) else None,
        source_span=source_span,
    )
```

**Step 5: Keep the ambiguous single-letter regression test**

Rename the existing `test_build_highlight_value_fallback_requires_min_length` to `test_build_highlight_value_fallback_ignores_ambiguous_single_letter_tokens` if you do not add the new test above separately. The important assertion is that `value="A"` in prose still returns `(0, 0)`.

**Step 6: Re-run highlight tests**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py -v -k build_highlight`
Expected: all existing and new `build_highlight` tests PASS, including `test_build_highlight_clamps_invalid_offsets`.

**Step 7: Full test pass**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/ -v`
Expected: all PASS.

**Step 8: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py \
        backend/tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py
git commit -m "fix(evidence): harden highlight offset fallback for cross-lingual snippets"
```

---

### Task 3: Frontend — Build tested bilingual comparison components

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Create: `frontend/vitest.config.ts`
- Modify: `frontend/src/features/evidence-search/types/evidenceSearch.ts`
- Modify: `frontend/src/features/evidence-search/components/EvidenceDetailView.tsx`
- Modify: `frontend/src/features/evidence-search/components/EvidenceHighlightText.tsx`
- Create: `frontend/src/features/evidence-search/components/BilingualComparison.tsx`
- Create: `frontend/tests/evidence-search/EvidenceHighlightText.test.tsx`
- Create: `frontend/tests/evidence-search/BilingualComparison.test.tsx`

**Step 1: Add the frontend test runner**

Run:

```bash
cd frontend
nvm use
npm install --save-dev vitest @testing-library/react @testing-library/jest-dom jsdom
```

Modify `frontend/package.json` scripts:

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint .",
    "type-check": "tsc --noEmit",
    "test": "vitest run"
  }
}
```

Create `frontend/vitest.config.ts`:

```typescript
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.{ts,tsx}"],
  },
});
```

**Step 2: Extend the TypeScript trace type**

In `frontend/src/features/evidence-search/types/evidenceSearch.ts`, add two fields to `EvidenceTrackTrace`:

```typescript
export interface EvidenceTrackTrace {
  canonical_evidence_id: string;
  field_id: string;
  field_name?: string | null;
  original_value?: string | null;
  translated_value?: string | null;
  original?: EvidenceChainHighlight | null;
  translated?: EvidenceChainHighlight | null;
  alignment_confidence?: number | null;
}
```

**Step 3: Write failing component tests**

Create `frontend/tests/evidence-search/EvidenceHighlightText.test.tsx`:

```tsx
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EvidenceHighlightText } from "../../src/features/evidence-search/components/EvidenceHighlightText";

describe("EvidenceHighlightText", () => {
  it("keeps the existing empty-state guard", () => {
    render(<EvidenceHighlightText highlight={null} />);

    expect(screen.getByText("No source span available.")).toBeInTheDocument();
  });

  it("renders a mark when the highlight range is non-empty", () => {
    const { container } = render(
      <EvidenceHighlightText
        highlight={{
          text: "BRCA1 was detected.",
          highlight_start: 0,
          highlight_end: 5,
          page: 3,
          source_span: {},
        }}
        active
      />,
    );

    const mark = container.querySelector("mark");
    expect(mark).toHaveTextContent("BRCA1");
    expect(screen.queryByText("highlight unavailable")).not.toBeInTheDocument();
  });

  it("shows highlight-unavailable feedback for zero-length ranges", () => {
    const { container } = render(
      <EvidenceHighlightText
        highlight={{
          text: "The source text is available.",
          highlight_start: 0,
          highlight_end: 0,
          page: null,
          source_span: {},
        }}
      />,
    );

    expect(container.querySelector("mark")).not.toBeInTheDocument();
    expect(screen.getByText("highlight unavailable")).toBeInTheDocument();
    expect(screen.getByText("The source text is available.")).toBeInTheDocument();
  });
});
```

Create `frontend/tests/evidence-search/BilingualComparison.test.tsx`:

```tsx
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BilingualComparison } from "../../src/features/evidence-search/components/BilingualComparison";

describe("BilingualComparison", () => {
  it("renders original and translated value anchors", () => {
    render(
      <BilingualComparison
        trace={{
          canonical_evidence_id: "evidence-1",
          field_id: "A.gene_symbol",
          field_name: "Gene symbol",
          original_value: "BRCA1",
          translated_value: "BRCA1",
          original: {
            text: "BRCA1 was detected.",
            highlight_start: 0,
            highlight_end: 5,
            page: 1,
            source_span: {},
          },
          translated: {
            text: "检测到 BRCA1。",
            highlight_start: 4,
            highlight_end: 9,
            page: 1,
            source_span: {},
          },
          alignment_confidence: 1,
        }}
      />,
    );

    expect(screen.getByText("Original value")).toBeInTheDocument();
    expect(screen.getByText("Translated value")).toBeInTheDocument();
    expect(screen.getAllByText("BRCA1").length).toBeGreaterThanOrEqual(2);
  });

  it("renders an empty state when no trace is selected", () => {
    render(<BilingualComparison trace={null} />);

    expect(screen.getByText("No evidence selected.")).toBeInTheDocument();
  });
});
```

**Step 4: Run tests to verify they fail before component changes**

Run: `cd frontend && nvm use && npm run test -- tests/evidence-search/EvidenceHighlightText.test.tsx tests/evidence-search/BilingualComparison.test.tsx`
Expected:
- `BilingualComparison` import fails because the component does not exist.
- `EvidenceHighlightText` test fails because `highlight unavailable` is not rendered.

**Step 5: Update `EvidenceHighlightText` with full null-safe rendering**

Replace `frontend/src/features/evidence-search/components/EvidenceHighlightText.tsx` with:

```tsx
"use client";

import type { EvidenceChainHighlight } from "../types/evidenceSearch";

interface EvidenceHighlightTextProps {
  highlight?: EvidenceChainHighlight | null;
  active?: boolean;
  anchorValue?: string;
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
  const hasMark = end > start;
  const before = highlight.text.slice(0, start);
  const marked = highlight.text.slice(start, end);
  const after = highlight.text.slice(end);

  return (
    <div className="rounded-md border border-gray-200 bg-white p-3 text-sm leading-6 text-gray-700">
      <div className="mb-2 flex items-center justify-between gap-3 text-xs text-gray-400">
        <span>Page {highlight.page ?? "—"}</span>
        {!hasMark && (
          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-500">
            highlight unavailable
          </span>
        )}
      </div>
      <p className="whitespace-pre-wrap">
        {before}
        {hasMark ? (
          <mark
            className={
              active
                ? "rounded bg-amber-200 px-0.5 text-gray-950"
                : "rounded bg-yellow-100 px-0.5 text-gray-900"
            }
          >
            {marked}
          </mark>
        ) : null}
        {!hasMark ? marked : null}
        {after}
      </p>
    </div>
  );
}
```

Notes:
- Keep the existing null guard. Partial traces can have `original: null` or `translated: null`.
- Render the unavailable chip whenever `highlight_start === highlight_end`, even when `anchorValue` is absent.
- `anchorValue` stays in the public prop type because callers pass it, but the component does not need to read it for the current chip copy.

**Step 6: Create `BilingualComparison` directly**

Create `frontend/src/features/evidence-search/components/BilingualComparison.tsx`:

```tsx
"use client";

import type { EvidenceTrackTrace } from "../types/evidenceSearch";
import { EvidenceHighlightText } from "./EvidenceHighlightText";

interface BilingualComparisonProps {
  trace: EvidenceTrackTrace | null;
}

export function BilingualComparison({ trace }: BilingualComparisonProps) {
  if (!trace) {
    return (
      <p className="py-8 text-center text-sm text-gray-400">No evidence selected.</p>
    );
  }

  return (
    <>
      <div className="mb-4 grid gap-3 rounded-md bg-slate-50 p-3 xl:grid-cols-2">
        <div>
          <p className="text-[10px] font-medium uppercase tracking-wide text-slate-500">Original value</p>
          <p className="mt-1 break-words font-mono text-sm text-slate-900">
            {trace.original_value ?? "—"}
          </p>
        </div>
        <div>
          <p className="text-[10px] font-medium uppercase tracking-wide text-slate-500">Translated value</p>
          <p className="mt-1 break-words font-mono text-sm text-slate-900">
            {trace.translated_value ?? "—"}
          </p>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <section>
          <h4 className="mb-2 text-xs font-medium uppercase text-gray-400">Original</h4>
          <EvidenceHighlightText
            highlight={trace.original}
            anchorValue={trace.original_value ?? undefined}
            active
          />
        </section>
        <section>
          <h4 className="mb-2 text-xs font-medium uppercase text-gray-400">Translated</h4>
          <EvidenceHighlightText
            highlight={trace.translated}
            anchorValue={trace.translated_value ?? undefined}
            active
          />
        </section>
      </div>
    </>
  );
}
```

**Step 7: Use `BilingualComparison` from `EvidenceDetailView`**

In `frontend/src/features/evidence-search/components/EvidenceDetailView.tsx`:

1. Replace `import { EvidenceHighlightText } from "./EvidenceHighlightText";` with:

```tsx
import { BilingualComparison } from "./BilingualComparison";
```

2. Replace the existing traceability body:

```tsx
<div className="grid gap-4 xl:grid-cols-2">
  ...
</div>
```

with:

```tsx
<BilingualComparison trace={selectedTrace} />
```

Keep the existing `Card` header and selected `field_id` display.

**Step 8: Run frontend component tests**

Run: `cd frontend && nvm use && npm run test -- tests/evidence-search/EvidenceHighlightText.test.tsx tests/evidence-search/BilingualComparison.test.tsx`
Expected: all PASS.

**Step 9: Run frontend checks**

Run: `cd frontend && nvm use && npm run type-check && npm run lint`
Expected: both PASS.

**Step 10: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.ts \
        frontend/src/features/evidence-search/types/evidenceSearch.ts \
        frontend/src/features/evidence-search/components/EvidenceDetailView.tsx \
        frontend/src/features/evidence-search/components/EvidenceHighlightText.tsx \
        frontend/src/features/evidence-search/components/BilingualComparison.tsx \
        frontend/tests/evidence-search/EvidenceHighlightText.test.tsx \
        frontend/tests/evidence-search/BilingualComparison.test.tsx
git commit -m "feat(evidence-ui): add tested bilingual comparison panel"
```

---

### Task 4: Integration verification

**Step 1: Backend regression pass**

Run: `cd backend && uv run pytest tests/ -v`
Expected: all PASS.

**Step 2: Frontend regression pass**

Run: `cd frontend && nvm use && npm run test && npm run type-check && npm run lint`
Expected: all PASS.

**Step 3: Frontend build pass**

Run: `cd frontend && nvm use && npm run build`
Expected: clean build, no type or lint warnings.

**Step 4: Manual smoke test**

Start the stack (`docker compose up` or dev servers) and open an evidence detail page that has bilingual traces. Verify:

- The value pair banner shows original + translated values for the selected evidence item.
- When the backend located a highlight, it appears in yellow.
- When the backend could not locate a highlight, a small "highlight unavailable" chip appears and the snippet is shown unmarked.
- Switching between evidence items updates the value banner and both snippets together.

**Step 5: Update progress and lesson logs**

Append to `progress.txt`:

```
[2026-06-08] [Bilingual comparison UX: value anchors + highlight hardening + comparison panel] [Completed]
```

If any debugging detours happened, record them in `lesson.md` per project rules.

**Step 6: Final commit (if any cleanup)**

```bash
git add -A
git commit -m "chore: sync bilingual comparison follow-ups"
```

---

## Out of Scope (future increments)

- **Sentence-level interleaving** — aligning original and translated sentences one-to-one for line-by-line reading. Requires sentence splitting on both tracks and a similarity matcher; defer until real usage shows the value-anchor approach is insufficient.
- **PDF page preview pane** — showing the original PDF page with the evidence region boxed. Needs a PDF renderer and bbox grounding that is not yet reliable for all tracks.
- **Term-glossary hover** — popping a bilingual term map on hover over medical tokens. Requires terminology persistence that lives in the translator module; separate feature.
