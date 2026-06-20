# Shared Library (`src/lib/`)

> Infrastructure utilities shared across all feature modules.

## Modules

### `lib/api/` — API Client

- **`client.ts`**: Axios instance. Base URL `/api/v1`, 30s timeout. Response interceptor normalizes errors into `ApiError`. Auth is handled by the backend via session cookie; no client-side token management.
- **`error.ts`**: `ApiError` class with `status`, `backendMessage`. `normalizeError()` converts Axios errors.

### `lib/config/` — Configuration

Typed singletons from `VITE_*` env vars. Never read `import.meta.env` outside this module.

| Export | Key Fields |
|--------|------------|
| `appConfig` | `name`, `version`, `environment`, `debug` |
| `apiConfig` | `baseUrl`, `timeout`, `healthEndpoint`, `healthPollInterval` |
| `featureFlags` | `enableChat`, `enableGraph` |

### `lib/utils/` — Utilities

- **`cn.ts`**: `clsx` + `tailwind-merge` for class name composition with conflict resolution.

### `lib/types/` — Shared Types

- **`common.ts`**: `ProcessingStatus`, `PhaseId`, `PaginatedResponse<T>`, `ApiErrorResponse`.

### `lib/hooks/` — Shared Hooks

| Hook | Description |
|------|-------------|
| `useDebounce<T>(value, delay)` | Debounces a value by the given delay (ms) |
| `useBackendHealth()` | Polls `GET /health` every 30s; returns `status`, `latencyMs`, `lastChecked` |
| `usePolling(key, fn, opts)` | Generic TanStack Query polling wrapper with configurable interval |
