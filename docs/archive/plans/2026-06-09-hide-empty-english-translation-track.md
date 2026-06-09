# Hide Empty English Translation Track Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Status:** completed
**Created:** 2026-06-09
**Completed:** 2026-06-09
**PR:** —

**Goal:** Hide the empty `English translation` reader in the bilingual evidence detail view when the source document is already English and no translated text exists.

**Architecture:** Keep translated-track visibility based on raw API data, not the filtered reader output. `EvidenceDetailView` builds original and translated reader documents, calls `hasTranslatedDocumentText(detail)` to decide whether a translated track exists, and renders a one-column or two-column reader layout accordingly.

**Tech Stack:** Next.js App Router, React 18, TypeScript, Tailwind CSS, Node built-in test runner.

---

### Task 1: Add Track-Availability Regression Tests

**Files:**
- Modify: `frontend/tests/evidence-search/literatureRows.test.ts`
- Test target: `frontend/src/features/evidence-search/utils/evidenceDocument.ts`

**Step 1: Import the translated-track availability helper**

Add `hasTranslatedDocumentText` to the existing import from `evidenceDocument`. Preserve all already-used category exports:

```ts
import {
  buildEvidenceDocument,
  countEvidenceHighlightTones,
  hasTranslatedDocumentText,
} from "../../src/features/evidence-search/utils/evidenceDocument";
```

If the import block has additional existing symbols, preserve them. Do not replace the block wholesale.

**Step 2: Write tests for no translated content and visibility-gate edge cases**

Append these tests in the existing `describe("evidence document helpers", () => { ... })` block:

```ts
  it("builds no translated paragraphs when translated trace and full text are null", () => {
    const detail: EvidenceGroupDetailResponse = {
      ...DETAIL,
      original_document_text: "PHARC syndrome is caused by mutations in ABHD12.",
      translated_document_text: null,
      traces: [{
        canonical_evidence_id: "ev-a",
        field_id: "A.gene_disease_relationship",
        field_name: "Gene-Disease Relationship",
        original_value: "causative",
        translated_value: null,
        alignment_confidence: null,
        original: {
          text: "PHARC syndrome is caused by mutations in ABHD12.",
          highlight_start: 0,
          highlight_end: 14,
          source_span: {},
        },
        translated: null,
      }],
    };

    const originalDocument = buildEvidenceDocument(detail, "original");
    const translatedDocument = buildEvidenceDocument(detail, "translated");

    assert.equal(originalDocument.paragraphs.length, 1);
    assert.equal(translatedDocument.paragraphs.length, 0);
  });

  it("builds no translated paragraphs when translated full text is undefined", () => {
    const detail: EvidenceGroupDetailResponse = {
      ...DETAIL,
      original_document_text: "PHARC syndrome is caused by mutations in ABHD12.",
      translated_document_text: undefined,
      traces: [{
        canonical_evidence_id: "ev-a",
        field_id: "A.gene_disease_relationship",
        field_name: "Gene-Disease Relationship",
        original_value: "causative",
        translated_value: null,
        alignment_confidence: null,
        original: {
          text: "PHARC syndrome is caused by mutations in ABHD12.",
          highlight_start: 0,
          highlight_end: 14,
          source_span: {},
        },
        translated: null,
      }],
    };

    const translatedDocument = buildEvidenceDocument(detail, "translated");

    assert.equal(translatedDocument.paragraphs.length, 0);
  });
```

**Step 3: Run the focused test**

Run:

```bash
cd frontend
nvm use
npm test
```

Expected: PASS. These tests document the data-layer contract and the visibility-gate predicate: no translated content produces `translatedDocument.paragraphs.length === 0`, whitespace-only translated text is ignored, and non-empty translated full text or trace text makes the translated track available.

### Task 2: Hide The Empty Translated Reader In The Compare View

**Files:**
- Modify: `frontend/src/features/evidence-search/components/EvidenceDetailView.tsx`
- Depends on: `frontend/src/features/evidence-search/utils/evidenceDocument.ts`

**Step 1: Leave the evidenceDocument import intact**

Do not replace the existing import block. It currently includes category exports that are used throughout this component. Add `hasTranslatedDocumentText` while preserving the existing imports:

```ts
import {
  buildEvidenceDocument,
  CATEGORY_COLORS,
  EVIDENCE_CATEGORIES,
  countEvidenceCategories,
  hasTranslatedDocumentText,
  type EvidenceDocumentHighlight,
  type EvidenceDocumentParagraph,
} from "../utils/evidenceDocument";
```

If the live import block differs, preserve all existing used imports.

**Step 2: Compute translated track availability from raw API data**

Inside `BilingualComparison`, after `translatedDocument` is created, add:

```ts
  // Data availability ignores user-applied filters so category toggles do not mount/unmount
  // the translated reader or reflow the document grid.
  const showTranslatedDocument = hasTranslatedDocumentText(detail);
```

**Step 3: Render one or two columns based on availability**

Replace the current reader grid:

```tsx
          <div className="grid gap-4 xl:grid-cols-2">
            <EvidenceDocumentReader
              title="Original document"
              paragraphs={originalDocument.paragraphs}
            />
            <EvidenceDocumentReader
              title="English translation"
              paragraphs={translatedDocument.paragraphs}
            />
          </div>
```

with:

```tsx
          <div
            className={cn(
              "grid gap-4",
              showTranslatedDocument && "xl:grid-cols-2",
            )}
          >
            <EvidenceDocumentReader
              title="Original document"
              paragraphs={originalDocument.paragraphs}
            />
            {showTranslatedDocument && (
              <EvidenceDocumentReader
                title="English translation"
                paragraphs={translatedDocument.paragraphs}
              />
            )}
          </div>
```

**Step 4: Confirm no empty reader UI remains**

Manual check in browser after implementation:

1. Open the affected compare page with an English original and no translated text.
2. Confirm the `Original document` reader is shown.
3. Confirm `English translation`, `0 aligned paragraphs`, and `No document text is available for this track.` are not shown.
4. Confirm non-English records with translated paragraphs still show both readers.

### Task 3: Run Verification

**Files:**
- Verify: `frontend/src/features/evidence-search/components/EvidenceDetailView.tsx`
- Verify: `frontend/tests/evidence-search/literatureRows.test.ts`

**Step 1: Run focused tests**

Run:

```bash
cd frontend
nvm use
npm test
```

Expected: PASS.

**Step 2: Run frontend lint**

Run:

```bash
cd frontend
nvm use
npm run lint
```

Expected: PASS with no new warnings.

**Step 3: Run frontend type check**

Run:

```bash
cd frontend
nvm use
npm run type-check
```

Expected: PASS.

### Task 4: Update Project Records

**Files:**
- Modify: `progress.txt`
- Modify only if troubleshooting changed during implementation: `lesson.md`

**Step 1: Record completion in progress**

Append:

```text
[2026-06-09] Hide empty English translation track in bilingual evidence view [completed]
```

**Step 2: Add a lesson only if implementation uncovers a new issue**

If tests, lint, or runtime checks reveal an unexpected failure, add a short retrospective to `lesson.md` with:

- Problem description
- Investigation process
- Root cause
- Solution
- Prevention

### Task 5: Commit The Implementation

**Files:**
- Stage only files changed for this task.

**Step 1: Review diff**

Run:

```bash
git diff -- frontend/src/features/evidence-search/components/EvidenceDetailView.tsx frontend/tests/evidence-search/literatureRows.test.ts progress.txt lesson.md
```

Expected: Diff only contains the compare-view conditional rendering, focused tests, and required project records.

**Step 2: Commit**

Use the repository git workflow and Conventional Commits:

```bash
git add frontend/src/features/evidence-search/components/EvidenceDetailView.tsx frontend/tests/evidence-search/literatureRows.test.ts progress.txt lesson.md
git commit -m "fix: hide empty evidence translation track"
```

Expected: Commit succeeds. Do not push to `master`.
