# Evidence DB Field Model Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** in-progress (Tasks 1-6 and 8-9 complete; Task 7 product-gated)
**Created:** 2026-06-29
**Completed:** -
**PR:** -

**Goal:** Improve the Evidence Database frontend field model so each route shows the fields that match its user task: find variants, judge evidence quality, then verify source text.

**Architecture:** Keep the existing three-level Evidence DB architecture. L1 `VariantIndexView` remains a scan-and-filter index, L2 `VariantDetailView` becomes the evidence-quality summary, and L3 `BilingualEvidenceView` remains the source-verification reader. Prefer front-end derived metrics first; add backend/API fields only where the current contracts cannot express the user-facing state.

**Tech Stack:** Vite + React + TypeScript strict mode, Ant Design, React Query, existing `frontend/src/features/evidence-db/` vertical slice, FastAPI `/api/v1/evidence/*` contracts when backend fields are needed.

---

## Current Findings

- L1 already shows the right core fields: gene, variant, disease, classification, evidence groups, literature refs, confidence, category strip, updated date.
- L2 already groups evidence by category and references by literature source, with a small original/translated preview.
- L3 already shows document title, PMID/DOI, evidence field count, confidence, export action, category filters, evidence navigation, active evidence card, original and translated readers.
- Frontend types do not expose `original_document_text` and `translated_document_text` on `EvidenceSearchResult`, although the backend model currently includes them.
- Backend contracts do not currently expose `reviewed_at`, `reviewer`, `conflict_count`, `evidence_completeness`, `has_full_text`, or `has_translation` as first-class summary fields.

## Target Field Model

### L1: Variant Index

Keep visible columns compact:

- Gene / Variant
- Disease
- Classification
- Evidence groups
- Literature refs
- Confidence
- Category coverage
- Review progress
- Updated

Do not add PMID, DOI, title, UUID, or per-field values to L1.

### L2: Variant Detail

Make this the decision-quality view:

- Hero: gene, variant, disease, classification, confidence.
- Summary metrics: evidence groups, literature count, total fields, categories, review progress, coverage score, conflict count.
- Evidence category panels: field name, value, confidence, review status, track.
- Literature references: title, PMID/DOI, field count, confidence, categories, full-text availability, translation availability, review status.

### L3: Literature Reader

Make this the verification view:

- Header: title, PMID, DOI, field count, confidence, full-text/translation badges, review status, export report.
- Sidebar: category filters, evidence field navigator, review-status filter.
- Active evidence card: field name, value, field id, category, confidence, review status, track, page, source span availability.
- Reader panels: original/translated text and highlights.

---

## Phase 1: Frontend-Only Derived Fields

**Status:** completed on 2026-06-29. Tasks 1-5 were implemented with frontend-derived metrics only.

### Task 1: Add Evidence DB view-model helpers

**Files:**
- Create: `frontend/src/features/evidence-db/utils/fieldModel.ts`
- Test: `frontend/tests/evidence-db/fieldModel.test.ts`

**Step 1: Write failing tests**

Cover these pure functions:

- `computeReviewProgress(items)` returns counts and percent for approved/corrected/rejected/provisional.
- `computeCoverage(distribution)` returns covered category count and percent over `EVIDENCE_CATEGORIES.length`.
- `computeConflictCount(items)` counts category `H` items and items whose field id starts with `H.`.
- `hasFullText(detail)` returns true when original text or original blocks exist.
- `hasTranslation(detail)` returns true when translated text, translated blocks, or translated trace text exists.

Run:

```bash
cd frontend
bun run test tests/evidence-db/fieldModel.test.ts
```

Expected before implementation: FAIL because `fieldModel.ts` does not exist.

**Step 2: Implement minimal helpers**

Use existing contracts:

- `EvidenceGroupDetailResponse`
- `EvidenceGroupItem`
- `EvidenceFieldDistribution`
- `EVIDENCE_CATEGORIES`

Return named TypeScript interfaces, for example:

```ts
export interface ReviewProgress {
  total: number;
  reviewed: number;
  approved: number;
  corrected: number;
  rejected: number;
  provisional: number;
  reviewedPercent: number;
}
```

**Step 3: Verify**

Run:

```bash
cd frontend
bun run test tests/evidence-db/fieldModel.test.ts
bun run type-check
```

Expected: tests pass and TypeScript passes.

### Task 2: Extend L1 VariantIndexEntry with derived review progress

**Files:**
- Modify: `frontend/src/features/evidence-db/types/variantDb.ts`
- Modify: `frontend/src/features/evidence-db/utils/variantAggregation.ts`
- Modify: `frontend/src/features/evidence-db/components/VariantIndexView.tsx`
- Test: `frontend/tests/evidence-db/variantAggregation.test.tsx`

**Step 1: Write failing tests**

Add tests proving `aggregateVariants()` computes:

- `reviewProgress.reviewed`
- `reviewProgress.reviewedPercent`
- `reviewProgress.rejected`

Use mixed `review_status` values in synthetic `EvidenceSearchResult[]`.

**Step 2: Implement aggregation**

Add `reviewProgress` to `VariantIndexEntry`. Compute from grouped search rows, not from detail rows, so L1 remains cheap.

**Step 3: Update L1 UI**

Replace or augment the current category-strip area with a compact review-progress indicator:

- keep category strip visible;
- add a small `Reviewed 3/5` text or progress bar in the same column group;
- keep table width stable at desktop and collapse into mobile stats on small screens.

**Step 4: Verify**

Run:

```bash
cd frontend
bun run test tests/evidence-db/variantAggregation.test.tsx
bun run type-check
```

Expected: pass.

### Task 3: Add L2 quality summary metrics

**Files:**
- Modify: `frontend/src/features/evidence-db/hooks/useVariantDetail.ts`
- Modify: `frontend/src/features/evidence-db/types/variantDb.ts`
- Modify: `frontend/src/features/evidence-db/components/VariantDetailView.tsx`
- Test: `frontend/tests/evidence-db/fieldModel.test.ts`

**Step 1: Write failing tests**

Use detail-shaped fixtures to prove:

- coverage percent is based on categories with non-zero evidence;
- conflict count comes from category `H`;
- review progress ignores empty item lists safely.

**Step 2: Add `quality` to `VariantDetailData`**

Recommended shape:

```ts
interface VariantQualitySummary {
  reviewProgress: ReviewProgress;
  coverage: EvidenceCoverage;
  conflictCount: number;
}
```

Compute from `evidenceGroups.flatMap((g) => g.items)` and group distributions.

**Step 3: Update hero stats**

In `VariantDetailView`, change the four stat tiles from only `groups/literature/fields/categories` to:

- Literature
- Evidence fields
- Coverage
- Reviewed

Show conflict count as a warning chip only when `conflictCount > 0`.

**Step 4: Verify**

Run:

```bash
cd frontend
bun run test tests/evidence-db/fieldModel.test.ts tests/evidence-db/variantAggregation.test.tsx
bun run type-check
```

Expected: pass.

### Task 4: Improve L2 literature reference cards

**Files:**
- Modify: `frontend/src/features/evidence-db/types/variantDb.ts`
- Modify: `frontend/src/features/evidence-db/hooks/useVariantDetail.ts`
- Modify: `frontend/src/features/evidence-db/components/VariantDetailView.tsx`
- Test: `frontend/tests/evidence-db/fieldModel.test.ts`

**Step 1: Write failing tests**

Create fixture `EvidenceGroupDetailResponse` values and verify a derived `LiteratureReference` includes:

- `hasFullText`
- `hasTranslation`
- `reviewProgress`
- `conflictCount`

**Step 2: Extend `LiteratureReference`**

Add:

```ts
hasFullText: boolean;
hasTranslation: boolean;
reviewProgress: ReviewProgress;
conflictCount: number;
```

**Step 3: Update card display**

In `LiteratureReferenceCard`:

- keep title and PMID/DOI;
- show `Full text` badge when `hasFullText`;
- show `Translated` badge when `hasTranslation`;
- show `Reviewed x/y`;
- show conflict warning only when non-zero.

Do not add UUIDs or long technical metadata to the visible card.

**Step 4: Verify**

Run:

```bash
cd frontend
bun run test tests/evidence-db/fieldModel.test.ts
bun run type-check
```

Expected: pass.

### Task 5: Add L3 reader header and evidence filter refinements

**Files:**
- Modify: `frontend/src/features/evidence-db/components/LiteratureHeader.tsx`
- Modify: `frontend/src/features/evidence-db/components/BilingualEvidenceView.tsx`
- Modify: `frontend/src/features/evidence-db/components/BilingualSidebar.tsx`
- Modify: `frontend/src/features/evidence-db/components/ActiveEvidenceCard.tsx`
- Test: `frontend/tests/evidence-db/LiteratureHeader.test.tsx`

**Step 1: Write failing tests**

Extend `LiteratureHeader.test.tsx` to verify:

- `Full text` badge renders when provided;
- `Translated` badge renders when provided;
- `Reviewed x/y` renders from review progress;
- export button still calls `onExportReport`.

**Step 2: Extend `LiteratureHeader` props**

Pass a small `quality` object from `BilingualEvidenceView`:

```ts
interface LiteratureHeaderQuality {
  hasFullText: boolean;
  hasTranslation: boolean;
  reviewProgress: ReviewProgress;
}
```

**Step 3: Add review-status filtering in sidebar**

In `BilingualEvidenceView`, add local state:

```ts
const [enabledStatuses, setEnabledStatuses] = useState<Set<string>>(...)
```

Filter evidence navigator items by both category and review status. Keep the document highlights category-driven only unless user confirms status-based highlight filtering is desired.

**Step 4: Update active evidence card**

Show `review_status` alongside confidence/track/page.

**Step 5: Verify**

Run:

```bash
cd frontend
bun run test tests/evidence-db/LiteratureHeader.test.tsx
bun run type-check
```

Expected: pass.

---

## Phase 2: Backend/API Field Additions

Only start this phase after Phase 1 is merged or accepted.

**Status:** review-gated. Do not start until the frontend-only field model is accepted.

### Task 6: Expose full-text and translation availability in search results

**Status:** completed on 2026-06-29.

**Files:**
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py`
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py`
- Modify: `frontend/src/features/evidence-search/types/evidenceSearch.ts`
- Test: relevant backend search service tests, or create `backend/tests/core/visualize_evidence_with_expert_in_loop/test_search_service_fields.py`

**API fields:**

```py
has_full_text: bool = False
has_translation: bool = False
```

Use existing data sources:

- `original_document_text`
- `translated_document_text`
- `original_blocks`
- `translated_blocks`

**Verification:**

```bash
cd backend
uv run pytest backend/tests/core/visualize_evidence_with_expert_in_loop/test_search_service_fields.py
uv run ruff check

cd ../frontend
bun run type-check
```

### Task 7: Add review metadata only if product requires named reviewers

**Files:**
- Backend model/repository depends on current audit storage; inspect before implementation.
- Likely touch: `backend/src/core/visualize_evidence_with_expert_in_loop/contracts.py`
- Likely touch: `backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py`
- Frontend touch: `frontend/src/features/evidence-search/types/evidenceSearch.ts`

**Fields to consider:**

- `reviewed_at`
- `reviewer_id`
- `reviewer_display_name`

**Decision gate:** Do not implement until the product decision is clear: should the UI expose individual reviewer identity, or only aggregate review progress?

---

## Phase 3: UX Cleanup and Field Configuration

### Task 8: Add column/display preferences for advanced users

**Status:** completed on 2026-06-29.

**Files:**
- Create: `frontend/src/features/evidence-db/hooks/useEvidenceDbViewPrefs.ts`
- Modify: `frontend/src/features/evidence-db/components/VariantIndexView.tsx`
- Test: `frontend/tests/evidence-db/useEvidenceDbViewPrefs.test.tsx`

**Scope:**

- default compact field set;
- optional toggles for `Updated`, `Categories`, `Review progress`;
- persist in localStorage with safe parsing.

Do not expose PMID/DOI/title on L1 by default.

### Task 9: Move field labels and metric formatting to shared helpers

**Status:** completed on 2026-06-29.

**Files:**
- Create: `frontend/src/features/evidence-db/utils/fieldLabels.ts`
- Modify: `VariantIndexView.tsx`
- Modify: `VariantDetailView.tsx`
- Modify: `LiteratureHeader.tsx`

**Goal:** Reduce repeated copy, keep labels consistent, and prepare for localization.

---

## Acceptance Criteria

- L1 remains scannable on desktop and mobile, with no horizontal overflow.
- L2 shows coverage, review progress, and conflict count without requiring the user to inspect every evidence card.
- L2 literature cards clearly show whether opening the reader will provide full text and translation.
- L3 header shows document identity plus export/report actions and source availability.
- No new API fields are invented in frontend types unless backend contracts expose them.
- `bun run test`, `bun run type-check`, `bun run lint`, and `bun run build` pass for frontend changes.
- Backend phase, if implemented, passes `uv run pytest` and `uv run ruff check`.

## Current Checkpoint

**2026-06-29 implementation checkpoint:** Tasks 1-6 and 8-9 are implemented and verified. The L3 active evidence card also shows source span availability from existing trace data, closing the L3 target field model. Task 6 adds first-class search-result availability flags without loading full document text into search responses.

Fresh frontend verification:

```bash
cd frontend
bun run test        # 16 files, 82 tests passed
bun run type-check  # passed
bun run lint        # 0 errors, 13 existing fast-refresh warnings
bun run build       # passed; existing chunk-size warning remains
```

Remaining work is intentionally gated:

- Task 7 requires a product decision on whether reviewer identity should be exposed.

## Recommended Execution Order

1. Task 1: pure helpers and tests.
2. Task 2: L1 review progress.
3. Task 3: L2 quality summary.
4. Task 4: L2 literature cards.
5. Task 5: L3 reader header/filter refinements.
6. Stop and review with users.
7. Only then start Phase 2 backend/API additions.
