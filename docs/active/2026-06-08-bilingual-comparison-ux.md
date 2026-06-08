# Bilingual Comparison UX Improvement — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the poor original/translated evidence comparison UX by (1) making the extracted evidence value the visual anchor, (2) hardening highlight offset logic for cross-lingual text, and (3) replacing the two-card layout with a compact, scan-friendly bilingual view.

**Architecture:** Keep changes inside the existing Phase 4 vertical slice (`core/visualize_evidence_with_expert_in_loop`) and the Evidence frontend module. Backend extends `EvidenceTrackTrace` with `original_value` / `translated_value` fields and tightens `_build_highlight` offset fallback. Frontend replaces the two-column Card layout in `EvidenceDetailView.tsx` with a single comparison panel that leads with the evidence value pair and renders both snippets inside a shared highlight card with a visible value anchor.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic, pytest; Next.js App Router, React 18, TypeScript, Tailwind, lucide-react.

---

## Problem Statement

The evidence detail page at `/evidence/detail?groupId=...` renders original and translated source spans side-by-side, but the comparison is hard to use:

1. **Highlight offset unreliability.** Stored `start_offset/end_offset` are document-global while `text_snippet` is a short excerpt. `_build_highlight` falls back to substring-searching `value` in `text_snippet`, which:
   - Refuses values shorter than 3 characters (kills single-letter amino acids, nucleotides, HGVS tokens like `p.R123X`)
   - Cannot locate translated values on the translated track when the value is stored as the original-language string
   - Silently falls back to `(0, 0)` — no visible highlight, no feedback

2. **No visible anchor.** The extracted `value` (the thing the user is reviewing) is not shown in the traceability panel. Users must scan each snippet to rediscover it.

3. **Layout is two disconnected cards.** Original and translated texts sit in separate cards with no visual relationship. There is no way to tell at a glance that both highlight the same evidence entity.

## Success Criteria

1. Every trace panel shows the original-side `value` and the translated-side `value` prominently above the snippets.
2. `_build_highlight` locates a highlight whenever either (a) the value is present verbatim in the snippet, or (b) a case-normalized / punctuation-tolerant match exists. Offsets never exceed snippet bounds.
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

**Step 6: Update the existing group-detail test fixture to assert value anchors**

In `backend/tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py::test_get_group_detail_pivots_distribution_and_traces`, add assertions after the existing trace checks:

```python
# New assertions — values exposed for bilingual anchor UI
assert traces[0].original_value is not None
assert traces[0].translated_value is not None
```

If the fixture payloads do not already contain `"value": ...` keys, add them now so the assertions hold.

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

**Step 1: Write three failing tests**

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


def test_build_highlight_value_fallback_allows_short_medical_tokens():
    """Single/double-char medical tokens (e.g. HGVS 'p.R123X', amino acids) must match."""
    highlight = _build_highlight(
        {"text_snippet": "Variant p.R123X was observed.", "start_offset": 900, "end_offset": 907},
        value="p.R123X",
    )
    assert highlight is not None
    assert highlight.highlight_start == 8
    assert highlight.highlight_end == 15


def test_build_highlight_value_fallback_marks_unknown_when_value_absent():
    """When value cannot be located, highlight_start == highlight_end (no mark)."""
    highlight = _build_highlight(
        {"text_snippet": "No relevant finding.", "start_offset": 900, "end_offset": 910},
        value="BRCA1",
    )
    assert highlight is not None
    assert highlight.highlight_start == highlight.highlight_end
```

**Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py -v -k build_highlight`
Expected: 2 FAIL (case-insensitive and short-token tests); unknown-value test may pass.

**Step 3: Rewrite the fallback block in `_build_highlight`**

In `backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py`, replace the existing `_build_highlight` body with a tolerant implementation. Key changes:

- Drop the `len(value) >= 3` gate. Even single-character medical tokens matter.
- Use a case-folded search for the value against the snippet.
- On failure, leave `highlight_start == highlight_end == 0` (no visible mark). This is already the current behavior; keep it but document it explicitly.

```python
def _build_highlight(
    source_span: dict[str, object],
    value: str | None = None,
) -> EvidenceChainHighlight | None:
    """Build a clamped highlight payload from a stored source span.

    Source spans store document-global offsets while text_snippet is a short
    excerpt. When offsets exceed the snippet bounds, locate ``value`` inside
    the snippet using a case-insensitive substring search. When the value
    cannot be located, start and end collapse to 0 (no visible highlight).
    """
    if not source_span:
        return None

    text = str(source_span.get("text_snippet") or "")
    if not text:
        return None

    text_len = len(text)
    start = int(source_span.get("start_offset") or 0)
    raw_end = source_span.get("end_offset")
    end = int(raw_end) if raw_end is not None else text_len
    if end < start:
        end = text_len

    # Offsets fit inside the snippet: clamp to bounds.
    if 0 <= start < text_len and start <= end <= text_len:
        page = source_span.get("page")
        return EvidenceChainHighlight(
            text=text,
            highlight_start=start,
            highlight_end=end,
            page=page if isinstance(page, int) else None,
            source_span=source_span,
        )

    # Offsets are document-global or invalid: fall back to value search.
    if value:
        needle = value
        haystack = text
        # Case-insensitive fallback — medical identifiers cross case often.
        idx = haystack.lower().find(needle.lower()) if needle else -1
        if idx >= 0:
            start = idx
            end = idx + len(needle)
        else:
            start = end = 0
    else:
        start = end = 0

    page = source_span.get("page")
    return EvidenceChainHighlight(
        text=text,
        highlight_start=max(start, 0),
        highlight_end=min(max(end, 0), text_len),
        page=page if isinstance(page, int) else None,
        source_span=source_span,
    )
```

**Step 4: Re-run highlight tests**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py -v -k build_highlight`
Expected: all 7 (4 existing + 3 new) PASS.

**Step 5: Update the existing short-value test expectation**

`test_build_highlight_value_fallback_requires_min_length` previously asserted that single-character values are ignored. With the new behavior, single-char values that *do* appear in the snippet should still highlight. Adjust the test: the snippet `"A was detected."` contains `"A"` at position 0, so expect `highlight_start == 0, highlight_end == 1`. If the test was intentionally asserting "no match" to avoid false positives, rename it and change the snippet to one that does not contain the value.

**Step 6: Full test pass**

Run: `cd backend && uv run pytest tests/core/visualize_evidence_with_expert_in_loop/ -v`
Expected: all PASS.

**Step 7: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py \
        backend/tests/core/visualize_evidence_with_expert_in_loop/test_search_service.py
git commit -m "fix(evidence): harden highlight offset fallback for cross-lingual snippets"
```

---

### Task 3: Frontend — Surface value anchors in the trace panel

**Files:**
- Modify: `frontend/src/features/evidence-search/types/evidenceSearch.ts`
- Modify: `frontend/src/features/evidence-search/components/EvidenceDetailView.tsx`
- Modify: `frontend/src/features/evidence-search/components/EvidenceHighlightText.tsx`

**Step 1: Extend the TypeScript trace type**

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

**Step 2: Run type-check to verify it compiles**

Run: `cd frontend && nvm use && npm run type-check`
Expected: PASS (no consumers yet reference the new fields).

**Step 3: Add a comparison header inside `EvidenceDetailView`**

In `frontend/src/features/evidence-search/components/EvidenceDetailView.tsx`, replace the existing traceability `<Card>` block (the one containing the "Original" / "Translated" two-column grid) with a new structure that leads with the value pair. Sketch:

```tsx
<Card>
  <div className="mb-4 flex items-center justify-between">
    <div>
      <h3 className="text-sm font-medium text-gray-900">Evidence Chain Traceability</h3>
      <p className="mt-1 text-xs text-gray-500">{selectedTrace?.field_id ?? "No evidence selected"}</p>
    </div>
  </div>

  {/* Value anchor — the review target */}
  <div className="mb-4 grid gap-3 rounded-md bg-slate-50 p-3 xl:grid-cols-2">
    <div>
      <p className="text-[10px] font-medium uppercase tracking-wide text-slate-500">Original value</p>
      <p className="mt-1 font-mono text-sm text-slate-900">
        {selectedTrace?.original_value ?? "—"}
      </p>
    </div>
    <div>
      <p className="text-[10px] font-medium uppercase tracking-wide text-slate-500">Translated value</p>
      <p className="mt-1 font-mono text-sm text-slate-900">
        {selectedTrace?.translated_value ?? "—"}
      </p>
    </div>
  </div>

  <div className="grid gap-4 xl:grid-cols-2">
    <section>
      <h4 className="mb-2 text-xs font-medium uppercase text-gray-400">Original</h4>
      <EvidenceHighlightText
        highlight={selectedTrace?.original}
        anchorValue={selectedTrace?.original_value ?? undefined}
      />
    </section>
    <section>
      <h4 className="mb-2 text-xs font-medium uppercase text-gray-400">Translated</h4>
      <EvidenceHighlightText
        highlight={selectedTrace?.translated}
        anchorValue={selectedTrace?.translated_value ?? undefined}
      />
    </section>
  </div>
</Card>
```

**Step 4: Allow `EvidenceHighlightText` to render an "anchor unknown" hint**

In `frontend/src/features/evidence-search/components/EvidenceHighlightText.tsx`, accept an optional `anchorValue` prop. When the highlight has `highlight_start === highlight_end` (no markable region) but `text` is non-empty, render a quiet notice line rather than silently showing an unmarked snippet:

```tsx
interface EvidenceHighlightTextProps {
  highlight?: EvidenceChainHighlight | null;
  active?: boolean;
  anchorValue?: string;
}

// Inside the body, after computing start/end:
const hasMark = end > start;

return (
  <div className="rounded-md border border-gray-200 bg-white p-3 text-sm leading-6 text-gray-700">
    <div className="mb-2 flex items-center justify-between text-xs text-gray-400">
      <span>Page {highlight.page ?? "—"}</span>
      {!hasMark && anchorValue && (
        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-500">
          highlight unavailable — value shown above
        </span>
      )}
    </div>
    <p className="whitespace-pre-wrap">
      {before}
      {hasMark && (
        <mark className={active ? "rounded bg-amber-200 px-0.5 text-gray-950" : "rounded bg-yellow-100 px-0.5 text-gray-900"}>
          {marked}
        </mark>
      )}
      {!hasMark && marked}
      {after}
    </p>
  </div>
);
```

**Step 5: Run frontend checks**

Run: `cd frontend && nvm use && npm run type-check && npm run lint`
Expected: both PASS.

**Step 6: Commit**

```bash
git add frontend/src/features/evidence-search/types/evidenceSearch.ts \
        frontend/src/features/evidence-search/components/EvidenceDetailView.tsx \
        frontend/src/features/evidence-search/components/EvidenceHighlightText.tsx
git commit -m "feat(evidence-ui): add bilingual value anchors and highlight-unavailable hint"
```

---

### Task 4: Frontend — Compact side-by-side comparison layout

**Files:**
- Modify: `frontend/src/features/evidence-search/components/EvidenceDetailView.tsx`
- Create: `frontend/src/features/evidence-search/components/BilingualComparison.tsx`

**Step 1: Extract a small reusable comparison component**

Create `frontend/src/features/evidence-search/components/BilingualComparison.tsx`. It receives one `EvidenceTrackTrace` and renders the whole value-anchor + dual-snippet panel. Keep it small (<60 lines) — this is a structural extraction, not a new abstraction layer.

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

**Step 2: Use it from `EvidenceDetailView`**

In `EvidenceDetailView.tsx`, replace the inline traceability body with `<BilingualComparison trace={selectedTrace} />`. Remove the now-redundant header and grid code from the detail view.

**Step 3: Run frontend checks**

Run: `cd frontend && nvm use && npm run type-check && npm run lint`
Expected: both PASS.

**Step 4: Commit**

```bash
git add frontend/src/features/evidence-search/components/BilingualComparison.tsx \
        frontend/src/features/evidence-search/components/EvidenceDetailView.tsx
git commit -m "refactor(evidence-ui): extract BilingualComparison for trace panel"
```

---

### Task 5: Integration verification

**Step 1: Backend regression pass**

Run: `cd backend && uv run pytest tests/ -v`
Expected: all PASS.

**Step 2: Frontend build pass**

Run: `cd frontend && nvm use && npm run build`
Expected: clean build, no type or lint warnings.

**Step 3: Manual smoke test**

Start the stack (`docker compose up` or dev servers) and open an evidence detail page that has bilingual traces. Verify:

- The value pair banner shows original + translated values for the selected evidence item.
- When the backend located a highlight, it appears in yellow.
- When the backend could not locate a highlight, a small "highlight unavailable" chip appears and the snippet is shown unmarked.
- Switching between evidence items updates the value banner and both snippets together.

**Step 4: Update progress and lesson logs**

Append to `progress.txt`:

```
[2026-06-08] [Bilingual comparison UX: value anchors + highlight hardening + comparison panel] [Completed]
```

If any debugging detours happened, record them in `lesson.md` per project rules.

**Step 5: Final commit (if any cleanup)**

```bash
git add -A
git commit -m "chore: sync bilingual comparison follow-ups"
```

---

## Out of Scope (future increments)

- **Sentence-level interleaving** — aligning original and translated sentences one-to-one for line-by-line reading. Requires sentence splitting on both tracks and a similarity matcher; defer until real usage shows the value-anchor approach is insufficient.
- **PDF page preview pane** — showing the original PDF page with the evidence region boxed. Needs a PDF renderer and bbox grounding that is not yet reliable for all tracks.
- **Term-glossary hover** — popping a bilingual term map on hover over medical tokens. Requires terminology persistence that lives in the translator module; separate feature.

