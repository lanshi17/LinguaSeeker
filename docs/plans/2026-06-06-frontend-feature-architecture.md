# Frontend Business Feature Architecture

**Date**: 2026-06-06
**Scope**: Restructure frontend to business feature modules with page/logic separation
**Status**: Planning

---

## Current State

Frontend is a **greenfield scaffold** — only `.gitkeep` files, zero actual code.
Stack: Next.js 15 App Router, React 18, TypeScript 5.5, Zustand 4.5, TanStack Query 5.5, Axios 1.7, Tailwind CSS 3.4, clsx.

---

## Target Architecture

### Core Principles

1. **Vertical Slice per Domain** — Each business feature is self-contained under `src/features/<name>/`
2. **Thin Page Shells** — `app/` pages only extract route params and compose feature components; zero business logic
3. **Page/Logic Separation** — Pages import from feature barrel exports; features own their components, hooks, services, types, stores
4. **`@/` → `./src/`** — All imports use the existing tsconfig path alias

### Target Directory Tree

```
frontend/
├── app/                              # Thin page shells only
│   ├── layout.tsx                    # Root layout: providers, global styles, Toast
│   ├── page.tsx                      # Redirect to /pipeline
│   ├── globals.css
│   ├── (auth)/                       # No sidebar layout
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   ├── (dashboard)/                  # Sidebar + main area layout
│   │   ├── layout.tsx
│   │   ├── pipeline/
│   │   │   ├── page.tsx              # Pipeline submission
│   │   │   └── [runId]/page.tsx      # Pipeline status
│   │   ├── tasks/
│   │   │   ├── agent-create/page.tsx
│   │   │   ├── new/page.tsx
│   │   │   └── literature/candidates/page.tsx
│   │   ├── requests/[requestId]/
│   │   │   ├── page.tsx
│   │   │   └── export/page.tsx
│   │   ├── documents/[documentId]/page.tsx
│   │   ├── evidence/
│   │   │   ├── [evidenceId]/page.tsx
│   │   │   └── audit/page.tsx
│   │   ├── chat/
│   │   │   ├── page.tsx
│   │   │   └── [sessionId]/page.tsx
│   │   ├── graph/page.tsx
│   │   └── settings/page.tsx
│   └── api/                          # Next.js BFF routes
│       ├── auth/login/route.ts
│       └── auth/register/route.ts
│
├── src/                              # All business code
│   ├── features/                     # 9 feature modules
│   │   ├── auth/                     # Login/register, useAuth hook
│   │   ├── pipeline/                 # Pipeline submit + status monitoring
│   │   ├── task-flow/                # Agent clarification + task form
│   │   ├── literature/               # Candidate search & selection
│   │   ├── evidence/                 # Evidence card patching
│   │   ├── delta-audit/              # Review audit trail
│   │   ├── source-link/              # Bilingual source traceability
│   │   ├── chat/                     # Chat sessions + SSE streaming
│   │   ├── document-viewer/          # Bilingual document reading
│   │   └── graph/                    # Knowledge graph explorer
│   │
│   ├── stores/                       # Global stores only (3)
│   │   ├── appStore.ts
│   │   ├── workflowStore.ts
│   │   └── toastStore.ts
│   │
│   ├── lib/                          # Shared infrastructure
│   │   ├── api/                      # client.ts, error.ts, sse.ts
│   │   ├── hooks/                    # usePolling, useDebounce
│   │   ├── types/                    # common.ts
│   │   └── utils/                    # cn.ts, format.ts, validation.ts
│   │
│   └── components/                   # Shared UI primitives
│       ├── ui/                       # Button, Card, Input, Badge, Modal, Spinner, Toast
│       └── layout/                   # AppShell, DashboardLayout, Sidebar, PageHeader
│
└── tests/                            # Mirrors src/ structure
```

### Feature Module Internal Structure

Each feature module follows the same convention:

```
features/<name>/
├── index.ts          # Barrel export (public API)
├── components/       # Presentational + container components
├── hooks/            # Data fetching (TanStack Query), state hooks
├── services/         # Axios API calls (one function per endpoint)
├── types/            # Request/Response types, domain models
└── stores/           # Feature-local Zustand store (optional, only if needed)
```

### Import Dependency Rules

```
page.tsx → @/features/<name> (barrel only)
  └── components/ → hooks/ → services/ → @/lib/api/client
  └── components/ → @/components/ui/*
  └── hooks/ → @/stores/* (global stores only)
```

**Forbidden**:
- Feature → another feature's internals (components/hooks/services/stores)
- Page.tsx → `@/lib/api/client` directly (must go through feature service)
- Feature → global store when local store suffices

---

## Feature Module Inventory

| Module | Backend API | Key Components | Key Hooks |
|--------|------------|----------------|-----------|
| **auth** | (Next.js BFF) | LoginForm, RegisterForm | useAuth |
| **pipeline** | POST `/pipeline/run`, GET `/pipeline/runs/{id}/status` | PipelineSubmitForm, PipelineStatusView, PhaseTimeline | usePipelineRun, usePipelineStatus |
| **task-flow** | (future: interaction endpoints) | TaskForm, ClarificationChat, FileUploadZone | useTaskFlow |
| **literature** | (future: candidates endpoints) | LiteratureCandidateList, CandidateCard | useCandidateSearch |
| **evidence** | PATCH `/evidence/{id}` | EvidenceCard, EvidencePatchForm | usePatchEvidence |
| **delta-audit** | GET `/delta-audit/` | AuditEventList, AuditEventRow | useAuditEvents |
| **source-link** | GET `/source-link/{id}/bilingual`, `/{id}/{track}` | BilingualSpanView, TrackSpanView | useBilingualSpan |
| **chat** | CRUD `/chat/sessions`, `/messages`, `/stream` (SSE) | ChatSessionList, ChatMessageList, ChatComposer | useChatStream, useChatMessages |
| **document-viewer** | (uses evidence + source-link) | DocumentViewer, BilingualReadingPane | useDocumentData |
| **graph** | (future: graph endpoints) | GraphSearchForm, GraphNodeList | useGraphSearch |

---

## Key Architectural Decisions

1. **Feature-local stores** — `taskFlowStore` lives in `features/task-flow/stores/`, not global. Only 3 global stores: app, workflow, toast.
2. **TanStack Query for all data fetching** — `useQuery` with `refetchInterval` for polling, `useMutation` for writes. No manual polling/AbortController.
3. **SSE replaces WebSocket** — Backend chat uses SSE. `lib/api/sse.ts` provides generic EventSource wrapper.
4. **No antd** — All UI via Tailwind primitives in `components/ui/`.
5. **`src/` for business code** — AGENTS.md rule 2. `app/` is framework routing, not business code.

---

## Implementation Phases

### Phase 1: Foundation (all features depend on this)

| # | File | Description |
|---|------|-------------|
| 1 | `tailwind.config.ts` | Tailwind config with custom theme |
| 2 | `postcss.config.js` | PostCSS config |
| 3 | `src/lib/api/client.ts` | Axios instance with interceptors |
| 4 | `src/lib/api/error.ts` | ApiError class, normalizeError() |
| 5 | `src/lib/utils/cn.ts` | clsx + tailwind-merge |
| 6 | `src/stores/toastStore.ts` | Toast notification queue |
| 7 | `src/stores/appStore.ts` | Minimal global UI state |
| 8 | `src/components/ui/*` | Button, Card, Input, Badge, Modal, Spinner, Toast |
| 9 | `src/components/layout/*` | AppShell, DashboardLayout, Sidebar, PageHeader |
| 10 | `app/layout.tsx` | Root layout with providers |
| 11 | `app/(dashboard)/layout.tsx` | Dashboard shell |
| 12 | `app/globals.css` | Tailwind directives + CSS vars |

**Verify**: `npm run dev` starts, dashboard layout renders with sidebar

### Phase 2: Core Features

| # | Feature | Files |
|---|---------|-------|
| 1 | `features/pipeline/` | types, services, hooks (usePipelineRun, usePipelineStatus), components (PipelineSubmitForm, PipelineStatusView, PhaseTimeline) |
| 2 | `stores/workflowStore.ts` | Real-time pipeline state |
| 3 | `features/auth/` | types, services, hooks (useAuth), components (LoginForm, RegisterForm) |
| 4 | App pages | `pipeline/page.tsx`, `pipeline/[runId]/page.tsx`, `(auth)/login/page.tsx`, `(auth)/register/page.tsx` |

**Verify**: Pipeline form submits, status page polls and displays phases

### Phase 3: Task Creation Flow

| # | Feature | Files |
|---|---------|-------|
| 1 | `features/task-flow/` | types, services, hooks (useTaskFlow), store (taskFlowStore), components (TaskForm, ClarificationChat, FileUploadZone) |
| 2 | `features/literature/` | types, services, hooks, components |
| 3 | App pages | `tasks/agent-create/`, `tasks/new/`, `tasks/literature/candidates/` |

### Phase 4: Evidence Review

| # | Feature | Files |
|---|---------|-------|
| 1 | `features/evidence/` | types, services, hooks, components |
| 2 | `features/source-link/` | types, services, hooks, components |
| 3 | `features/delta-audit/` | types, services, hooks, components |
| 4 | `features/document-viewer/` | types, hooks, components, utils (normalizeEvidence, normalizePaperResult) |
| 5 | App pages | `evidence/[evidenceId]/`, `evidence/audit/`, `documents/[documentId]/`, `requests/[requestId]/export/` |

### Phase 5: Supporting Features

| # | Feature | Files |
|---|---------|-------|
| 1 | `features/chat/` | types, services, hooks (useChatStream with SSE), components |
| 2 | `features/graph/` | types, services, hooks, components |
| 3 | `src/lib/api/sse.ts` | Generic SSE EventSource wrapper |
| 4 | App pages | `chat/`, `graph/` |

---

## Notes

- Remove all `.gitkeep` files from directories that now contain real code
- AGENTS.md requires `progress.txt` updates after each phase
- Check `.old_version/` before implementing each feature for reuse opportunities
- `tsconfig.json` path alias `@/*` → `./src/*` is already correct, no change needed
