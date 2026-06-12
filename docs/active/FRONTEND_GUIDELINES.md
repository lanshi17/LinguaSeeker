# FRONTEND_GUIDELINES — CrossEvidence Frontend

## 1. Tech Stack

| Concern | Choice | Notes |
|---|---|---|
| Framework | Next.js (App Router) | File-based routing, layouts, SSR |
| UI Library | React 18 | Concurrent features |
| Language | TypeScript 5.5+ | Strict mode |
| Styling | Tailwind CSS 3.4 | Utility-first, no CSS-in-JS. `clsx` + `tailwind-merge` for class merging |
| UI Components | Custom primitives + Ant Design 6 | `src/components/ui/` for base components; `antd` + `@ant-design/x` for advanced widgets |
| Icons | lucide-react | Tree-shakeable SVG icons |
| Client State | Zustand 4.5 | `appStore`, `toastStore` |
| Server State | React Query 5.50 | Caching, invalidation |
| HTTP | Axios 1.7 | Calls `/api/v1/*` through Next.js proxy |
| Linting | ESLint 9 + Next config | Google TypeScript Style |
| Type Check | TypeScript compiler | Current-stage frontend verification |

FastAPI is authoritative for authentication and API behavior. Next.js proxies requests and renders UI; it does not sign or verify JWTs. In open-source deployment, all data is visible to all visitors -- no user isolation. Transparency is maintained via delta audit logs.

## 2. Product UX Principles

### 2.1 Core Positioning

CrossEvidence is an "evidence porter" -- absolutely loyal to source data. Every piece of extracted information must be 100% traceable to its original location in the literature.

### 2.2 Design Principles

- **Minimal**: Every screen element must justify its existence. No decorative chrome.
- **Transparent**: Every piece of data must be traceable to its source. No black-box summaries that hide extraction provenance.
- **Restrained**: The system collects, structures, and presents -- it does not interpret or diagnose.
- **Open by default**: No user isolation. Transparency replaces permission systems -- all actions recorded in audit logs.

### 2.3 Evidence-First Framing

- Current UI presents extracted and standardized evidence, not final autonomous medical classification.
- Reports and result pages must describe outputs as evidence summaries and extraction results.
- Low confidence, missing traceability, ambiguous standardization, and extraction disagreement must be visible.
- Biomedical strings (HGVS, rsIDs, transcript IDs, gene symbols) use monospace formatting.

### 2.4 Bi-Directional Traceability

- Every evidence item shown in the UI must link to an original source span.
- Clicking/tapping an evidence item must scroll to and highlight the source text.
- If a result lacks required anchors/bbox-backed spans, the UI displays it as invalid/incomplete.

## 3. Navigation Structure

The dashboard uses a collapsible sidebar layout. The root page (`/`) redirects to `/chat`.

```
┌─────────────┬───────────────────────────────────────────┐
│  CrossEvidence│                                           │
│             │              Top Bar                       │
│  [AI Chat]  ├───────────────────────────────────────────┤
│  [Evidence] │                                           │
│             │              Page Content                  │
│             │                                           │
│             │                                           │
│  v0.1.0     │                                           │
└─────────────┴───────────────────────────────────────────┘
```

| Section | Route | Core Responsibility |
|---|---|---|
| AI Chat | `/(dashboard)/chat` | Chat sessions list; `/chat/[sessionId]` for individual conversation with pipeline integration |
| Evidence | `/(dashboard)/evidence` | Search and browse extracted evidence; `/evidence/detail` for evidence detail view |
| Pipeline | `/(dashboard)/pipeline` | Submit and monitor pipeline runs; `/pipeline/[runId]` for run detail (accessible via direct URL or chat forms) |
| Auth | `/(auth)/login`, `/(auth)/register` | Login and registration (separate layout group) |

**Note**: The Sidebar currently renders two navigation items (AI Chat, Evidence). Pipeline routes exist and are functional but are accessed through the chat interface's pipeline forms rather than a dedicated sidebar link.

## 4. Directory Structure

```
frontend/
├── app/
│   ├── layout.tsx                   # Root layout with QueryProvider + NotificationToast
│   ├── page.tsx                     # Redirect to /chat
│   ├── globals.css                  # Tailwind base styles
│   ├── providers.tsx                # React Query provider wrapper
│   ├── (auth)/
│   │   ├── login/page.tsx           # Login page
│   │   └── register/page.tsx        # Registration page
│   └── (dashboard)/
│       ├── layout.tsx               # Dashboard shell with Sidebar + top bar
│       ├── chat/
│       │   ├── page.tsx             # Chat sessions list
│       │   └── [sessionId]/page.tsx # Individual chat session
│       ├── evidence/
│       │   ├── page.tsx             # Evidence search
│       │   └── detail/page.tsx      # Evidence detail view
│       └── pipeline/
│           ├── page.tsx             # Pipeline list / submit
│           └── [runId]/page.tsx     # Pipeline run detail
├── src/
│   ├── features/                    # Vertical feature slices
│   │   ├── auth/
│   │   │   ├── components/ (LoginForm.tsx, RegisterForm.tsx)
│   │   │   ├── services/ (auth.ts)
│   │   │   ├── types/ (auth.ts)
│   │   │   ├── hooks/ (useAuth.ts)
│   │   │   └── index.ts
│   │   ├── pipeline/
│   │   │   ├── components/ (PipelineSubmitForm.tsx, PipelineStatusView.tsx,
│   │   │   │                 PhaseTimeline.tsx, PhaseDetailCard.tsx)
│   │   │   ├── services/ (pipeline.ts)
│   │   │   ├── types/ (pipeline.ts)
│   │   │   ├── hooks/ (usePipelineStatus.ts, usePipelineRun.ts, usePhaseTimeline.ts)
│   │   │   └── index.ts
│   │   ├── evidence-search/
│   │   │   ├── components/ (EvidenceSearchView.tsx, EvidenceSearchForm.tsx,
│   │   │   │                 EvidenceResultsTable.tsx, EvidenceDetailView.tsx,
│   │   │   │                 EvidenceHighlightText.tsx)
│   │   │   ├── services/ (evidenceSearch.ts)
│   │   │   ├── types/ (evidenceSearch.ts)
│   │   │   ├── hooks/ (useEvidenceSearch.ts, useEvidenceGroupDetail.ts)
│   │   │   ├── utils/ (evidenceDocument.ts, literatureRows.ts)
│   │   │   └── index.ts
│   │   └── chat/
│   │       ├── components/ (ChatView.tsx, forms/ with PipelineStartForm.tsx,
│   │       │                 PipelineStatusCard.tsx)
│   │       ├── services/ (chat.ts)
│   │       ├── types/ (chat.ts)
│   │       ├── hooks/ (useChatMessages.ts, useChatSessions.ts)
│   │       ├── providers/ (acmgChatProvider.ts)
│   │       └── index.ts
│   ├── components/
│   │   ├── layout/ (DashboardLayout.tsx, Sidebar.tsx, PageHeader.tsx,
│   │   │           ConnectionStatus.tsx)
│   │   └── ui/ (Button.tsx, Card.tsx, Modal.tsx, Spinner.tsx, Badge.tsx,
│   │             Select.tsx, Input.tsx, Toast.tsx, ErrorBoundary.tsx)
│   ├── lib/
│   │   ├── api/ (client.ts, error.ts)
│   │   ├── config/ (app.ts, api.ts, types.ts, index.ts)
│   │   ├── hooks/ (useDebounce.ts, useBackendHealth.ts, usePolling.ts)
│   │   ├── types/ (common.ts)
│   │   └── utils/ (cn.ts)
│   └── stores/
│       ├── appStore.ts              # Sidebar collapsed state
│       ├── toastStore.ts            # Global toast notifications
│       └── index.ts                 # Re-exports
├── tests/
├── public/
├── next.config.ts
├── package.json
└── tsconfig.json
```

### 4.1 Component Architecture (Orchestrated Vertical Slices)

Frontend modules mirror Orchestrated Vertical Slice Architecture at UI scale:

```
app/<section>/page.tsx       # Page-level orchestration and data composition only
src/features/<feature>/      # Vertical UI feature slices (components, services, types, hooks)
src/components/ui/           # Shared primitives (no ACMG domain concepts)
src/components/layout/       # Shell layout components
src/lib/api/                 # Backend API providers
src/lib/hooks/               # Shared hooks
src/lib/types/               # Cross-feature contracts
src/stores/                  # Global UI/runtime state only
```

Rules:
- `api`/hook layer fetches or mutates backend data.
- Component views render state and emit typed events.
- Shared UI primitives stay generic -- no ACMG evidence concepts.
- Page files wire slices together and pass state; they do not contain business rules.

## 5. Current Implementation: Chat Feature

The chat feature is the primary entry point. It provides conversation-based interaction with pipeline integration.

### 5.1 Components

- **ChatView.tsx** -- Main chat interface rendering message streams.
- **PipelineStartForm.tsx** -- Form embedded in chat to start new pipeline runs.
- **PipelineStatusCard.tsx** -- Inline card showing pipeline run status within chat context.

### 5.2 Hooks

- **useChatMessages.ts** -- Message state and send operations for a chat session.
- **useChatSessions.ts** -- Session list management and session switching.

### 5.3 Services

- **chat.ts** -- API calls for chat sessions and messages.
- **acmgChatProvider.ts** -- Chat provider abstraction for ACMG-specific chat behavior.

### 5.4 Types

- **chat.ts** -- Message, Session, and related type definitions.

---

## 6. Current Implementation: Evidence Search

The evidence search feature provides structured search and browsing of extracted evidence data.

### 6.1 Components

- **EvidenceSearchView.tsx** -- Top-level view composing search form and results.
- **EvidenceSearchForm.tsx** -- Search input with filtering options.
- **EvidenceResultsTable.tsx** -- Tabular display of search results.
- **EvidenceDetailView.tsx** -- Detailed view for a selected evidence item or group.
- **EvidenceHighlightText.tsx** -- Text rendering with source highlight annotations.

### 6.2 Hooks

- **useEvidenceSearch.ts** -- Search state, query execution, and result caching.
- **useEvidenceGroupDetail.ts** -- Detail view state for evidence groups.

### 6.3 Services & Utils

- **evidenceSearch.ts** -- API calls for evidence search and detail.
- **evidenceDocument.ts** -- Document-level evidence processing utilities.
- **literatureRows.ts** -- Literature table row transformation utilities.

### 6.4 Types

- **evidenceSearch.ts** -- Search query, result, and evidence item type definitions.

---

## 7. Current Implementation: Pipeline

The pipeline feature manages submission and monitoring of processing runs.

### 7.1 Components

- **PipelineSubmitForm.tsx** -- Form to configure and submit a new pipeline run.
- **PipelineStatusView.tsx** -- Top-level status view for a pipeline run.
- **PhaseTimeline.tsx** -- Visual timeline of pipeline phases.
- **PhaseDetailCard.tsx** -- Detailed card for an individual pipeline phase.

### 7.2 Hooks

- **usePipelineStatus.ts** -- Polling/fetching pipeline run status.
- **usePipelineRun.ts** -- Single pipeline run state management.
- **usePhaseTimeline.ts** -- Phase timeline data and progression state.

### 7.3 Services

- **pipeline.ts** -- API calls for pipeline submission, status, and phase details.

### 7.4 Types

- **pipeline.ts** -- Pipeline run, phase, and status type definitions.

---

## 8. Current Implementation: Auth

Authentication feature with login and registration forms.

### 8.1 Components

- **LoginForm.tsx** -- Login form with credential submission.
- **RegisterForm.tsx** -- Registration form for new users.

### 8.2 Hooks & Services

- **useAuth.ts** -- Authentication state, login/logout/register operations.
- **auth.ts** -- API calls for authentication endpoints.

### 8.3 Types

- **auth.ts** -- User, credentials, and auth response type definitions.

---

## 9. State Management

### 9.1 appStore

```typescript
interface AppState {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
}
```

### 9.2 toastStore

```typescript
type ToastLevel = "info" | "success" | "warning" | "error";

interface Toast {
  id: string;
  level: ToastLevel;
  title: string;
  message?: string;
  ttl?: number;  // Auto-dismiss ms, default 4000
}

interface ToastState {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, "id">) => void;
  removeToast: (id: string) => void;
}
```

Feature-specific state is managed locally within each feature's hooks (e.g., `useChatSessions`, `usePipelineStatus`, `useEvidenceSearch`). Cross-cutting UI state that cannot be scoped to a single feature lives in the stores above.

## 10. API Client Organization

```
src/lib/api/
├── client.ts          # Axios instance, base URL, interceptors, auth token injection
└── error.ts           # API error types and error handling utilities
```

Feature-specific API services are co-located within each feature slice:

```
src/features/<feature>/services/
├── auth.ts            # POST /auth/login, POST /auth/register
├── chat.ts            # Chat session and message endpoints
├── pipeline.ts        # Pipeline submit, status, phase detail endpoints
└── evidenceSearch.ts  # Evidence search and detail endpoints
```

## 11. Shared Hooks

```
src/lib/hooks/
├── useDebounce.ts     # Debounce value changes (search inputs, etc.)
├── useBackendHealth.ts # Backend connectivity health check
└── usePolling.ts      # Generic polling hook for status updates
```

## 12. Communication Protocol

### REST for CRUD

Standard JSON REST for all current features: auth, chat sessions/messages, pipeline operations, evidence search.

### SSE / Streaming (Planned)

Future chat streaming support may use Server-Sent Events for real-time message delivery and pipeline progress updates.

---

*Document version v3.0 -- 2026-06-09 -- Rewritten to reflect actual implemented frontend. Removed references to planned features (Vercel AI SDK, shiki, react-markdown, shadcn/ui, 4-tab layout, task board, knowledge base, settings).*
