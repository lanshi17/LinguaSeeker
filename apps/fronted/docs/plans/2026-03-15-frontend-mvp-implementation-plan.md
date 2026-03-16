# Frontend MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship a working React+TS+Vite frontend implementing the PRD MVP flow using the current OpenAPI contract (`api_docs/openapi.json`).

**Architecture:** React Router pages for the workflow (task create/clarify → upload or PubMed candidates → request monitor → results → export). Centralized API service layer, Zustand store for shared state, schema-tolerant evidence normalization (OpenAPI returns `data: object`).

**Tech Stack:** React 19, TypeScript, Vite, React Router DOM, Zustand, DOMPurify, Vitest.

---

## Notes / Constraints

- Repo policy: **do not create git commits unless explicitly requested**.
- Verify with:
  - `npm run lint`
  - `npx tsc --noEmit`
  - `npm run build`
  - `npm run test:run`

---

## Task 1: Restore Vite entrypoints and baseline app shell

**Files:**
- Create: `index.html`
- Create: `vite.config.ts`
- Create: `src/main.tsx`
- Create: `src/App.tsx`
- Create: `src/router/index.tsx`
- Create: `src/assets/globals.css`
- Create: `src/components/layout/app-shell.tsx`
- Create: `src/components/feedback/notification-toast.tsx`
- Create: `src/store/useToastStore.ts`
- Create: `src/utils/globalErrorHandler.ts`

**Step 1: Add `index.html` + `src/main.tsx`**

Expected: `npm run build` no longer fails due to missing entry.

**Step 2: Add router skeleton**

Include placeholder routes for pages (implemented in later tasks).

**Step 3: Add global CSS variables + basic layout**

Keep styling minimal and responsive.

---

## Task 2: Add ESLint flat config and basic project hygiene

**Files:**
- Create: `eslint.config.js`
- Create: `src/vite-env.d.ts`

**Step 1: ESLint config**

Configure for TS/React, disable overly strict rules that conflict with existing tsconfig (strict=false), but keep hooks rules.

**Step 2: Run lint**

Run: `npm run lint`
Expected: PASS.

---

## Task 3: API layer (typed wrappers + error handling)

**Files:**
- Create: `src/config/env.ts`
- Create: `src/types/api.ts`
- Create: `src/services/http.ts`
- Create: `src/services/api.ts`

**Step 1: Define API base URL**

Read `VITE_API_BASE_URL` (fallback `/api/v1`).

**Step 2: Implement `requestJson` + `requestFormData`**

Use `fetch`, `AbortController`, and a unified error type (preserve HTTP status + backend code/message/detail if present).

**Step 3: Implement endpoint wrappers**

- interaction start/respond
- pubmed candidates/submit
- upload
- request status
- logs reissue
- evidence document

---

## Task 4: Validation helpers (upload + selection limits)

**Files:**
- Create: `src/utils/validation.ts`
- Test: `src/utils/validation.test.ts`

**Step 1: Write failing tests for upload rules**

Test limits: file count, per-file size, total size, allowed extensions.

**Step 2: Implement `validateUploadFiles(files: File[]): ValidationResult`**

Return structured errors with codes.

---

## Task 5: Evidence normalization (schema-tolerant)

**Files:**
- Create: `src/types/evidence.ts`
- Create: `src/utils/normalizeEvidence.ts`
- Test: `src/utils/normalizeEvidence.test.ts`

**Step 1: Write tests for three decoding tiers**

1) `segments`-style payload → full model
2) `source_text` + `translated_text` → paragraph split, highlight disabled
3) unknown object → fallback model with `raw`

**Step 2: Implement `normalizeEvidence(data: unknown): EvidenceViewModel`**

No `any`. Use narrow checks and safe defaults.

---

## Task 6: Pages (workflow)

**Files:**
- Create: `src/pages/login/login-page.tsx`
- Create: `src/pages/login/register-page.tsx`
- Create: `src/pages/tasks/task-new-page.tsx`
- Create: `src/pages/tasks/pubmed-candidates-page.tsx`
- Create: `src/pages/requests/request-monitor-page.tsx`
- Create: `src/pages/documents/document-page.tsx`
- Create: `src/pages/requests/request-export-page.tsx`
- Create: `src/hooks/useRequestPolling.ts`

**Step 1: Login/Register placeholders**

UI-only pages explaining backend auth is not available yet.

**Step 2: Task new page**

- TaskFormStructured fields
- Clarification session via interaction endpoints (round ≤ 2)
- Two actions: "Upload" / "Search PubMed"

**Step 3: PubMed candidates page**

- Fetch candidates
- Pagination (max 15)
- Selection 1–10 enforced
- Submit → navigate to `/requests/:requestId`

**Step 4: Request monitor page**

- Poll request status
- Render per-paper statuses
- Reissue log link button with 429 handling

**Step 5: Document results page**

- Fetch evidence document
- Use `normalizeEvidence`
- Dual-tab reading/judgment UI
- DOMPurify sanitization where needed

**Step 6: Export page**

- Print layout
- `@media print` to enforce 2 pages
- Export button triggers `window.print()`

---

## Task 7: Final verification

Run:

```bash
npm run lint
npx tsc --noEmit
npm run test:run
npm run build
```

Expected: all commands exit 0.
