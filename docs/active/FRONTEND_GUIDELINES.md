# FRONTEND_GUIDELINES — ACMG Lingua Frontend

## 1. Tech Stack

| Concern | Choice | Notes |
|---------|--------|-------|
| Framework | Next.js 15 App Router | File-based routing, layouts, SSR |
| UI Library | React 18 | Concurrent features |
| Language | TypeScript 5.5+ | Strict mode |
| Styling | Tailwind CSS 3.4 | Utility-first, no CSS-in-JS |
| State (client) | Zustand 4.5 | Minimal boilerplate, no providers |
| State (server) | React Query 5.50 | Caching, background refetch |
| HTTP | Axios 1.7 | Calls `/api/v1/*` through Next.js proxy |
| WebSocket | Native WebSocket API | Per-task processing status |
| Utilities | clsx 2.1 | Conditional classnames |
| Linting | ESLint 8.57 + next config | Google TypeScript Style |
| Type Check | TypeScript compiler | Current-stage frontend verification |

FastAPI is authoritative for authentication and API behavior. Next.js proxies requests and renders UI; it does not sign or verify JWTs.

## 2. Directory Structure

```
frontend/
├── app/
│   ├── api/                           # Proxy routes only when needed
│   ├── (dashboard)/                   # Dashboard layout group
│   │   ├── layout.tsx                 # Sidebar + topbar layout
│   │   ├── analysis/                  # New analysis task page
│   │   │   └── page.tsx               # Upload/input form + status-oriented UX
│   │   ├── results/                   # Results review page
│   │   │   └── [taskId]/              # Per-task result view
│   │   │       └── page.tsx           # Document + evidence side-by-side
│   │   └── settings/                  # User settings page
│   │       └── page.tsx
│   ├── auth/
│   │   ├── login/page.tsx             # Login page
│   │   ├── register/page.tsx          # Public registration page
│   │   └── verify-email/page.tsx      # Email verification page
│   ├── layout.tsx                     # Root layout (providers, fonts)
│   ├── page.tsx                       # Landing / redirect to dashboard
│   └── globals.css                    # Tailwind directives
├── components/
│   ├── ui/                            # Base components
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   ├── select.tsx
│   │   ├── dialog.tsx
│   │   ├── toast.tsx
│   │   ├── spinner.tsx
│   │   └── badge.tsx
│   ├── charts/                        # Visualizations
│   │   ├── evidence-timeline.tsx
│   │   └── confidence-gauge.tsx
│   ├── forms/                         # Input and review forms
│   │   ├── upload-form.tsx            # PDF upload + PMID/DOI/keyword input
│   │   ├── keyword-search-form.tsx    # Search and candidate selection
│   │   └── review-comment-form.tsx    # Human review comments only
│   ├── document-panel.tsx             # MinerU-rendered document view
│   ├── evidence-panel.tsx             # Evidence and classification draft view
│   ├── processing-status.tsx          # WebSocket-driven progress view
│   └── layout/                        # Page layout components
│       ├── sidebar.tsx
│       ├── topbar.tsx
│       └── dashboard-shell.tsx
├── lib/
│   ├── api/
│   │   ├── client.ts                  # Axios instance with interceptors
│   │   ├── auth.ts                    # /api/v1/auth/* calls
│   │   ├── tasks.ts                   # /api/v1/tasks calls
│   │   ├── literature.ts              # /api/v1/literature/search
│   │   ├── evidence.ts                # Evidence query API (P1)
│   │   └── ws.ts                      # WebSocket client
│   ├── hooks/
│   │   ├── use-task.ts                # Task React Query hooks
│   │   ├── use-task-result.ts         # Result fetching hook
│   │   ├── use-websocket.ts           # Per-task WebSocket hook
│   │   └── use-auth.ts                # Auth state hook
│   ├── types/
│   │   ├── task.ts                    # Task types
│   │   ├── evidence.ts                # Evidence types (mirrors backend schema)
│   │   ├── variant.ts                 # Variant types
│   │   └── api.ts                     # API response types
│   └── utils/
│       ├── format.ts                  # Date, number formatting
│       └── validation.ts              # Input validation helpers
├── stores/
│   ├── auth-store.ts                  # JWT token, user info, email verification state
│   ├── task-store.ts                  # Active in-memory task UI state
│   └── ui-store.ts                    # UI state (sidebar, modals)
├── styles/
│   └── globals.css
├── public/
├── tests/                             # Future frontend tests
├── next.config.ts
├── package.json
└── tsconfig.json
```

## 3. Design Principles

### 3.1 Medical Professional UX

- **Zero learning curve**: users are not expected to have coding experience.
- **Status clarity**: long-running analysis must show concrete processing stages to reduce waiting anxiety.
- **Traceability first**: every evidence item links back to source text in the rendered document.
- **Draft framing**: ACMG/GDV outputs are expert-review drafts, not final clinical conclusions.
- **Confidence visibility**: confidence scores are shown alongside extracted fields and evidence items.
- **Safe review semantics**: users add comments/rationale; they do not edit structured classification outputs in the current stage.

### 3.2 Layout: Split-Panel Evidence Review

```
┌─────────────────────────────────────────────────────────────┐
│  Topbar: [ACMG Lingua]  [Task #123]  [User ▼]              │
├──────────┬──────────────────────────────────────────────────┤
│          │                                                  │
│  Sidebar │  Main Content Area                               │
│          │                                                  │
│  • New   │  ┌─────────────────────┬───────────────────────┐ │
│    Task  │  │  Document Panel     │  Evidence Panel       │ │
│          │  │                     │                       │ │
│  • Tasks │  │  Rendered MD/HTML   │  Variant summary      │ │
│    List  │  │  from MinerU        │  Evidence chain       │ │
│          │  │                     │  Draft classification │ │
│  •       │  │  [Highlighted text  │  Confidence scores    │ │
│  Results │  │   linked by source  │                       │ │
│          │  │   anchors/bbox]     │  [Comment] [Export]   │ │
│  •       │  └─────────────────────┴───────────────────────┘ │
│  Settings│                                                  │
└──────────┴──────────────────────────────────────────────────┘
```

### 3.3 Analysis Page Interaction

The MVP analysis page is structured-form first. Chat assistant behavior is P1/future; current status-oriented UX should focus on clear steps and progress.

```
┌──────────────────────────────────────────────────┐
│  Analysis Page                                    │
│                                                   │
│  ┌─────────────────────┐  ┌────────────────────┐ │
│  │  Structured Form    │  │  Processing Status │ │
│  │                     │  │                    │ │
│  │  [Upload PDF]       │  │  Ready             │ │
│  │  ── or ──           │  │                    │ │
│  │  [PMID/DOI input]   │  │  After submit:     │ │
│  │  ── or ──           │  │  acquisition → OCR │ │
│  │  [Keyword search]   │  │  → translation →   │ │
│  │                     │  │  extraction → ...  │ │
│  │  [Start Analysis]   │  │                    │ │
│  └─────────────────────┘  └────────────────────┘ │
└──────────────────────────────────────────────────┘
```

## 4. Key Components

### 4.1 Upload Form (`forms/upload-form.tsx`)

- Drag-and-drop PDF upload zone, max 50MB.
- Tab switch: PDF / PMID / DOI / Keyword.
- File validation for type and size before upload.
- Progress bar during upload.
- `POST /api/v1/tasks` with multipart for PDF upload.
- `POST /api/v1/tasks` with JSON for PMID/DOI and selected keyword candidate.

### 4.2 Keyword Search Form (`forms/keyword-search-form.tsx`)

Keyword analysis is search-first:

1. User enters keyword query.
2. Frontend calls `/api/v1/literature/search`.
3. User selects an analyzable candidate.
4. Candidate must include at least one PDF download URL.
5. Frontend creates the task with `source_type="keyword"` and `selected_candidate`.

Minimum `selected_candidate` fields:

- `provider`
- `title`
- `canonical_id` when available (`doi`, `pmid`, or `url`)
- `selected_download_url`

### 4.3 Processing Status (`processing-status.tsx`)

Real-time WebSocket-driven step indicators connect to `WS /api/v1/tasks/{task_id}/ws`.

```
[✓] Acquisition Complete   — 1.1s
[✓] OCR Complete           — 2.3s
[✓] Translation Complete   — 15.2s
[⟳] Extracting Evidence    — 45% (est. 30s)
[ ] Standardization
[ ] ACMG Reasoning
[ ] GDV Reasoning
[ ] Arbitration
```

Each step shows status icon, elapsed time, and progress percentage when available. When the WebSocket emits `complete`, the UI fetches `GET /api/v1/tasks/{task_id}/result`.

### 4.4 Document Panel (`document-panel.tsx`)

- Renders MinerU output as styled HTML/MD.
- Does not embed a PDF viewer in the current stage.
- Highlights evidence source text through source anchors and bbox-backed spans.
- Clicking highlighted text scrolls to the linked evidence item in the Evidence Panel.
- Displays images and VLM descriptions when available.

### 4.5 Evidence Panel (`evidence-panel.tsx`)

Sections:

1. **Variant Summary**: Gene, HGVS, Disease, MONDO.
2. **GDV Draft**: GDV tier, rationale, confidence, and block status.
3. **ACMG Draft**: ACMG tier and rationale only when GDV does not block display.
4. **Evidence Chain**: Expandable list of triggered rules and source links.
5. **Functional Data**: Experiment details, controls, thresholds.
6. **Population Data**: gnomAD frequencies.
7. **Predictions**: CADD, REVEL, SpliceAI scores.
8. **Review Comments**: persisted human comments/rationale.
9. **Actions**: Add Comment / Export Draft PDF.

GDV display rules:

- `No Known Disease Validity`, `Disputed`, and `Refuted` block ACMG tier display.
- `Limited` shows ACMG with a warning.
- `Definitive`, `Strong`, and `Moderate` allow ACMG display.

### 4.6 Review Comment Form (`forms/review-comment-form.tsx`)

- Text area for review comment/rationale.
- Optional target: whole task, specific variant, or specific evidence item.
- Submit requires login.
- Submission saves a review comment; it does not change structured classification, evidence strength, or tier.
- Comments persist and appear in exported draft reports.

### 4.7 WebSocket Hook (`lib/hooks/use-websocket.ts`)

```typescript
// Features:
// - Connects to /api/v1/tasks/{taskId}/ws
// - Auto-connects after task creation
// - Reconnects on transient disconnects while task is running
// - Parses status, complete, and error messages
// - Cleans up on unmount
```

Running tasks are in-memory. If the backend restarts and the task disappears, the UI should show a clear message that the running task was interrupted and can be recreated.

### 4.8 Graph Query (`components/graph-query.tsx`) — P1/Future

- Input: HGVS string or gene-disease pair.
- Display: Neo4j results as interactive node-link diagram or table.
- Statistics: evidence count, classification history.

Graph query is not required for the current MVP.

## 5. State Management

### 5.1 Auth Store (Zustand)

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

### 5.2 Task Store (Zustand)

```typescript
interface TaskState {
  activeTaskId: string | null;
  processingSteps: ProcessingStep[];
  setActiveTask: (id: string) => void;
  updateStep: (step: ProcessingStep) => void;
  reset: () => void;
}
```

The task store mirrors UI runtime state only. Completed task data should be fetched from backend result endpoints.

### 5.3 API Client (Axios)

```typescript
// Interceptors:
// - Request: attach JWT token from auth store when available
// - Response: handle 401 by sending user to login when the current action requires login
// - Error: normalize error format
```

Task/result reads are public. Comment creation and deployed task creation require login.

## 6. API Integration

### 6.1 Auth API

All auth endpoints are FastAPI endpoints proxied under `/api/v1/*`.

```
POST /api/v1/auth/register       → Register with email/password
POST /api/v1/auth/verify-email   → Verify email
POST /api/v1/auth/login          → Login, return 24h JWT
GET  /api/v1/auth/me             → Current user, if authenticated
```

### 6.2 Literature and Task API

```
GET/POST /api/v1/literature/search          → Keyword/provider search
POST     /api/v1/tasks                      → Create analysis task
GET      /api/v1/tasks                      → List active/recent tasks and persisted completed results
GET      /api/v1/tasks/{task_id}            → Get task metadata/status
WS       /api/v1/tasks/{task_id}/ws         → Real-time processing status
GET      /api/v1/tasks/{task_id}/result     → Get final analysis result
POST     /api/v1/tasks/{task_id}/comments   → Add review comment (login required)
POST     /api/v1/tasks/{task_id}/export     → Generate draft PDF report
GET      /api/v1/health                     → Health check
```

Use `POST /api/v1/tasks` as the authoritative creation endpoint.

### 6.3 Future/P1 API

```
GET /api/v1/evidence            → Query evidence chains
GET /api/v1/graph/query         → Query Neo4j knowledge graph
GET /api/v1/graph/stats         → Graph statistics
```

## 7. Styling Guidelines

### 7.1 Tailwind Configuration

- Use project color palette with medical/scientific tone.
- Responsive breakpoints are mobile-first.
- Dark mode support is future work.

### 7.2 Component Patterns

- Use `clsx` for conditional classes.
- Avoid inline styles.
- Extract repeated patterns into component variants or Tailwind utilities.
- Use accessible primitives for dialogs, dropdowns, and tooltips.

### 7.3 Typography

- Monospace for HGVS strings, gene symbols, and coordinates.
- Serif for document content readability.
- Sans-serif for UI chrome.

## 8. Testing Strategy

Current-stage frontend verification:

- `npm run lint`
- `npm run type-check`
- Manual golden-path UI check when UI behavior is implemented

Future hardening:

- Component tests with React Testing Library.
- E2E tests for upload → review → export.
- Mock WebSocket tests for processing status.
- MSW for API mocking.
