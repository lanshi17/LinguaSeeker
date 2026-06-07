# Shared Library (`src/lib/`)

> Infrastructure utilities shared across all feature modules: API client, configuration, type definitions, and custom hooks. This is the foundation layer that features and components depend on.

## Modules

### `lib/api/` — API Client

Shared Axios instance with auth token injection and error normalization.

#### `apiClient` (from `lib/api/client`)

```typescript
import { apiClient } from "@/lib/api/client";

const { data } = await apiClient.get<PipelineStatusResponse>(`/pipeline/runs/${runId}/status`);
const { data } = await apiClient.post<PipelineRunResponse>("/pipeline/run", body);
```

**Configuration:**
- Base URL: `/api/v1` (hardcoded to avoid Turbopack module-caching issues with `NEXT_PUBLIC_*`)
- Timeout: 30s
- Content-Type: `application/json`

**Request interceptor:**
- Reads `localStorage.access_token` and attaches as `Authorization: Bearer <token>`

**Response interceptor:**
- On 401: clears token, redirects to `/login` (guarded against duplicate navigations)
- Normalizes all errors into `ApiError` via `normalizeError()`

#### `ApiError` (from `lib/api/error`)

```typescript
import { ApiError, normalizeError } from "@/lib/api/error";

try {
  await apiClient.get("/some-endpoint");
} catch (error) {
  if (error instanceof ApiError) {
    console.log(error.status, error.backendMessage);
  }
}
```

| Property | Type | Description |
|----------|------|-------------|
| `status` | `number` | HTTP status code (0 for network errors) |
| `backendMessage` | `string` | Original backend error message |
| `message` | `string` | Normalized error message |

---

### `lib/config/` — Configuration

Typed configuration loaded from `NEXT_PUBLIC_*` environment variables.

#### `appConfig`

```typescript
import { appConfig, featureFlags } from "@/lib/config";

console.log(appConfig.name);      // "ACMG Lingua"
console.log(appConfig.version);   // "0.1.0"
console.log(featureFlags.enableChat); // true
```

| Field | Type | Env Var | Description |
|-------|------|---------|-------------|
| `name` | `string` | `NEXT_PUBLIC_APP_NAME` | App display name |
| `version` | `string` | `NEXT_PUBLIC_APP_VERSION` | Semantic version |
| `environment` | `"development" \| "production"` | `NODE_ENV` | Current environment |
| `debug` | `boolean` | `NEXT_PUBLIC_DEBUG` | Verbose logging flag |

#### `apiConfig`

```typescript
import { apiConfig } from "@/lib/config";

console.log(apiConfig.healthPollInterval); // 30000
```

| Field | Type | Env Var | Description |
|-------|------|---------|-------------|
| `baseUrl` | `string` | `NEXT_PUBLIC_API_BASE_URL` | API base URL |
| `timeout` | `number` | `NEXT_PUBLIC_API_TIMEOUT` | Request timeout (ms) |
| `healthEndpoint` | `string` | `NEXT_PUBLIC_HEALTH_ENDPOINT` | Health check path |
| `healthPollInterval` | `number` | `NEXT_PUBLIC_HEALTH_POLL_INTERVAL` | Poll interval (ms) |

#### `featureFlags`

| Flag | Type | Env Var | Description |
|------|------|---------|-------------|
| `enableChat` | `boolean` | `NEXT_PUBLIC_ENABLE_CHAT` | Chat/SSE feature toggle |
| `enableGraph` | `boolean` | `NEXT_PUBLIC_ENABLE_GRAPH` | Knowledge graph explorer toggle |

**Important:** Never read `process.env` directly outside `lib/config/`. Always use the typed singletons.

---

### `lib/utils/` — Utilities

#### `cn()` (from `lib/utils/cn`)

Tailwind class merging with conflict resolution.

```typescript
import { cn } from "@/lib/utils/cn";

cn("px-4 py-2", isActive && "bg-primary-600", className)
// → "px-4 py-2 bg-primary-600" (with conflicts resolved)
```

Uses `clsx` for conditional joining and `tailwind-merge` for conflict resolution (e.g., `px-4` vs `px-2`).

---

### `lib/types/` — Shared Types

#### `common.ts`

| Type | Description |
|------|-------------|
| `ProcessingStatus` | `"queued" \| "running" \| "completed" \| "failed" \| "cancelled"` |
| `PhaseId` | `"phase_1" \| "phase_2" \| "phase_3"` |
| `PaginatedResponse<T>` | `{ items: T[], total: number, page: number, pageSize: number }` |
| `ApiErrorResponse` | `{ detail?, message?, status_code? }` |

---

### `lib/hooks/` — Shared Hooks

#### `useDebounce<T>(value, delay)`

Debounces a value by the given delay.

```typescript
import { useDebounce } from "@/lib/hooks/useDebounce";

const [query, setQuery] = useState("");
const debouncedQuery = useDebounce(query, 300);

useEffect(() => {
  if (debouncedQuery) search(debouncedQuery);
}, [debouncedQuery]);
```

#### `useBackendHealth()`

Polls the backend health endpoint and returns connection status.

```typescript
import { useBackendHealth } from "@/lib/hooks/useBackendHealth";

const { status, latencyMs, lastChecked } = useBackendHealth();
// status: "connected" | "disconnected" | "checking"
```

| Property | Type | Description |
|----------|------|-------------|
| `status` | `"connected" \| "disconnected" \| "checking"` | Connection state |
| `latencyMs` | `number \| null` | Last measured latency |
| `lastChecked` | `Date \| null` | Last check timestamp |

#### `usePolling<T>(queryKey, queryFn, options)`

Generic polling wrapper built on TanStack Query.

```typescript
import { usePolling } from "@/lib/hooks/usePolling";

const { data } = usePolling(
  ["my-data"],
  () => fetchData(),
  { interval: 5000 } // 5s polling
);
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `interval` | `number \| false` | `3000` | Polling interval (ms), `false` to disable |

Most features use `useQuery` with `refetchInterval` directly. This hook is for cases where a simple wrapper is cleaner.

## Architecture Diagram

```
Feature Modules
  │
  ├── features/auth
  ├── features/pipeline
  ├── features/evidence-search
  └── features/chat
          │
          ▼
    ┌─────────────┐
    │   lib/api   │ ← apiClient (Axios)
    │  lib/config │ ← appConfig, apiConfig, featureFlags
    │  lib/utils  │ ← cn()
    │  lib/types  │ ← ProcessingStatus, PhaseId, etc.
    │  lib/hooks  │ ← useDebounce, useBackendHealth, usePolling
    └─────────────┘
          │
          ▼
    Next.js Proxy (/api/v1 → backend)
```

## Usage Patterns

### Making an API call from a service function

```typescript
// features/my-feature/services/myFeature.ts
import { apiClient } from "@/lib/api/client";
import type { MyResponse } from "../types/myFeature";

export async function getMyData(id: string): Promise<MyResponse> {
  const { data } = await apiClient.get<MyResponse>(`/my-endpoint/${id}`);
  return data;
}
```

### Using configuration in a hook

```typescript
import { apiConfig } from "@/lib/config";

export function useCustomPolling() {
  return useQuery({
    queryKey: ["custom"],
    queryFn: fetchData,
    refetchInterval: apiConfig.healthPollInterval, // reuse config
  });
}
```

### Debouncing user input

```typescript
const [searchTerm, setSearchTerm] = useState("");
const debouncedSearch = useDebounce(searchTerm, 500);

useEffect(() => {
  if (debouncedSearch) {
    performSearch(debouncedSearch);
  }
}, [debouncedSearch]);
```

## Extension Guide

### Adding a new shared hook

1. Create `lib/hooks/useMyHook.ts`
2. Export the hook function
3. Use TanStack Query for data-fetching hooks, `useState`/`useEffect` for UI hooks
4. Add documentation to this README

### Adding a new config field

1. Add the `NEXT_PUBLIC_*` env var to `.env.development` and `.env.production`
2. Add the field to the appropriate interface in `lib/config/types.ts`
3. Read it in `lib/config/app.ts` or `lib/config/api.ts`
4. Export via `index.ts`

## Testing

```bash
cd frontend
npm run test -- --testPathPattern=lib
```

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `axios` | ^1.7.0 | HTTP client for `apiClient` |
| `clsx` | ^2.1.0 | Conditional class joining for `cn()` |
| `tailwind-merge` | ^3.6.0 | Tailwind conflict resolution for `cn()` |
| `@tanstack/react-query` | ^5.50.0 | Data fetching and caching for hooks |
