# APP_FLOW — CrossEvidence Application Flow

## 1. Navigation & Architecture Overview

CrossEvidence uses a sidebar-based dashboard layout. Unauthenticated users are
redirected to the login page. The root route (`/`) redirects to `/chat`.

```
┌──────────────┬───────────────────────────────────────────────┐
│  CrossEvidence │  ┌──────────────────────────────────────────┐ │
│              │  │  header: sidebar toggle · connection status│ │
│  [AI Chat]   │  ├──────────────────────────────────────────┤ │
│  [Evidence]  │  │                                          │ │
│              │  │           main content area               │ │
│              │  │                                          │ │
│  v0.1.0      │  └──────────────────────────────────────────┘ │
└──────────────┴───────────────────────────────────────────────┘
```

### Routes

| Route | Component | Purpose |
|---|---|---|
| `/login` | `LoginForm` | Email + password login (JWT) |
| `/register` | `RegisterForm` | Email + password registration |
| `/chat` | `ChatView` | Chat sessions list with conversation sidebar |
| `/chat/[sessionId]` | `ChatView(sessionId)` | Single session chat with message history |
| `/pipeline` | `PipelineSubmitForm` | Submit PDF or online search query to start a pipeline |
| `/pipeline/[runId]` | `PipelineStatusView` | 3-phase timeline + per-phase detail cards |
| `/evidence` | `EvidenceSearchView` | Search evidence by gene, variant, disease, PMID, DOI |
| `/evidence/detail` | `EvidenceDetailView` | Literature overview or bilingual full-text comparison |

### Sidebar Navigation

Two items are registered in the sidebar (`NAV_ITEMS`):

| Label | Icon | Route |
|---|---|---|
| AI Chat | `MessageSquare` | `/chat` |
| Evidence | `Search` | `/evidence` |

Pipeline pages are reached from within the Chat feature (pipeline start form) or
directly via URL. The sidebar collapses/expands via the header toggle button.

## 2. Architecture: Orchestrated Vertical Slices at Runtime

```
Entry (sidebar nav or direct URL)
  │
  ▼
Page-level orchestration (app/**/page.tsx)
  │  Data composition, routing, state wiring only
  │
  ├──► Feature slice: Auth (login, register, JWT session)
  ├──► Feature slice: Chat (sessions, messages, SSE streaming, pipeline forms)
  ├──► Feature slice: Pipeline (submit form, 3-phase status view, timeline)
  └──► Feature slice: Evidence Search (search form, results table, detail/compare)
          │
          ▼
Shared infrastructure: API client, hooks, types, stores, UI primitives
```

### Feature slice source layout

```
frontend/src/features/
├── auth/            components/ (LoginForm, RegisterForm)
│                    hooks/ (useAuth)
│                    services/ (auth — stubbed, pending backend /auth endpoints)
│                    types/ (LoginRequest, LoginResponse, RegisterRequest, AuthUser)
├── chat/            components/ (ChatView)
│                    components/forms/ (PipelineStartForm, PipelineStatusCard)
│                    hooks/ (useChatSessions, useChatMessages)
│                    providers/ (chatProvider — SSE-based custom provider)
│                    services/ (chat — session CRUD, message append, stream URL)
│                    types/ (ChatSessionResponse, ChatMessageResponse, ChatSSEEvent)
├── pipeline/        components/ (PipelineSubmitForm, PipelineStatusView,
│                                 PhaseTimeline, PhaseDetailCard)
│                    hooks/ (usePipelineRun, usePipelineStatus, usePhaseTimeline)
│                    services/ (pipeline — start run, poll status)
│                    types/ (PipelineRunRequest, PipelineRunResponse,
│                             PipelineStatusResponse, PhaseTimelineStep)
└── evidence-search/ components/ (EvidenceSearchView, EvidenceSearchForm,
│                                  EvidenceResultsTable, EvidenceDetailView,
│                                  EvidenceHighlightText)
                     hooks/ (useEvidenceSearch, useEvidenceGroupDetail)
                     services/ (evidenceSearch — search, group detail)
                     types/ (EvidenceSearchQuery, EvidenceSearchResponse,
                              EvidenceGroupDetailResponse, EvidenceTrackTrace, ...)
                     utils/ (evidenceDocument — paragraph/highlight builder,
                              literatureRows — bilingual compare href builder)
```

At runtime, the frontend calls FastAPI `/api/v1/*` endpoints via `apiClient`
(Axios instance). Next.js proxies `/api/v1/*` to `localhost:8000` (configured
in `next.config.ts`). FastAPI owns business logic, orchestration, and
persistence. Next.js renders the UI.

## 3. Chat Flow

The Chat feature is the primary user interaction surface, built on
`@ant-design/x` components (`XProvider`, `Bubble`, `Sender`, `Conversations`,
`Welcome`, `Prompts`).

### 3.1 Full Chat View (`/chat`)

```
User opens /chat
  │
  ▼
FullChatView renders:
  ├── Left: Conversations sidebar (240px)
  │     ├── Session list from GET /api/v1/chat/sessions/{processingRunId}
  │     ├── "New session" button → POST /api/v1/chat/sessions
  │     └── Click session → switch active conversation
  │
  └── Right: Chat area
        ├── Empty state:
        │     Welcome component ("CrossEvidence Agent" + description)
        │     + Prompt suggestions (3 clickable items):
        │       - "Start Pipeline" → shows inline PipelineStartForm
        │       - "Upload PDF" → shows inline PipelineStartForm (file mode)
        │       - "Search Evidence" → navigates to /evidence
        │
        └── Active chat:
              Bubble.List with user + assistant messages
              + Sender input at bottom
              + Inline PipelineStatusCard when pipeline is running
```

### 3.2 Message Flow

```
User types message and hits Send
  │
  ├── 1. POST /api/v1/chat/sessions/{sessionId}/messages
  │     (persists user message to backend)
  │
  ├── 2. Open SSE stream: GET /api/v1/chat/sessions/{sessionId}/stream
  │       ?user_message=...
  │
  └── 3. SSE events parsed by CrossEvidenceChatProvider:
        data: {"type": "text", "content": "..."}  → accumulate tokens
        data: {"type": "done"}                     → stream complete
        data: {"type": "error", "message": "..."}  → display error
```

The `CrossEvidenceChatProvider` extends `AbstractChatProvider` from `@ant-design/x-sdk`.
It customizes the fetch function to append `user_message` as a query parameter
to the SSE endpoint. The backend agent auto-classifies intent (question,
correction, note) and streams replies accordingly.

### 3.3 Inline Pipeline Start Form

When the user clicks "Start Pipeline" or "Upload PDF" from the prompt
suggestions, a `PipelineStartForm` is rendered as a special `contentRender`
bubble inside the chat. The form supports:

- **Online mode**: search query input (PMID, DOI, or free-text query)
- **Local mode**: PDF file upload via drag-and-drop-style file picker

On submit:
```
PipelineStartForm submit
  │
  ├── POST /api/v1/pipeline/run  (starts the pipeline)
  │
  ├── Assistant message injected: "Pipeline started. Run ID: xxxxxxxx..."
  │
  └── PipelineStatusCard rendered as an inline bubble
        Shows: run ID, overall status badge, 3-phase progress indicators
        Polls GET /api/v1/pipeline/runs/{id}/status every 2 seconds
        until terminal status (completed / failed / awaiting_review / cancelled)
```

### 3.4 Single Session Chat (`/chat/[sessionId]`)

Renders a simpler `ChatView` for a single session — no conversation sidebar,
no prompt suggestions. Just `Bubble.List` + `Sender`. Messages are streamed
via the same `CrossEvidenceChatProvider` mechanism.

### 3.5 Standalone Chat Sessions

`/chat` supports standalone chat sessions that are not bound to a pipeline run.
When opened without a `processingRunId`, the chat feature:

- Creates sessions with `POST /api/v1/chat/sessions` (empty body).
- Stores visible session metadata in browser `localStorage` (key: `cross-evidence.chat.sessions.v1`).
- Remembers the active session ID in `localStorage` (key: `cross-evidence.chat.activeSessionId.v1`).
- Reloading `/chat` restores the standalone session cards and active session from `localStorage`.
- Clicking the "Upload PDF" prompt opens the pipeline form with local upload selected by default.
- Uploading a PDF starts `POST /api/v1/pipeline/run`, shows an inline status card, and does not navigate away.
- All message history and assistant responses are persisted in the backend database.

### 3.6 Session Persistence

```
Chat session data model:
  ├── session_id (UUID)
  ├── processing_run_id (UUID | null — nullable for standalone sessions)
  ├── created_at
  └── message_count

Chat message data model:
  ├── message_id (UUID)
  ├── role: "user" | "assistant" | "system"
  ├── content: string
  ├── evidence_id (optional — links to specific evidence)
  ├── entity_id (optional)
  └── created_at
```

## 4. Pipeline Flow

### 4.1 Submit Pipeline (`/pipeline`)

```
User opens /pipeline
  │
  ▼
PipelineSubmitForm renders:
  ├── Source Type selector: "Online Search" | "Local File Upload"
  ├── Online: Search Query input (e.g., "BRCA1 pathogenic variant breast cancer")
  ├── Local: File picker accepting .pdf / .docx
  └── "Start Pipeline" button
  │
  ▼
POST /api/v1/pipeline/run
  Body: { source_type, mode: "full", query?, content_base64?, filename? }
  Response: { processing_run_id, source_document_id, status, status_url }
  │
  ▼
Router navigates to /pipeline/{processing_run_id}
```

### 4.2 Pipeline Status View (`/pipeline/[runId]`)

```
PipelineStatusView renders:
  │
  ├── Header: "Pipeline Status" + Run ID + overall status Badge
  │     Status values: queued | running | completed | failed | cancelled
  │
  ├── PhaseTimeline: visual horizontal timeline of 3 phases
  │     ┌────┐         ┌────┐         ┌────┐
  │     │ 1  │─────────│ 2  │─────────│ 3  │
  │     │Phase 1│      │Phase 2│      │Phase 3│
  │     │ 45.2s │      │ 12.8s │      │  --   │
  │     └────┘         └────┘         └────┘
  │     Each node styled by status:
  │       queued → gray | running → blue pulse | completed → green | failed → red
  │     Connector lines: green when previous phase completed, gray otherwise
  │
  └── PhaseDetailCards: 3-column grid, one card per phase
        Each card shows: phase name, status badge, started_at, duration, summary, error
  │
  ▼
Status is polled via usePipelineStatus hook:
  GET /api/v1/pipeline/runs/{runId}/status
  Returns: { processing_run_id, source_document_id, pipeline_status,
             current_phase, phases: { phase_1, phase_2, phase_3 },
             error_message, error_phase, started_at, completed_at }
```

### 4.3 Three Pipeline Phases

| Phase | ID | Purpose |
|---|---|---|
| Phase 1 — Acquisition | `phase_1` | Literature acquisition + MinerU document parsing |
| Phase 2 — Extraction | `phase_2` | Cross-lingual dual-track extraction (native + translated); cross-track reconciliation planned |
| Phase 3 — Standardization | `phase_3` | Entity standardization + knowledge alignment |

Phase 3 may be skipped (`skip_phase_3_reason` field in status response).

## 5. Evidence Search Flow

### 5.1 Search (`/evidence`)

```
User opens /evidence
  │
  ▼
EvidenceSearchView renders:
  ├── EvidenceSearchForm (Card with filters):
  │     ├── Gene input (partial match)
  │     ├── Variant input (partial match on HGVS)
  │     ├── Disease input (partial match on diagnosis)
  │     ├── PMID input
  │     ├── DOI input
  │     └── "Search" / "Clear" buttons
  │
  ▼
GET /api/v1/evidence/search?gene=...&variant=...&disease=...&pmid=...&doi=...
      &page=...&page_size=...
  │
  ▼
EvidenceResultsTable:
  ├── Paginated table of EvidenceSearchResult rows
  │     Each row: title, PMID, DOI, gene, variant, disease, classification,
  │               field_count, avg_confidence, review_status
  ├── Click row → navigate to /evidence/detail?groupId={group_id}
  └── Pagination controls
```

### 5.2 Evidence Detail — Literature Overview (`/evidence/detail`)

```
URL: /evidence/detail?groupId={groupId}

GET /api/v1/evidence/groups/detail?group_id={groupId}
  │
  ▼
EvidenceDetailView (LiteratureOverview mode):
  ├── Back link to /evidence
  │
  ├── Literature metadata header:
  │     Title, source_document_id (UUID), PMID, DOI
  │     Gene / Variant / Disease / Classification metadata tokens
  │     "Traceable" badge
  │
  ├── Left sidebar:
  │     ├── Evidence coverage stats: items, confidence, traces, fields
  │     ├── Evidence categories (category → count chips)
  │     └── Review status badges (provisional / approved / corrected / rejected)
  │
  └── Right main area:
        ├── "Extracted evidence fields" header + "Full-text comparison" button
        └── EvidenceItemSummary cards (one per field-level evidence item):
              ├── Category pill (color-coded by evidence category)
              ├── Review status badge
              ├── Field name, field_id (mono)
              ├── "Compare full text" button → navigates to compare view
              ├── Value text (line-clamped)
              └── Stats: confidence %, track, page
```

### 5.3 Evidence Detail — Bilingual Comparison

```
URL: /evidence/detail?groupId={groupId}&evidenceId={id}&view=compare

EvidenceDetailView (BilingualComparison mode):
  ├── Back link to literature detail
  │
  ├── Header: literature title + metadata + selected evidence info
  │     + confidence, alignment confidence, source page stats
  │
  ├── Left sidebar (340px):
  │     ├── Evidence categories toggle panel
  │     │     Each category: checkbox toggle with item count
  │     │     Toggling filters which evidence spans are highlighted
  │     │
  │     └── Evidence navigator
  │           List of all evidence items (button list)
  │           Click → selects item, updates highlights in document reader
  │
  └── Right main area:
        ├── Active evidence detail card (selected item info)
        │
        └── Document readers (side-by-side when translated text available):
              ├── Original document reader
              │     Paragraphs with colored <mark> highlights per evidence span
              │     Highlight colors: gene (blue), variant (teal), disease (amber),
              │       classification (purple), functional (orange), neutral (gray)
              │     Selected evidence gets outline ring
              │
              └── English translation reader (same highlight system)
                    Only shown when translated_document_text or translated traces exist
```

The bilingual comparison view uses `buildEvidenceDocument()` to convert raw
trace data into highlight spans, and `CategoryLayerToggle` to filter which
evidence categories are visible in the document reader.

## 6. Knowledge Base Query — PLANNED

> **Status**: Not yet implemented. Future feature.

Planned capabilities:
- Variant-centric knowledge base search (HGVS, gene, disease)
- Evidence matrix view grouped by variant
- AI-assisted natural language query (Text-to-SQL)
- Evidence comparison across literature
- ACMG classification draft generation from accumulated evidence

## 7. Settings — PLANNED

> **Status**: Not yet implemented. Future feature.

Planned capabilities:
- Vocabulary manager (HPO, OMIM, ClinVar, gnomAD version management)
- Prompt template editor per evidence dimension
- System configuration panel (MinerU, database, model settings)

## 8. Authentication Flow

```
User visits any route
  │
  ▼
Auth state checked (useAuth hook, JWT in localStorage)
  │
  ├── Not authenticated → redirect to /login
  │     ├── LoginForm: email + password → POST /auth/login → JWT
  │     └── Link to /register
  │
  └── Authenticated → render DashboardLayout with Sidebar
```

> **Note**: Backend auth endpoints (`POST /auth/login`, `POST /auth/register`)
> are not yet wired. The frontend auth service (`features/auth/services/auth.ts`)
> currently returns stub responses for development.

## 9. Runtime Architecture Flow (Backend)

```
User Action (chat / pipeline / evidence)
  │
  ▼
Next.js proxy: /api/v1/* → localhost:8000
  │
  ▼
FastAPI /api/v1/* endpoint
  │
  ├── POST /api/v1/chat/sessions              → Create chat session
  ├── GET  /api/v1/chat/sessions/{runId}       → List sessions for run
  ├── GET  /api/v1/chat/sessions/{id}/messages → List messages
  ├── POST /api/v1/chat/sessions/{id}/messages → Append message
  ├── GET  /api/v1/chat/sessions/{id}/stream   → SSE: agent reply stream
  │
  ├── POST /api/v1/pipeline/run                → Start pipeline (returns 202)
  ├── GET  /api/v1/pipeline/runs/{id}/status   → Poll pipeline status
  │
  ├── GET  /api/v1/evidence/search             → Search evidence
  ├── GET  /api/v1/evidence/groups/detail       → Group detail + traces
  ├── PATCH /api/v1/evidence/{id}               → Patch evidence card
  │
  ├── GET  /api/v1/delta-audit/*               → Delta audit log
  └── GET  /api/v1/source-link/*               → Source document links
  │
  ▼
Orchestrator (src/agents/)
  │  LangGraph workflow topology, PipelineGraphState, routing
  │
  ├──► Phase 1: acquisition + MinerU document parsing
  ├──► Phase 2: cross-lingual extraction + translation (dual-track; reconciliation planned)
  └──► Phase 3: entity standardization + knowledge alignment
          │
          ▼
Phase 4 (independent of orchestrator):
  ├── Chat service (session/message CRUD, SSE agent stream)
  ├── Feedback service (evidence patch + audit)
  └── Search service (evidence search, group detail, literature profiles)
          │
          ▼
Shared infrastructure: config, DAO (PostgreSQL), Rust I/O (rust-io, files-io, net-io),
                       telemetry, rate limiting, Redis cache
```

## 10. Communication Architecture

```
Frontend                           Backend (FastAPI :8000)
────────                           ─────────────────────

Auth (stubbed)          ──REST──►  POST /auth/login, /auth/register
                                   ◄── { access_token, token_type }

Chat Sessions           ──REST──►  POST /api/v1/chat/sessions
                                   ◄── { chat_session_id, processing_run_id, ... }

Chat Messages           ──REST──►  POST /api/v1/chat/sessions/{id}/messages
                                   ◄── { message_id, role, content, created_at }

Chat Stream             ──SSE────  GET /api/v1/chat/sessions/{id}/stream
                                   ◄── data: {"type":"text","content":"..."}
                                   ◄── data: {"type":"done"}

Pipeline Run            ──REST──►  POST /api/v1/pipeline/run
                                   ◄── { processing_run_id, status_url, ... }

Pipeline Status         ──REST──►  GET /api/v1/pipeline/runs/{id}/status
                                   ◄── { pipeline_status, phases: {...}, ... }

Evidence Search         ──REST──►  GET /api/v1/evidence/search?gene=...&pmid=...
                                   ◄── { items: [...], total, page, page_size }

Evidence Group Detail   ──REST──►  GET /api/v1/evidence/groups/detail?group_id=...
                                   ◄── { group_id, items, traces, distribution, ... }

Evidence Patch          ──REST──►  PATCH /api/v1/evidence/{canonical_evidence_id}
                                   ◄── { canonical_evidence_id, old_status, new_status, deltas }

Delta Audit             ──REST──►  GET /api/v1/delta-audit/*
                                   ◄── audit log entries

Source Links            ──REST──►  GET /api/v1/source-link/*
                                   ◄── source document metadata
```

### Proxy Configuration

`next.config.ts` rewrites all `/api/v1/*` requests to the FastAPI backend at
`localhost:8000`. The frontend `apiClient` (Axios instance) uses
`/api/v1` as its base URL. The SSE stream for chat uses a custom `fetch`-based
implementation that bypasses Axios to support streaming.

---

*Document version v3.0 · 2026-06-09 · Updated to reflect actual implemented features; marked planned features*
