# FRONTEND_GUIDELINES — ACMG Lingua Frontend

## 1. Tech Stack

| Concern | Choice | Notes |
|---|---|---|
| Framework | Next.js 15 App Router | File-based routing, layouts, SSR |
| UI Library | React 18 | Concurrent features |
| Language | TypeScript 5.5+ | Strict mode |
| Styling | Tailwind CSS 3.4 | Utility-first, no CSS-in-JS |
| Client State | Zustand 4.5 | Minimal runtime state |
| Server State | React Query 5.50 | Caching, invalidation, polling fallback |
| HTTP | Axios 1.7 | Calls `/api/v1/*` through Next.js proxy |
| WebSocket | Native WebSocket API | Per-task processing status |
| Utilities | clsx 2.1 | Conditional class names |
| Linting | ESLint 8.57 + Next config | Google TypeScript Style |
| Type Check | TypeScript compiler | Current-stage frontend verification |

FastAPI is authoritative for authentication and API behavior. Next.js proxies requests and renders UI; it does not sign or verify JWTs.

## 2. Product UX Principles

### 2.1 Scope Safety

- **Evidence-first framing**: current UI presents extracted and standardized evidence, not final autonomous medical classification.
- **Non-diagnostic language**: reports and result pages must describe outputs as evidence summaries and extraction results.
- **No silent uncertainty**: low confidence, missing traceability, ambiguous standardization, and native/translated extraction disagreement must be visible.
- **Correction capture**: expert corrections should be structured so they can improve native extraction, translation, translated extraction, fusion, and standardization.

### 2.2 Bi-Directional Traceability First

- Every evidence item shown in the UI must link to an original source span.
- For translated content, every evidence item should also link to a translated-text span.
- Clicking an evidence item must highlight the original text/table/figure region and the translated text/table/figure region side by side.
- If a result lacks required anchors/bbox-backed spans, the UI should display it as invalid/incomplete rather than plausible.

### 2.3 Low-Friction Medical Professional UX

- Users are not expected to code or understand pipeline internals.
- Long-running tasks must show concrete stages and current progress.
- Confidence scores and fusion status should be displayed near the evidence they describe.
- Biomedical strings such as HGVS, rsIDs, transcript IDs, and gene symbols should use monospace formatting.

## 3. Directory Structure

```text
frontend/
├── app/
│   ├── api/                           # Proxy routes only when needed
│   ├── auth/
│   │   ├── login/page.tsx
│   │   ├── register/page.tsx
│   │   └── verify-email/page.tsx
│   ├── (dashboard)/
│   │   ├── layout.tsx                 # Sidebar + topbar layout
│   │   ├── analysis/page.tsx          # Upload/input/search + status UX
│   │   ├── results/[taskId]/page.tsx  # Bilingual source/evidence review
│   │   └── settings/page.tsx
│   ├── layout.tsx                     # Root layout and providers
│   ├── page.tsx                       # Landing or redirect
│   └── globals.css                    # Tailwind directives
├── components/
│   ├── ui/
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   ├── select.tsx
│   │   ├── dialog.tsx
│   │   ├── toast.tsx
│   │   ├── spinner.tsx
│   │   └── badge.tsx
│   ├── forms/
│   │   ├── upload-form.tsx            # PDF/DOCX + PMID/DOI/keyword input
│   │   ├── keyword-search-form.tsx    # Candidate search/selection
│   │   └── review-feedback-form.tsx   # Structured expert feedback
│   ├── charts/
│   │   ├── evidence-timeline.tsx
│   │   └── confidence-gauge.tsx
│   ├── document-panel.tsx             # Original parsed document and highlights
│   ├── translated-document-panel.tsx  # Translated document and highlights
│   ├── evidence-panel.tsx             # Evidence matrix and fusion review
│   ├── processing-status.tsx          # WebSocket progress
│   └── layout/
│       ├── sidebar.tsx
│       ├── topbar.tsx
│       └── dashboard-shell.tsx
├── lib/
│   ├── api/
│   │   ├── client.ts
│   │   ├── auth.ts
│   │   ├── tasks.ts
│   │   ├── literature.ts
│   │   ├── evidence.ts
│   │   └── ws.ts
│   ├── hooks/
│   │   ├── use-task.ts
│   │   ├── use-task-result.ts
│   │   ├── use-websocket.ts
│   │   └── use-auth.ts
│   ├── types/
│   │   ├── task.ts
│   │   ├── evidence.ts
│   │   ├── variant.ts
│   │   └── api.ts
│   └── utils/
│       ├── format.ts
│       └── validation.ts
├── stores/
│   ├── auth-store.ts
│   ├── task-store.ts
│   └── ui-store.ts
├── styles/
├── public/
├── tests/
├── next.config.ts
├── package.json
└── tsconfig.json
```

### 3.1 Component Architecture Preference

Frontend modules should mirror **Orchestrated Vertical Slice Architecture** at UI scale:

```text
app/(route)/page.tsx          # Page-level orchestration and data composition only
components/<feature>/         # Vertical UI feature slices
components/ui/                # Shared primitives
lib/api/                      # Backend API providers
lib/hooks/                    # Feature/provider hooks
lib/types/                    # Cross-feature contracts
stores/                       # Global UI/runtime state only
```

When a screen grows beyond simple composition, split it by feature responsibility rather than by technical widget type alone. For example, bilingual evidence review should keep document rendering, translated rendering, evidence matrix behavior, and feedback submission as cohesive slices with explicit typed props/contracts. Page files should wire slices together and pass state; they should not contain evidence-specific business rules, source-anchor resolution, or feedback normalization logic.

Component slice rules:

- `api`/hook layer fetches or mutates backend data.
- `core`/utility functions handle pure UI-domain transformations such as grouping evidence rows or resolving highlight targets.
- Component views render state and emit typed events.
- Shared UI primitives stay generic and must not depend on ACMG evidence concepts.

## 4. Primary Screens

### 4.1 Analysis Page

The MVP analysis page is structured-form first. Chat assistant behavior is P1/future.

```text
┌────────────────────────────────────────────────────────────┐
│ New Dual Evidence Extraction Task                           │
├──────────────────────────────┬─────────────────────────────┤
│ Input                         │ Processing Status           │
│                              │                             │
│ [Upload PDF/DOCX]            │ Ready / Running             │
│ ── or ──                     │                             │
│ [PMID input]                 │ acquisition                 │
│ [DOI input]                  │ parsing                     │
│ [Keyword search]             │ native_extraction           │
│                              │ translation                 │
│ [Start Extraction]           │ translated_extraction       │
│                              │ fusion                      │
│                              │ standardization             │
│                              │ report_preparation          │
└──────────────────────────────┴─────────────────────────────┘
```

### 4.2 Result Review Page

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ Topbar: Task #123 | Evidence Matrix Ready | Fusion Warnings | Export       │
├─────────────────────────┬─────────────────────────┬─────────────────────────┤
│ Original Document       │ Translated Document     │ Evidence Panel          │
│                         │                         │                         │
│ Original Markdown/HTML  │ English/Chinese HTML    │ Standardized matrix     │
│ Table/figure regions    │ Translated snippets     │ Evidence by category    │
│ Highlighted source span │ Highlighted translation │ Fusion status/conflicts │
│                         │                         │ Structured feedback     │
└─────────────────────────┴─────────────────────────┴─────────────────────────┘
```

## 5. Key Components

### 5.1 Upload Form (`forms/upload-form.tsx`)

- Drag-and-drop local PDF/DOCX upload.
- Tab switch: PDF/DOCX / PMID / DOI / Keyword.
- Client-side file validation for type and configured size limit.
- `POST /api/v1/tasks` with multipart for file upload.
- `POST /api/v1/tasks` with JSON for PMID/DOI/selected keyword candidate.
- Clear warning that uploaded clinical documents may contain sensitive data and must follow the user's institutional policy.

### 5.2 Keyword Search Form (`forms/keyword-search-form.tsx`)

Keyword analysis is search-first:

1. User enters keyword query.
2. Frontend calls `/api/v1/literature/search`.
3. User selects an analyzable candidate.
4. Candidate must include a downloadable PDF/document URL.
5. Frontend creates the task with `source_type="keyword"` and `selected_candidate`.

Minimum `selected_candidate` fields:

- `provider`
- `title`
- `canonical_id` when available (`doi`, `pmid`, or `url`)
- `selected_download_url`

### 5.3 Processing Status (`processing-status.tsx`)

Connect to `WS /api/v1/tasks/{task_id}/ws` and render concrete stages:

```text
[✓] Acquisition Complete
[✓] Parsing Complete
[✓] Native Extraction Complete
[✓] Translation Complete
[⟳] Translated Extraction — 45%
[ ] Fusion and Cross-Validation
[ ] Entity Standardization
[ ] Report Preparation
```

When WebSocket emits `complete`, fetch `GET /api/v1/tasks/{task_id}/result`.

If backend restart loses an in-memory running task, show a clear interrupted-task message and offer recreation when possible.

### 5.4 Original Document Panel (`document-panel.tsx`)

Responsibilities:

- Render MinerU/PaddleOCR Markdown/HTML output.
- Render DOCX-derived text and tables in the same source-span model.
- Render extracted tables as table views when structured JSON/CSV is available.
- Show figure/pedigree/plot regions with VLM-generated descriptions.
- Highlight original source spans by `source_anchor`, bbox, table cell, or figure region.
- Clicking highlighted source text scrolls to the linked evidence item.

Current stage does not require an embedded native PDF viewer; rendered MD/HTML is the primary original document surface.

### 5.5 Translated Document Panel (`translated-document-panel.tsx`)

Responsibilities:

- Render English/Chinese translated Markdown/HTML.
- Preserve translated anchors mapped back to original anchors.
- Highlight translated spans corresponding to selected evidence items.
- Show translation warnings when biomedical literals changed or content was dropped.
- Provide side-by-side review with the original document panel.

### 5.6 Evidence Panel (`evidence-panel.tsx`)

Sections:

1. **Document Metadata**: DOI, PMID, authors, year, journal, language.
2. **Evidence Matrix Summary**: total evidence items, categories, low-confidence count, fusion-conflict count.
3. **Variant/Gene Mentions**: original values, translated values, standardized IDs.
4. **Disease/Phenotype Mentions**: original terms, translated terms, HPO/OMIM/MONDO matches.
5. **Functional/Experimental Data**: assays, controls, thresholds, quantitative/qualitative results.
6. **Genetic Data**: segregation, de novo, case-control evidence when present.
7. **Population and Computational Data**: reported frequencies and prediction data.
8. **Entity Standardization**: match method, source DB, match score/rationale.
9. **Bilingual Source Links**: original snippets, translated snippets, page/line/bbox/table/figure references.
10. **Fusion Status**: agreed, native-only, translated-only, conflict, manually corrected.
11. **Conflicts and Confidence**: low-confidence fields, disagreements, ambiguous matches.
12. **Structured Feedback**: targeted expert feedback.
13. **Actions**: Add feedback/comment, export PDF/DOCX evidence summary.

### 5.7 Structured Feedback Form (`forms/review-feedback-form.tsx`)

Feedback target types:

- `native_extraction`
- `translated_extraction`
- `translation`
- `fusion`
- `entity`
- `evidence_item`
- `missed_evidence`
- `report`
- `task`

Fields:

- Target type.
- Target ID when applicable.
- Problem category.
- Reviewer rationale.
- Suggested correction text.
- Optional original source anchor.
- Optional translated source anchor.

Submitting feedback requires login. In the current stage, feedback persists for audit/export/dataset preparation and does not directly mutate evidence rows.

### 5.8 WebSocket Hook (`lib/hooks/use-websocket.ts`)

Required behavior:

```typescript
// - Connects to /api/v1/tasks/{taskId}/ws
// - Auto-connects after task creation
// - Reconnects on transient disconnects while the task is running
// - Parses status, complete, and error messages
// - Cleans up on unmount
// - Surfaces interrupted in-memory task state clearly
```

## 6. State Management

### 6.1 Auth Store

```typescript
interface AuthState {
  token: string | null;
  user: { id: string; email: string; emailVerified: boolean } | null;
  login: (token: string, user: User) => void;
  logout: () => void;
  isAuthenticated: () => boolean;
}
```

JWT TTL is 24 hours. Password reset and refresh-token flows are future work.

### 6.2 Task Store

```typescript
interface TaskState {
  activeTaskId: string | null;
  processingSteps: ProcessingStep[];
  setActiveTask: (id: string) => void;
  updateStep: (step: ProcessingStep) => void;
  reset: () => void;
}
```

The task store mirrors UI runtime state only. Completed task data is fetched from backend result endpoints.

### 6.3 API Client

```typescript
// Interceptors:
// - Request: attach JWT token from auth store when available
// - Response: handle 401 by routing to login when action requires login
// - Error: normalize backend error format
```

Task/result reads are public in the current MVP. Comment/feedback creation and deployed task creation require login.

## 7. API Integration

### 7.1 Auth API

```text
POST /api/v1/auth/register       → Register with email/password
POST /api/v1/auth/verify-email   → Verify email
POST /api/v1/auth/login          → Login, return 24h JWT
GET  /api/v1/auth/me             → Current user, if authenticated
```

### 7.2 Literature and Task API

```text
GET      /api/v1/literature/search          → Keyword/provider search
POST     /api/v1/tasks                      → Create dual extraction task
GET      /api/v1/tasks                      → List active/recent and completed tasks
GET      /api/v1/tasks/{task_id}            → Get task metadata/status
WS       /api/v1/tasks/{task_id}/ws         → Real-time processing status
GET      /api/v1/tasks/{task_id}/result     → Get bilingual evidence matrix result
POST     /api/v1/tasks/{task_id}/comments   → Add review comment/feedback, login required
POST     /api/v1/tasks/{task_id}/export     → Generate PDF/DOCX evidence report
GET      /api/v1/health                     → Health check
```

### 7.3 Future/P1 API

```text
GET /api/v1/evidence            → Query evidence matrices/chains
GET /api/v1/graph/query         → Query knowledge graph if enabled
GET /api/v1/graph/stats         → Graph statistics if enabled
```

## 8. Styling Guidelines

### 8.1 Visual Tone

- Use a medical/scientific palette: calm neutrals, clear warning states, accessible contrast.
- Reserve red for blocking parse/extraction errors.
- Reserve amber for low confidence, ambiguous standardization, or fusion conflicts.
- Reserve green for completed processing and valid bilingual source linkage.

### 8.2 Component Patterns

- Use `clsx` for conditional classes.
- Avoid inline styles.
- Extract repeated patterns into component variants or Tailwind utilities.
- Use accessible primitives for dialogs, dropdowns, and tooltips.
- Keep evidence cards dense but scannable; avoid hiding traceability, fusion status, or uncertainty behind hover-only UI.

### 8.3 Typography

- Monospace for HGVS, gene symbols, transcript IDs, rsIDs, and coordinates.
- Serif or document-optimized readable style for source document content.
- Sans-serif for UI chrome.

## 9. Testing Strategy

Current-stage frontend verification:

- `npm run lint`
- `npm run type-check`
- Manual golden-path UI check when UI behavior is implemented

Future hardening:

- Component tests with React Testing Library.
- E2E tests for upload → bilingual review → export.
- Mock WebSocket tests for dual extraction status.
- MSW for API mocking.
