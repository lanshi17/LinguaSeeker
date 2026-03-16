# Frontend Design (MVP)

Date: 2026-03-15

## 1. Goal

Implement a React 19 + TypeScript + Vite frontend for the Multi-ACMG workflow described in:

- `docs/PRD.md`
- `docs/APP_FLOW.md`
- `docs/FRONTEND_GUIDELINES.md`

While staying contract-faithful to the current backend OpenAPI spec at `api_docs/openapi.json`.

## 2. Key Constraints (from PRD)

### 2.1 Upload limits (client-side)

- Formats: PDF, DOCX
- Max files: 10
- Max single file size: 10MB
- Max total size: 50MB

### 2.2 Candidate & selection limits

- Max candidates returned: 15
- Pagination: default 10/page, max 15/page
- User selection: min 1, max 10

### 2.3 Clarification rounds

- Max rounds: 2

## 3. Backend Contract Snapshot (OpenAPI)

The MVP flow is driven by these endpoints:

- Clarification:
  - `POST /api/v1/tasks/interaction/start`
  - `POST /api/v1/tasks/interaction/respond`
- PubMed candidates:
  - `POST /api/v1/tasks/requests/pubmed/candidates`
  - `POST /api/v1/tasks/requests/pubmed/submit` → returns `request_id`
- Upload:
  - `POST /api/v1/tasks/requests/upload` (multipart: `task_form` string + `files[]`)
- Monitoring:
  - `GET /api/v1/tasks/requests/{request_id}`
- Logs:
  - `GET /api/v1/logs/reissue?request_id=...` → `log_link` (24h), 429 rate limit
- Evidence:
  - `GET /api/v1/evidence/document/{document_id}` returns a generic `EvidenceSearchResponse`:
    - `{ code, message, data: object }`

### 3.1 Notable gap: authentication

OpenAPI currently does **not** include login/register endpoints, but PRD lists auth pages.

Design decision:
- Ship `/login` and `/register` as UI-only placeholders.
- API client supports pluggable auth headers (future-proof).
- Any future `401/403` should redirect to `/login`.

## 4. Routes & Pages

React Router DOM drives the app routes:

- `/` → redirect to `/tasks/new`
- `/login` → placeholder (backend auth not available)
- `/register` → placeholder (backend auth not available)

### 4.1 Main MVP flow

1) `/tasks/new`
- Enter `TaskFormStructured`: `{ goal, disease, country, language }`
- Start clarification session (round ≤ 2)
- Choose a path:
  - Upload PDFs/DOCX
  - PubMed candidates

2) `/tasks/pubmed/candidates`
- Fetch candidates (limit 15)
- Enforce selection 1–10
- Submit → receive `request_id` → navigate to `/requests/:requestId`

3) `/requests/:requestId`
- Monitor request-level status + per-paper status list
- Poll `GET /api/v1/tasks/requests/{request_id}` with adaptive interval
- Surface error codes and “reissue log_link” action

4) `/documents/:documentId`
- Dual-tab result view:
  - Tab A: bilingual reading (source vs translation)
  - Tab B: evidence judgment
- Highlighting is enabled only when backend provides structured spans/offsets; otherwise show fallbacks.

5) `/requests/:requestId/export`
- Print-to-PDF export view
- CSS print rules enforce **two pages** (Reading then Judgment)

## 5. State Management

Use Zustand for minimal global state:

- `taskForm`: the structured task form
- `interaction`: session_id, round, question, ready
- `requestStatusById`: cached snapshots from `GET /tasks/requests/{id}`
- `toasts`: global notifications

Polling should be page-scoped (monitor page) but can update store cache.

## 6. API Layer

All API calls go through `src/services/api.ts`.

Principles:

- No `any` types.
- Centralized error parsing:
  - Prefer backend-provided `detail` / `message` fields.
  - Preserve `error_code` where present.
- Handle `401/403` by redirecting to `/login` (future proof).
- For polling, use `setTimeout` loops (avoid overlapping requests) + `AbortController`.

## 7. Evidence Rendering (Contract-tolerant)

Because `EvidenceSearchResponse.data` is `object`, the UI must gracefully handle unknown shapes.

Design decision: introduce a front-end internal model:

```ts
type EvidenceViewModel = {
  sourceLang: string;
  targetLang: string;
  segments: Array<{
    id: string;
    sourceText: string;
    targetText: string;
    groupId?: string;
    highlights?: Array<{
      kind: 'evidence' | 'acmg' | 'user';
      sourceRanges?: Array<{ start: number; end: number }>;
      targetRanges?: Array<{ start: number; end: number }>;
      label?: string;
    }>;
  }>;
  raw?: unknown;
};
```

Normalization strategy:

1) If `data` contains structured segments + offsets → enable synchronized highlighting.
2) Else if `data` contains raw bilingual text fields → show side-by-side text, disable synchronized highlights.
3) Else → show a JSON viewer fallback with an “unsupported evidence format” banner.

All HTML content is sanitized with DOMPurify.

## 8. PDF Export

No dedicated PDF generator dependency is required for MVP.

Approach:

- Render an export route with print-optimized layout.
- Use `@media print` CSS rules to hide navigation and enforce page breaks.
- Trigger `window.print()`.

## 9. Verification Checklist

- `npm run lint`
- `npx tsc --noEmit`
- `npm run build`

## 10. Non-goals (for MVP)

- Real authentication flows (blocked by missing backend endpoints).
- Perfect highlight alignment without backend-provided spans/offsets.
