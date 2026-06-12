# Code Review: /evidence Page

**Date:** 2026-06-12
**Scope:** `frontend/app/(dashboard)/evidence/` + `frontend/src/features/evidence-search/`
**Reviewer:** Claude Fable 5

---

## 1. Summary

Evidence feature 提供文献级别的 ACMG 证据搜索与审阅界面。搜索页支持 Gene/Variant/Disease/PMID 过滤，结果按文献聚合后分页展示。详情页提供 Overview（元数据+证据列表）和 Compare（原文/译文并排高亮对比）两种视图。

**Overall verdict: Well-structured, clean code.** 模块划分清晰，类型定义完整，测试覆盖核心工具函数。以下按严重程度列出发现项。

---

## 2. Findings

### 2.1 Medium -- `applyFilters` is a no-op on initial mount

**File:** `frontend/src/features/evidence-search/hooks/useEvidenceSearch.ts:16-19`

React Query with `queryKey: ["evidence", "search", filters]` will fire automatically whenever `filters` changes. The `applyFilters` function calls `query.refetch()`, but this is redundant — changing `filters` already triggers a new query. The only case `refetch()` adds value is when the user clicks "Search" without changing any filter values, which is a rare edge case.

The real problem: `updateFilter` (line 23-30) sets `page` back to 1 on every keystroke, which means the query fires on every keystroke because `filters` is in the query key. This is wasteful — the API is called for every character typed.

**Recommendation:** Either debounce `filters` state before passing to `useQuery`, or separate the "draft" form state from the "committed" query state. The current pattern fires N API calls when the user types "BRCA1" (one per character).

### 2.2 Medium -- `categoryFromItem` duplicated across two files

**File:** `frontend/src/features/evidence-search/utils/evidenceDocument.ts:119-127` and `frontend/src/features/evidence-search/components/EvidenceDetailView.tsx:95-103`

The `categoryFromItem` function is defined identically in both files. This creates a maintenance risk where one copy could be updated and the other forgotten.

**Recommendation:** Remove the local copy in `EvidenceDetailView.tsx` and import from `evidenceDocument.ts` (the utility already exports other functions used by the component).

### 2.3 Medium -- `STATUS_VARIANT` and `formatPercent` duplicated

**File:** `frontend/src/features/evidence-search/components/EvidenceResultsTable.tsx:28-43` and `frontend/src/features/evidence-search/components/EvidenceDetailView.tsx:49-93`

`STATUS_VARIANT` and `formatPercent` are defined identically in both component files. Any status variant or formatting change requires updating both.

**Recommendation:** Extract to a shared utility (e.g., `utils/format.ts` or add to `evidenceDocument.ts`).

### 2.4 Low -- `EvidenceDetailView` is ~880 lines with 7 inline components

**File:** `frontend/src/features/evidence-search/components/EvidenceDetailView.tsx`

This file defines `MetadataToken`, `EvidenceTonePill`, `EvidenceItemSummary`, `LiteratureOverview`, `CategoryLayerToggle`, `BilingualComparison`, and `HighlightedParagraph` as local components. While colocation is reasonable for tightly coupled UI, the file is approaching the point where splitting improves navigability.

**Recommendation:** Consider extracting `BilingualComparison` and `LiteratureOverview` into separate files under `components/detail/`. This keeps the main file under 300 lines and makes each view independently testable.

### 2.5 Low -- `buildLiteratureRows` called on every render of `EvidenceResultsTable`

**File:** `frontend/src/features/evidence-search/components/EvidenceResultsTable.tsx:120`

`buildLiteratureRows(results)` runs on every render. The function groups, merges, and sorts results — for large result sets (page_size=50, each with multiple groups), this could cause unnecessary re-computation.

**Recommendation:** Wrap in `useMemo(() => buildLiteratureRows(results), [results])`.

### 2.6 Low -- `enabledTones` state is set once and never toggled

**File:** `frontend/src/features/evidence-search/components/EvidenceDetailView.tsx:574`

```tsx
const [enabledTones] = useState<Set<EvidenceHighlightTone>>(
  () => new Set(HIGHLIGHT_TONES),
);
```

This is initialized but never modified — there is no UI to toggle tones. The `enabledTones` parameter is passed to `buildEvidenceDocument` but always contains all tones. This is dead code in practice (the Set is always full).

**Recommendation:** Either add tone toggle UI, or remove the `enabledTones` parameter from `buildEvidenceDocument` and simplify the filtering logic. If it's planned for a future iteration, add a `// TODO` comment to clarify intent.

### 2.7 Low -- `useEvidenceSearch` dependency array in `applyFilters`

**File:** `frontend/src/features/evidence-search/hooks/useEvidenceSearch.ts:37-39`

```tsx
const applyFilters = useCallback(() => {
  query.refetch();
}, [query]);
```

The `query` object from React Query is a new reference on every render, so this `useCallback` provides no memoization benefit — `applyFilters` is recreated every render regardless.

**Recommendation:** Change dependency to `query.refetch` which is a stable reference.

### 2.8 Info -- Error display leaks raw error message

**File:** `frontend/src/features/evidence-search/components/EvidenceSearchView.tsx:44-46`

```tsx
<p className="text-sm text-red-600">
  Failed to load evidence: {error.message}
</p>
```

`error.message` may contain internal details (stack traces, network errors). The project has `extractErrorMessage()` in `lib/api/error.ts` which sanitizes errors for display.

**Recommendation:** Use `extractErrorMessage(error)` instead of `error.message`.

### 2.9 Info -- `EvidenceHighlightText` exported but unused

**File:** `frontend/src/features/evidence-search/components/EvidenceHighlightText.tsx` + `index.ts:4`

This component is exported from the barrel but not used by any evidence page component. It appears to be a reusable utility for external consumers.

**Recommendation:** Document its intended external use, or remove from the barrel export if not needed.

### 2.10 Info -- `EVIDENCE_CATEGORIES` is derived at module level

**File:** `frontend/src/features/evidence-search/utils/evidenceDocument.ts:94`

```tsx
export const EVIDENCE_CATEGORIES = Object.keys(CATEGORY_COLORS);
```

This is fine functionally, but `Object.keys()` order is insertion order in modern JS, so the categories render in A-J order. If `CATEGORY_COLORS` is ever reordered or extended, the display order would change silently.

**Recommendation:** This is acceptable as-is given the stable ACMG category set. No action needed.

---

## 3. Architecture Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| Module structure | Good | Clean vertical slice: types, services, hooks, components, utils |
| Type safety | Good | All API contracts typed; no `any` usage found |
| State management | Good | React Query for server state, local state for UI — appropriate for feature scope |
| Test coverage | Adequate | Core utility functions tested; no component tests |
| Accessibility | Good | Keyboard navigation on table rows, `aria-label` on interactive elements, `sr-only` inputs |
| Responsive design | Good | Mobile card layout + desktop table; responsive grid on detail page |
| Error handling | Adequate | ErrorBoundary wraps sections; API errors displayed (but see 2.8) |

---

## 4. Test Coverage Gaps

The test file covers utility functions well:
- `buildLiteratureRows` -- grouping, merging, null handling
- `findInitialEvidenceId` -- selection priority
- `buildBilingualCompareHref` -- URL construction
- `buildEvidenceDocument` -- highlight filtering, fallback paths
- `countEvidenceHighlightTones` -- tone counting
- `hasTranslatedDocumentText` -- whitespace/null edge cases

**Missing:**
- No component rendering tests (React Testing Library)
- No integration test for search -> navigate -> detail flow
- No test for `normalizedHighlights` overlap deduplication logic
- No test for `findAnchorValue` regex safety (2-char uppercase guard)

---

## 5. Positive Highlights

1. **Clean data flow**: Search filters -> React Query -> row aggregation -> table display. No unnecessary indirection.
2. **Highlight positioning**: `findHighlightInFullText` has a 3-tier fallback (anchor value -> highlighted text -> full snippet) that gracefully handles backend inconsistencies in highlight offsets.
3. **Category color system**: `CATEGORY_COLORS` with hex/chip/mark variants is well-organized and makes the ACMG category system visually intuitive.
4. **Responsive table**: Mobile card layout and desktop table are both well-implemented with proper ARIA roles.
5. **`buildLiteratureRows` aggregation**: Weighted average confidence calculation and "mixed" review status handling are correct and tested.

---

## 6. Recommended Actions (Priority Order)

| # | Action | Severity | Effort |
|---|--------|----------|--------|
| 1 | Debounce search filter input or separate draft/committed state | Medium | ~1h |
| 2 | Deduplicate `categoryFromItem` | Medium | ~10min |
| 3 | Deduplicate `STATUS_VARIANT` and `formatPercent` | Medium | ~20min |
| 4 | Memoize `buildLiteratureRows` in `EvidenceResultsTable` | Low | ~5min |
| 5 | Clarify or remove `enabledTones` dead state | Low | ~10min |
| 6 | Fix `applyFilters` useCallback dependency | Low | ~5min |
| 7 | Use `extractErrorMessage` for error display | Info | ~5min |
| 8 | Split `EvidenceDetailView.tsx` into sub-files | Low | ~30min |
