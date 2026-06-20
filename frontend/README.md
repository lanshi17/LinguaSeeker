# Frontend — CrossEvidence

> Vite + React 18 SPA for medical genetics evidence extraction, built with a feature-sliced architecture: thin page shells, self-contained feature modules, and shared infrastructure.

## Quick Start

```bash
cd frontend
bun install           # install dependencies (bun.lock)
bun run dev           # Vite dev server on :3000 (proxies /api/v1 → :8000)
bun run build         # tsc --noEmit && vite build → dist/
bun run test          # vitest run (54 tests across 7 files)
```

The backend must be running on `:8000` for API calls.

## Architecture

```
index.html
  └─ src/main.tsx                    # Entry: BrowserRouter + QueryProvider + App
       └─ src/App.tsx                 # Route table (React Router v7)
            └─ <DashboardLayout>      # Dashboard routes (open access, no login)
                 ├─ /chat, /chat/:sessionId
                 ├─ /evidence, /evidence/detail
                 ├─ /evidence-db
                 └─ /pipeline, /pipeline/:runId
```

```
src/
├── main.tsx              # Vite entry — mounts React root
├── App.tsx               # All routes in one file
├── providers.tsx         # QueryClientProvider (React Query)
├── globals.css           # Tailwind directives + custom animations
├── components/           # Shared UI + layout (cross-feature)
│   ├── layout/           # DashboardLayout, Sidebar, PageHeader, ConnectionStatus
│   └── ui/               # Button, Card, Input, Modal, Toast, Badge, Spinner, ...
├── features/             # Vertical feature slices (self-contained)
│   ├── chat/             # ChatView, SSE streaming, chat sessions
│   ├── evidence-search/  # Evidence search, detail, bilingual comparison
│   ├── evidence-db/      # Variant index, variant detail, bilingual evidence
│   └── pipeline/         # Pipeline submit, status, phase timeline, run history
├── pages/                # Route-level page components (thin shells)
│   ├── ChatPage.tsx
│   ├── ChatSessionPage.tsx
│   ├── EvidencePage.tsx
│   ├── EvidenceDetailPage.tsx
│   ├── EvidenceDbPage.tsx
│   ├── PipelinePage.tsx
│   └── PipelineRunPage.tsx
├── lib/                  # Shared infrastructure
│   ├── api/              # apiClient (Axios), ApiError, normalizeError
│   ├── config/           # Typed env var singletons (appConfig, apiConfig)
│   ├── hooks/            # useBackendHealth, usePolling, useDebounce, useElapsedSeconds
│   ├── types/            # ProcessingStatus, PaginatedResponse, ApiErrorResponse
│   └── utils/            # cn (clsx + tailwind-merge), format
└── stores/               # Zustand stores (appStore, toastStore)
```

### Request Flow

```
Component → feature hook (useQuery/useMutation)
  → feature service (axios call via apiClient)
    → Vite proxy (/api/v1/* → http://localhost:8000)
      → FastAPI backend (session cookie or X-API-Key auth)
        → Response
  ← React Query cache → component re-render
```

### Auth

This is an open-access research tool — no login is required. The frontend has no
authentication guard; all routes are publicly accessible. The backend's
`require_api_key` dependency is disabled (returns `None`) when no `API_KEY`
environment variable is set, so all API routes are open. Set `API_KEY` on the
backend to optionally re-enable API-key/session-cookie auth.

## Public API

### Feature Exports

Each feature exposes its public API through a barrel `index.ts`:

| Feature | Key Exports |
|---------|-------------|
| `@/features/chat` | `ChatView`, `useChatSessions`, `createAcmgChatProvider`, `sendChatMessage` |
| `@/features/evidence-search` | `EvidenceSearchView`, `EvidenceDetailView`, `BilingualComparison`, `useEvidenceSearch`, `useEvidenceGroupDetail` |
| `@/features/evidence-db` | `VariantIndexView`, `VariantDetailView`, `BilingualEvidenceView` |
| `@/features/pipeline` | `PipelineSubmitForm`, `PipelineStatusView`, `PhaseTimeline`, `RunHistory`, `usePipelineRun`, `usePipelineStatus`, `usePipelineRuns` |

### Shared Hooks (`@/lib/hooks`)

| Hook | Signature | Description |
|------|-----------|-------------|
| `useBackendHealth` | `() => BackendHealth` | Polls `GET /health` at configurable interval; returns `status`, `latencyMs`, `lastChecked` |
| `usePolling<T>` | `(key: string[], fn: () => Promise<T>, opts?) => UseQueryResult<T>` | Generic TanStack Query polling wrapper with `refetchInterval` |
| `useDebounce<T>` | `(value: T, delay: number) => T` | Debounces a value by the given delay (ms) |
| `useElapsedSeconds` | `(startTs: number \| null) => number` | Returns elapsed seconds since a timestamp, updating every second |

### Zustand Stores (`@/stores`)

| Store | Key State | Description |
|-------|-----------|-------------|
| `useAppStore` | `sidebarCollapsed`, `toggleSidebar()` | Global UI state (sidebar collapse) |
| `useToastStore` | `toasts[]`, `addToast()`, `removeToast()` | Global toast notifications; `<NotificationToast />` renders them |

### API Client (`@/lib/api`)

| Export | Signature | Description |
|--------|-----------|-------------|
| `apiClient` | `AxiosInstance` | Pre-configured Axios instance: baseURL from config, 30s timeout, error normalization via `normalizeError` |
| `ApiError` | `class extends Error` | Normalized error with `status: number` and `backendMessage: string` |
| `normalizeError` | `(err: AxiosError) => ApiError` | Converts Axios errors to ApiError (network failures get status 0) |
| `extractErrorMessage` | `(err: unknown, fallback?) => string` | Duck-typed error message extraction for UI display |

### Config Singletons (`@/lib/config`)

| Export | Type | Description |
|--------|------|-------------|
| `appConfig` | `AppConfig` | `name`, `version`, `environment`, `debug` — from `VITE_APP_*` env vars |
| `apiConfig` | `ApiConfig` | `baseUrl`, `timeout`, `healthEndpoint`, `healthPollInterval` — from `VITE_API_*` env vars |
| `featureFlags` | `FeatureFlags` | `enableChat`, `enableGraph` — from `VITE_ENABLE_*` env vars |

## Internal Design

### Routing (React Router v7)

All routes are defined in `src/App.tsx` and nested under a single `<DashboardLayout>` wrapper (open access, no auth guard):

```tsx
<Route element={<DashboardLayout />}>
  <Route path="/chat" element={<ChatPage />} />
  <Route path="/chat/:sessionId" element={<ChatSessionPage />} />
  ...
</Route>
```

`DashboardLayout` renders the sidebar, topbar, and `<Outlet />` for nested route content. Dynamic segments (`:sessionId`, `:runId`) are accessed via `useParams`. Query parameters (`?groupId=...`) are accessed via `useSearchParams`.

### API Client Interceptors

The shared Axios instance (`apiClient`) has a single response interceptor that normalizes all errors into `ApiError` via `normalizeError()`. No request-side token injection or 401 redirect is performed — auth is delegated to the backend.

### Feature Slice Pattern

Each feature in `src/features/` follows the same structure:

```
features/<name>/
├── index.ts           # Barrel: public exports
├── components/         # React components
├── hooks/              # React Query hooks (useQuery, useMutation)
├── services/           # API call functions (axios via apiClient)
├── types/              # TypeScript types
└── utils/              # Feature-specific utilities (optional)
```

Hooks wrap React Query's `useQuery`/`useMutation` and call service functions. Components consume hooks and render UI. Pages in `src/pages/` are thin shells that compose feature components.

### State Management

- **Server state**: React Query (TanStack Query) with `staleTime: 30s`, `retry: 1`, `refetchOnWindowFocus: false` (set in `QueryProvider`).
- **Global UI state**: Zustand stores (`appStore` for sidebar, `toastStore` for notifications).

### Styling

Tailwind CSS 3.4 with a custom design system (medical teal primary, health green success, pathogenicity color scale). Class names are composed via `cn()` (clsx + tailwind-merge). Custom animations (fadeIn, slideInRight, shimmer, thinkingBounce, chatCursorBlink) are defined in `src/globals.css`.

## Usage Patterns

### Adding a New Feature Page

```tsx
// 1. Create the page component in src/pages/MyFeaturePage.tsx
import { MyFeatureView } from "@/features/my-feature";

export function MyFeaturePage() {
  return (
    <div className="space-y-6">
      <MyFeatureView />
    </div>
  );
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

### Using React Query in a Feature Hook

```typescript
// features/my-feature/hooks/useMyFeature.ts
import { useQuery } from "@tanstack/react-query";
import { fetchMyFeature } from "../services/myFeatureApi";

export function useMyFeature(id: string) {
  return useQuery({
    queryKey: ["my-feature", id],
    queryFn: () => fetchMyFeature(id),
    enabled: !!id,
  });
}
```

### Showing a Toast Notification

```tsx
import { useToastStore } from "@/stores/toastStore";

function MyComponent() {
  const addToast = useToastStore((s) => s.addToast);

  function handleSuccess() {
    addToast({ level: "success", title: "Saved", message: "Changes applied." });
  }

  function handleError() {
    addToast({ level: "error", title: "Failed", ttl: 8000 });
  }
}
```

### Navigating Programmatically

```tsx
import { useNavigate } from "react-router-dom";

function MyComponent() {
  const navigate = useNavigate();

  function handleSubmit(id: string) {
    navigate(`/my-feature/${id}`);
  }
}
```

## Extension Guide

### Adding a New Feature Slice

1. Create `src/features/<name>/` with `index.ts`, `components/`, `hooks/`, `services/`, `types/`.
2. Export all public symbols from `index.ts` (barrel pattern).
3. Use `apiClient` from `@/lib/api/client` in service functions — never create a new Axios instance.
4. Wrap API calls in React Query hooks, not in components directly.
5. Create a page component in `src/pages/` and add a route in `src/App.tsx`.

### Auth

Open access by default — no `API_KEY` configured. To optionally re-enable API-key
auth on the backend, set the `API_KEY` environment variable; the backend's
`require_api_key` dependency then enforces an `X-API-Key` header or signed
`ce_session` cookie on all routes. The frontend ships no login UI (removed in
favor of open access); re-adding a login page would require restoring an
`features/auth` slice and an `AuthGuard` wrapper.

### Common Pitfalls

- **`baseUrl` must be relative**: Setting `VITE_API_BASE_URL` to an absolute URL bypasses the Vite proxy and the session cookie won't be sent cross-origin.
- **Don't read `import.meta.env` outside `src/lib/config/`**: All env var access is centralized in the config module for testability.
- **Use `cn()` for class composition**: Never concatenate class strings manually — `tailwind-merge` in `cn()` resolves conflicts (e.g., `px-4` vs `px-2`).
- **Pages are thin shells**: Business logic belongs in feature hooks/components, not in page components.

## Performance Notes

- **Bundle size**: The production build is ~1.2 MB (377 KB gzipped). The main bottleneck is antd + @ant-design/x. Consider lazy-loading heavy feature routes with `React.lazy()` if initial load time becomes an issue.
- **React Query staleTime**: Default 30s. Polling hooks (`useBackendHealth`, `usePipelineStatus`) use their own intervals. Adjust per-query if data freshness requirements differ.
- **SSE streaming**: Chat uses Server-Sent Events via `EventSource`. The backend sends 15-second keepalive heartbeats to prevent proxy timeouts.
- **Vite dev server proxy**: Development proxies `/api/v1` and `/health` to `:8000`. No CORS issues in dev. In production, Nginx handles the reverse proxy.

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `react` / `react-dom` | ^18.3.0 | UI framework |
| `react-router-dom` | ^7.0.0 | Client-side routing |
| `vite` | ^6.0.0 | Build tool + dev server |
| `@vitejs/plugin-react` | ^4.3.0 | React Fast Refresh + JSX transform |
| `antd` | ^6.4.3 | UI component library |
| `@ant-design/icons` | ^6.2.5 | Icon set for antd |
| `@ant-design/x` / `x-sdk` | ^2.7.0 | AI chat components (used by chat feature) |
| `@tanstack/react-query` | ^5.50.0 | Server state management (caching, polling, mutations) |
| `axios` | ^1.7.0 | HTTP client |
| `zustand` | ^4.5.0 | Lightweight global state (sidebar, toasts) |
| `tailwindcss` | ^3.4.0 | Utility-first CSS framework |
| `clsx` + `tailwind-merge` | ^2.1.0 / ^3.6.0 | Class name composition with conflict resolution |
| `lucide-react` | ^1.17.0 | Icon set (layout, evidence, pipeline UI) |
| `react-markdown` | ^10.1.0 | Markdown rendering (evidence documents) |
| `vitest` | ^4.1.8 | Test runner (jsdom environment) |
| `@testing-library/react` | ^16.3.2 | Component testing utilities |

## Testing

```bash
bun run test          # vitest run — 54 tests across 7 files
bun run test:node     # tsc + node --test (for pure-logic tests without React)
bun run type-check    # tsc --noEmit — TypeScript type checking
bun run lint          # eslint . — ESLint with react-hooks + react-refresh plugins
```

Test files live in `frontend/tests/` and mirror the source structure:

```
tests/
├── features/
│   └── chat/                    # Chat feature tests
├── evidence-search/
│   ├── BilingualComparison.test.tsx
│   ├── EvidenceHighlightText.test.tsx
│   └── literatureRows.test.ts   # Pure logic: row building, evidence ID finding
└── config/
    └── layeredConfig.test.ts    # Config singleton behavior
```

Tests use Vitest with jsdom environment. React Query is tested via `@testing-library/react`. Pure logic utilities (e.g., `literatureRows`, `evidenceDocument`) are tested without React rendering.

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
| `VITE_APP_NAME` | `Cross Evidence` | Application display name |
| `VITE_APP_VERSION` | `0.0.0` | Semantic version |
| `VITE_API_BASE_URL` | `/api/v1` | API base URL (must be relative for proxy) |
| `VITE_API_TIMEOUT` | `30000` | Request timeout in ms |
| `VITE_HEALTH_ENDPOINT` | `/health` | Backend health check endpoint |
| `VITE_HEALTH_POLL_INTERVAL` | `30000` | Health poll interval in ms |
| `VITE_ENABLE_CHAT` | `true` | Feature flag: chat |
| `VITE_ENABLE_GRAPH` | `true` | Feature flag: graph explorer |
| `VITE_DEBUG` | `false` | Enable verbose frontend behavior |
