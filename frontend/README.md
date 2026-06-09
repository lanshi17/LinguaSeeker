# Frontend — ACMG Lingua

> Next.js 15 App Router frontend for a medical genetics evidence extraction platform. Business feature architecture with thin page shells, self-contained feature modules, and shared infrastructure.

## Quick Start

```bash
# From the frontend/ directory
npm install
npm run dev          # Starts on http://localhost:3000
```

The dev server proxies `/api/v1/*` to `http://localhost:8000` (the backend). No environment variables are required for local development.

```bash
npm run type-check   # tsc --noEmit — verify types
npm run lint         # ESLint — verify code style
npm run build        # Production build
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  app/                           (thin page shells only)     │
│  ┌──────────┐ ┌──────────────┐ ┌──────────────────────────┐ │
│  │ (auth)/   │ │(dashboard)/  │ │  app/layout.tsx          │ │
│  │  login    │ │  pipeline/   │ │    QueryProvider          │ │
│  │  register │ │  evidence/   │ │    NotificationToast      │ │
│  │           │ │  chat/       │ │                            │ │
│  │           │ │              │ │  app/(dashboard)/layout   │ │
│  │           │ │              │ │    DashboardLayout        │ │
│  │           │ │              │ │      Sidebar + main       │ │
│  └──────────┘ └──────────────┘ └──────────────────────────┘ │
└────────────────────────┬────────────────────────────────────┘
                         │ imports from
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  src/features/              (4 implemented modules)         │
│                                                             │
│  auth/  pipeline/  evidence-search/  chat/                  │
│                                                             │
│  Each module:                                               │
│  ├── index.ts        ← barrel export (public API)           │
│  ├── components/     ← presentational + container           │
│  ├── hooks/          ← TanStack Query + state hooks         │
│  ├── services/       ← Axios API calls                      │
│  ├── types/          ← request/response/domain types        │
│  └── utils/          ← feature-local utilities (optional)   │
└────────────────────────┬────────────────────────────────────┘
                         │ imports from
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  src/                   (shared infrastructure)              │
│                                                             │
│  lib/api/       client.ts (Axios), error.ts                 │
│  lib/config/    app.ts, api.ts, types.ts                    │
│  lib/hooks/     usePolling, useDebounce, useBackendHealth   │
│  lib/types/     common.ts                                   │
│  lib/utils/     cn.ts (clsx + tailwind-merge)               │
│                                                             │
│  stores/        appStore, toastStore (global Zustand)       │
│                                                             │
│  components/    ui/ (Button, Card, Input, ...)               │
│                 layout/ (DashboardLayout, Sidebar, ...)      │
└─────────────────────────────────────────────────────────────┘
```

### Import Rules

```
page.tsx  ──→  @/features/<name>  (barrel only)
                  │
                  ├── components/ ──→ hooks/ ──→ services/ ──→ @/lib/api/client
                  └── components/ ──→ @/components/ui/*
```

**Forbidden:** Feature → another feature's internals. Page → `@/lib/api/client` directly.

### Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | Next.js (App Router) | ^15.0.0 |
| UI | React | ^18.3.0 |
| Data fetching | TanStack React Query | ^5.50.0 |
| HTTP client | Axios | ^1.7.0 |
| Client state | Zustand | ^4.5.0 |
| Styling | Tailwind CSS | ^3.4.0 |
| Icons | Lucide React | ^1.17.0 |
| Language | TypeScript (strict) | ^5.5.0 |
| Path alias | `@/*` → `./src/*` | tsconfig paths |

## Feature Modules

### Module Inventory

| Module | Components | Hooks | Types | Backend API |
|--------|-----------|-------|-------|-------------|
| **auth** | 2 | 1 | 1 | `POST /auth/login`, `POST /auth/register` |
| **pipeline** | 4 | 3 | 1 | `POST /pipeline/run`, `GET /pipeline/runs/{id}/status` |
| **evidence-search** | 5 | 2 | 1 | `POST /evidence/search`, `GET /evidence/{id}` |
| **chat** | 3 | 2 | 1 | `CRUD /chat/sessions`, `POST /chat/messages` |

**Totals:** 14 components, 8 hooks across 4 implemented modules.

### Pipeline (backbone feature)

The pipeline feature is the central data flow — every other feature depends on its output.

```typescript
// Start a pipeline run
const { mutateAsync: startRun } = usePipelineRun();
const result = await startRun({
  source_type: "online",
  mode: "full",
  query: "BRCA1 pathogenic variant breast cancer",
});
// → { processing_run_id: "abc-123", status_url: "/pipeline/runs/abc-123/status" }

// Poll status (auto-stops on terminal state)
const { data } = usePipelineStatus("abc-123");
// → { pipeline_status: "running", phases: [{ phase_id: "phase_1", status: "completed", ... }, ...] }

// Project to timeline steps for the PhaseTimeline component
const steps = usePhaseTimeline(data);
// → [{ phaseId: "phase_1", label: "Document Acquisition", status: "completed", duration: 12.3 }, ...]
```

### Chat (SSE streaming)

The chat feature uses Server-Sent Events for real-time AI replies. Callbacks are stored in refs to prevent infinite reconnection loops.

```typescript
// List sessions for a run
const { sessions, createSession } = useChatSessions(processingRunId);

// Send a message and get the AI reply
const { messages, sendMessage } = useChatMessages(sessionId);
await sendMessage({ content: "What is the ACMG classification?" });
```

### Evidence Search

The evidence search feature provides search, results table, and detail views for extracted evidence.

```typescript
// Search evidence
const { data, isLoading } = useEvidenceSearch({ query: "BRCA1", ... });

// View group detail
const { data: detail } = useEvidenceGroupDetail(groupId);
```

## Shared Infrastructure

### API Client (`src/lib/api/client.ts`)

Centralized Axios instance with two interceptors:

1. **Request:** Injects `Bearer` token from `localStorage`
2. **Response:** On 401, clears token and redirects to `/login` (with duplicate-navigation guard). All errors normalized to `ApiError`.

```typescript
import { apiClient } from "@/lib/api/client";

// All feature services use this same instance
const { data } = await apiClient.get<PipelineStatusResponse>(
  `/pipeline/runs/${runId}/status`,
);
```

### Error Handling (`src/lib/api/error.ts`)

```typescript
import { ApiError, normalizeError } from "@/lib/api/error";

try {
  await startPipelineRun(body);
} catch (err) {
  if (err instanceof ApiError) {
    console.error(err.status);        // 400, 409, 500, or 0 (network)
    console.error(err.backendMessage); // "Run already in progress"
  }
}
```

### Toast Notifications (`src/stores/toastStore.ts`)

```typescript
import { useToastStore } from "@/stores/toastStore";

// From any component or hook
useToastStore.getState().addToast({
  level: "success",
  title: "Pipeline started",
  message: "Run ID: abc-123",
  ttl: 5000, // optional, default 4000ms
});
```

### Class Name Utility (`src/lib/utils/cn.ts`)

```typescript
import { cn } from "@/lib/utils/cn";

// Conditional classes with Tailwind conflict resolution
<div className={cn(
  "px-4 py-2",
  isActive && "bg-primary-600",
  className,  // parent override — px-2 here correctly overrides px-4
)} />
```

### Error Boundary (`src/components/ui/ErrorBoundary.tsx`)

```tsx
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";

<ErrorBoundary onError={(err) => logToSentry(err)}>
  <EvidenceJudgmentPane rawData={backendResponse} />
</ErrorBoundary>
```

## Page Composition Pattern

Every page follows the same pattern — thin shell, feature component does the work:

```tsx
// app/(dashboard)/pipeline/[runId]/page.tsx  (15 lines)
import { PipelineStatusView } from "@/features/pipeline";

interface PipelineRunPageProps {
  params: Promise<{ runId: string }>;
}

export default async function PipelineRunPage({ params }: PipelineRunPageProps) {
  const { runId } = await params;
  return (
    <div className="space-y-6">
      <PipelineStatusView runId={runId} />
    </div>
  );
}
```

The page extracts route params and passes them down. `PipelineStatusView` owns all data fetching (via `usePipelineStatus`), loading states, error handling, and rendering. The page never touches `apiClient`, `useQuery`, or any domain types.

## Routing

| Route | Page | Status |
|-------|------|--------|
| `/` | Landing / redirect | Active |
| `/login` | `LoginForm` | Active |
| `/register` | `RegisterForm` | Active |
| `/pipeline` | `PipelineSubmitForm` + run list | Active |
| `/pipeline/[runId]` | `PipelineStatusView` + phase timeline | Active |
| `/evidence` | `EvidenceSearchView` + `EvidenceSearchForm` | Active |
| `/evidence/detail` | `EvidenceDetailView` | Active |
| `/chat` | `ChatView` session list | Active |
| `/chat/[sessionId]` | Chat conversation with messages | Active |

**Active** = wires real feature components with data fetching and rendering.

## Extension Guide

### Adding a New Feature Module

1. Create the directory structure:
   ```bash
   mkdir -p src/features/<name>/{components,hooks,services,types}
   ```

2. Define types in `types/<name>.ts`:
   ```typescript
   export interface MyRequest { ... }
   export interface MyResponse { ... }
   ```

3. Create the service in `services/<name>.ts`:
   ```typescript
   import { apiClient } from "@/lib/api/client";
   export async function fetchSomething(): Promise<MyResponse> {
     const { data } = await apiClient.get<MyResponse>("/my-endpoint");
     return data;
   }
   ```

4. Create hooks in `hooks/` using TanStack Query:
   ```typescript
   import { useQuery } from "@tanstack/react-query";
   import { fetchSomething } from "../services/<name>";
   export function useSomething() {
     return useQuery({ queryKey: ["something"], queryFn: fetchSomething });
   }
   ```

5. Create components in `components/` — they import from `../hooks` and `@/components/ui`.

6. Create the barrel export in `index.ts`:
   ```typescript
   export { MyComponent } from "./components/MyComponent";
   export { useSomething } from "./hooks/useSomething";
   export type { MyRequest, MyResponse } from "./types/<name>";
   ```

7. Create the page shell in `app/(dashboard)/<route>/page.tsx`:
   ```tsx
   import { MyComponent } from "@/features/<name>";
   export default function Page() {
     return <MyComponent />;
   }
   ```

### Adding a New UI Primitive

Add to `src/components/ui/`. Follow the existing pattern: forward ref, accept `className`, compose with `cn()`.

```tsx
import { cn } from "@/lib/utils/cn";

interface TooltipProps {
  content: string;
  children: React.ReactNode;
  className?: string;
}

export function Tooltip({ content, children, className }: TooltipProps) {
  return (
    <div className={cn("relative group", className)}>
      {children}
      <div className="invisible group-hover:visible absolute ...">
        {content}
      </div>
    </div>
  );
}
```

## Dependencies

| Package | Purpose |
|---------|---------|
| `next` | App framework (App Router, SSR, API routes) |
| `react` / `react-dom` | UI library |
| `@tanstack/react-query` | Server state: caching, polling, mutations |
| `axios` | HTTP client with interceptors |
| `zustand` | Lightweight client state (sidebar, toasts) |
| `clsx` | Conditional class joining |
| `tailwind-merge` | Tailwind class conflict resolution |
| `lucide-react` | SVG icon library |
| `tailwindcss` | Utility-first CSS framework |

## Testing

```bash
# All tests
npm run test

# Single feature
npm run test -- --testPathPattern=features/pipeline
```

Tests mirror source structure under `tests/`:
```
tests/
├── features/
│   ├── pipeline/       # usePipelineStatus polling logic
│   ├── chat/           # useChatStream reconnection
│   └── ...
├── components/
│   └── ui/             # Button, Modal rendering
└── lib/
    └── api/            # client interceptor behavior
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_BASE_URL` | `/api/v1` | Backend API base URL |

All API requests go through `next.config.ts` rewrites in development: `/api/v1/*` → `http://localhost:8000/api/v1/*`.
