# Frontend -- Lingua Seeker

> Vite + React 18 SPA for medical genetics evidence extraction, built with a feature-sliced architecture: thin page shells, self-contained feature modules, and shared infrastructure.

## Quick Start

```bash
cd frontend
bun install           # install dependencies (bun.lock)
bun run dev           # Vite dev server on :3000 (proxies /api/v1 -> :8000)
bun run build         # tsc --noEmit && vite build -> dist/
bun run test          # vitest run (16 test files)
bun run type-check    # tsc --noEmit
bun run lint          # eslint .
```

The backend must be running on `:8000` for API calls.

## Architecture

```
index.html
  -> src/main.tsx                    # Entry: BrowserRouter + ConfigProvider + QueryProvider + App
       -> src/App.tsx                # Route table (React Router v7)
            -> <DashboardLayout>     # Dashboard routes (open access, no login)
                 +-- /chat, /chat/:sessionId
                 +-- /evidence, /evidence/detail
                 +-- /evidence-db, /evidence-db/:variantSlug, /evidence-db/:variantSlug/:sourceDocumentId
                 +-- /pipeline, /pipeline/:runId
                 +-- /audit
```

```
src/
|-- main.tsx              # Vite entry -- mounts React root
|-- App.tsx               # All routes in one file (lazy-loaded pages)
|-- providers.tsx         # QueryClientProvider (React Query)
|-- theme.ts              # antd theme configuration
|-- globals.css           # Custom animations and utility classes
|-- api/                  # Shared API functions (evidence search, annotations)
|   |-- evidence.ts       # searchEvidence, getEvidenceGroupDetail
|   +-- annotations.ts    # Document annotation CRUD
|-- components/           # Shared UI + layout (cross-feature)
|   |-- layout/           # DashboardLayout, Sidebar, PageHeader, ConnectionStatus
|   +-- ui/               # Badge, Spinner, ErrorBoundary, MetricTile, LivePulse, Skeleton, PageTransition
|-- features/             # Vertical feature slices (self-contained)
|   |-- audit/            # Audit trail: event table, detail drawer, evidence review
|   |-- chat/             # AI chat: SSE streaming, sessions, action dispatching
|   |-- evidence-search/  # Evidence search, detail, bilingual comparison, annotations
|   |-- evidence-db/      # Variant-centric database: index, detail, bilingual evidence view
|   +-- pipeline/         # Pipeline status, phase timeline, run history, task queue
|-- pages/                # Route-level page components (thin shells)
|   |-- ChatPage.tsx
|   |-- ChatSessionPage.tsx
|   |-- EvidencePage.tsx
|   |-- EvidenceDetailPage.tsx
|   |-- EvidenceDbPage.tsx
|   |-- PipelinePage.tsx
|   |-- PipelineRunPage.tsx
|   +-- AuditPage.tsx
|-- lib/                  # Shared infrastructure
|   |-- api/              # apiClient (Axios), ApiError, normalizeError
|   |-- hooks/            # useBackendHealth, useElapsedSeconds
|   |-- types/            # ProcessingStatus, PhaseId
|   +-- utils/            # formatDuration, formatRelative, formatTimestamp
+-- stores/               # Zustand stores
    +-- appStore.ts       # Global UI state (sidebar collapsed)
```

### Request Flow

```
Component -> feature hook (useQuery/useMutation)
  -> feature service (axios call via apiClient)
    -> Vite proxy (/api/v1/* -> http://localhost:8000)
      -> FastAPI backend
        -> Response
  <- React Query cache -> component re-render
```

### Auth

Open-access research tool -- no login required. The frontend has no authentication guard; all routes are publicly accessible. Set `API_KEY` on the backend to optionally re-enable API-key/session-cookie auth.

## Public API

### Feature Exports

Each feature exposes its public API through a barrel `index.ts`:

| Feature | Key Exports |
|---------|-------------|
| `@/features/chat` | `ChatView`, `useChatSessions`, `createAcmgChatProvider`, `sendChatMessage` |
| `@/features/evidence-search` | `EvidenceSearchView`, `EvidenceDetailView`, `BilingualComparison`, `useEvidenceSearch`, `useEvidenceGroupDetail`, `buildEvidenceDocument`, `CATEGORY_COLORS`, `buildLiteratureRows`, `buildBilingualCompareHref` |
| `@/features/evidence-db` | `VariantIndexView`, `VariantDetailView`, `BilingualEvidenceView` |
| `@/features/pipeline` | `PipelineStatusView`, `PhaseTimeline`, `PhaseDetailCard`, `RunHistory`, `TaskQueuePanel`, `usePipelineRun`, `usePipelineStatus`, `usePipelineRuns`, `usePhaseTimeline` |
| `@/features/audit` | `AuditView`, `AuditEventTable`, `AuditEventDetailDrawer`, `EvidenceReviewDrawer`, `useAuditEvents`, `listAuditEvents` |

### Shared Hooks (`@/lib/hooks`)

| Hook | Signature | Description |
|------|-----------|-------------|
| `useBackendHealth` | `() => BackendHealth` | Polls `GET /health` at configurable interval; returns `status`, `latencyMs`, `lastChecked` |
| `useElapsedSeconds` | `(start: string \| null) => number` | Returns elapsed seconds since a timestamp, updating every 250ms |

### Zustand Stores (`@/stores`)

| Store | Key State | Description |
|-------|-----------|-------------|
| `useAppStore` | `sidebarCollapsed`, `toggleSidebar()`, `setSidebarCollapsed()` | Global UI state (sidebar collapse) |

### API Client (`@/lib/api`)

| Export | Signature | Description |
|--------|-----------|-------------|
| `apiClient` | `AxiosInstance` | Pre-configured Axios instance: baseURL from env, 30s timeout, error normalization via `normalizeError` |
| `ApiError` | `class extends Error` | Normalized error with `status: number` and `backendMessage: string` |
| `normalizeError` | `(err: AxiosError) => ApiError` | Converts Axios errors to ApiError (network failures get status 0) |
| `extractErrorMessage` | `(err: unknown, fallback?) => string` | Duck-typed error message extraction for UI display |

## Internal Design

### Routing (React Router v7)

All routes are defined in `src/App.tsx` and nested under a single `<DashboardLayout>` wrapper (open access, no auth guard). Pages are lazy-loaded via `React.lazy()` for code splitting.

`DashboardLayout` renders the sidebar, topbar, and `<AnimatedOutlet />` for nested route content with page transition animations. Dynamic segments (`:sessionId`, `:runId`, `:variantSlug`) are accessed via `useParams`. Query parameters (`?groupId=...`) are accessed via `useSearchParams`.

### Feature Slice Pattern

Each feature in `src/features/` follows the same structure:

```
features/<name>/
|-- index.ts           # Barrel: public exports
|-- components/        # React components
|-- hooks/             # React Query hooks (useQuery, useMutation)
|-- services/          # API call functions (axios via apiClient)
|-- types/             # TypeScript types
+-- utils/             # Feature-specific utilities (optional)
```

Hooks wrap React Query's `useQuery`/`useMutation` and call service functions. Components consume hooks and render UI. Pages in `src/pages/` are thin shells that compose feature components.

### State Management

- **Server state**: React Query (TanStack Query) with `staleTime: 30s`, `retry: 1`, `refetchOnWindowFocus: false` (set in `QueryProvider`).
- **Global UI state**: Zustand store (`appStore` for sidebar collapse).

### Styling

Ant Design 6.x with inline styles and antd theme tokens. CSS custom properties defined in `globals.css` provide the design system (medical teal primary). Custom animations (fadeIn, slideInRight, shimmer, thinkingBounce, chatCursorBlink, ping) are defined in `src/globals.css`.

## Usage Patterns

### Adding a New Feature Page

```tsx
// 1. Create the page component in src/pages/MyFeaturePage.tsx
import { MyFeatureView } from "@/features/my-feature";

export function MyFeaturePage() {
  return <MyFeatureView />;
}

// 2. Add the route in src/App.tsx inside the DashboardLayout wrapper
<Route path="/my-feature" element={<MyFeaturePage />} />

// 3. Add nav item in src/components/layout/Sidebar.tsx
const NAV_ITEMS = [
  // ...
  { label: "My Feature", href: "/my-feature", icon: MyIcon },
];
```

### Using the API Client in a Feature Service

```typescript
// features/my-feature/services/myFeatureApi.ts
import { apiClient } from "@/lib/api/client";
import type { MyFeatureData } from "../types";

export async function fetchMyFeature(id: string): Promise<MyFeatureData> {
  const res = await apiClient.get(`/my-feature/${id}`);
  return res.data;
}
```

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `react` / `react-dom` | ^18.3.0 | UI framework |
| `react-router-dom` | ^7.0.0 | Client-side routing |
| `vite` | ^6.0.0 | Build tool + dev server |
| `@vitejs/plugin-react` | ^4.3.0 | React Fast Refresh + JSX transform |
| `antd` | ^6.4.3 | UI component library |
| `@ant-design/x` / `x-sdk` | ^2.7.0 | AI chat components (Bubble, Sender, Conversations, XProvider) |
| `@tanstack/react-query` | ^5.50.0 | Server state management (caching, polling, mutations) |
| `axios` | ^1.7.0 | HTTP client |
| `zustand` | ^4.5.0 | Lightweight global state (sidebar) |
| `lucide-react` | ^1.17.0 | Icon set |
| `react-markdown` | ^10.1.0 | Markdown rendering |
| `remark-gfm` | ^4.0.1 | GitHub-flavored Markdown support |
| `remark-math` / `rehype-katex` | ^6.0.0 / ^7.0.1 | LaTeX math rendering |
| `katex` | ^0.17.0 | Math typesetting |
| `vitest` | ^4.1.8 | Test runner (jsdom environment) |
| `@testing-library/react` | ^16.3.2 | Component testing utilities |
| `typescript` | ^5.5.0 | Type checking |

## Testing

```bash
bun run test          # vitest run (16 test files)
bun run type-check    # tsc --noEmit
bun run lint          # eslint .
```

Test files live in `frontend/tests/` and mirror the source structure:

```
tests/
|-- audit/                         # Audit feature tests
|   |-- reviewPatch.test.tsx
|   +-- useAuditEvents.test.tsx
|-- config/
|   +-- layeredConfig.test.ts      # Config singleton behavior
|-- evidence-db/
|   +-- variantAggregation.test.tsx # Variant aggregation utilities
|-- evidence-search/
|   |-- BilingualComparison.test.tsx
|   |-- EvidenceHighlightText.test.tsx
|   +-- literatureRows.test.ts     # Literature row aggregation
+-- features/
    +-- chat/                      # Chat feature tests
        |-- acmgChatProvider.test.tsx
        |-- ChatActionBubble.test.tsx
        |-- ChatMarkdown.test.tsx
        |-- localSessions.test.ts
        |-- messageHistory.test.ts
        |-- messageRequests.test.ts
        |-- messageStore.test.tsx
        |-- sse.test.ts
        +-- useChatSessions.test.tsx
```

Tests use Vitest with jsdom environment. React Query is tested via `@testing-library/react`. Pure logic utilities are tested without React rendering.

### Environment Variables

All env vars use the `VITE_` prefix (required by Vite to expose them to the client). They are loaded from layered `.env` files:

| File | Priority | Purpose |
|------|----------|---------|
| `.env` | Lowest | Safe defaults, committed to git |
| `.env.development` | Medium | Dev overrides (loaded when `NODE_ENV=development`) |
| `.env.production` | Medium | Production overrides (loaded when `NODE_ENV=production`) |
| `.env.local` | Highest | Local secrets, git-ignored |

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_APP_NAME` | `Lingua Seeker` | Application display name |
| `VITE_APP_VERSION` | `0.0.0` | Semantic version |
| `VITE_API_BASE_URL` | `/api/v1` | API base URL (must be relative for proxy) |
| `VITE_API_TIMEOUT` | `30000` | Request timeout in ms |
| `VITE_HEALTH_ENDPOINT` | `/health` | Backend health check endpoint |
| `VITE_HEALTH_POLL_INTERVAL` | `30000` | Health poll interval in ms |
| `VITE_BASE_PATH` | `/` | SPA mount subpath (e.g. `/linguaseeker`) |

## Extension Guide

### Adding a New Feature Slice

1. Create `src/features/<name>/` with `index.ts`, `components/`, `hooks/`, `services/`, `types/`.
2. Export all public symbols from `index.ts` (barrel pattern).
3. Use `apiClient` from `@/lib/api/client` in service functions -- never create a new Axios instance.
4. Wrap API calls in React Query hooks, not in components directly.
5. Create a page component in `src/pages/` and add a route in `src/App.tsx`.

### Common Pitfalls

- **`baseUrl` must be relative**: Setting `VITE_API_BASE_URL` to an absolute URL bypasses the Vite proxy and the session cookie won't be sent cross-origin.
- **Don't read `import.meta.env` outside `src/lib/api/` or `src/lib/config/`**: Centralize env var access for testability.
- **Pages are thin shells**: Business logic belongs in feature hooks/components, not in page components.
