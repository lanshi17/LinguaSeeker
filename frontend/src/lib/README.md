# Shared Library (`src/lib/`)

> Infrastructure utilities shared across all feature modules.

## Modules

### `lib/api/` -- API Client

- **`client.ts`**: Shared Axios instance used by every feature service layer. Base URL from `VITE_API_BASE_URL` (default `{BASE_URL}api/v1`), 30s timeout. Response interceptor normalizes errors into `ApiError`. Supports subpath mount (e.g., `/linguaseeker/api/v1`).
- **`error.ts`**: `ApiError` class with `status` and `backendMessage`. `normalizeError()` converts Axios errors. `extractErrorMessage()` provides duck-typed error message extraction for UI display.

| Export | Type | Description |
|--------|------|-------------|
| `apiClient` | `AxiosInstance` | Pre-configured Axios instance with error normalization interceptor |
| `ApiError` | `class extends Error` | Normalized error: `status` (0 for network), `backendMessage` |
| `normalizeError` | `(AxiosError) => ApiError` | Converts Axios errors; network failures get status 0 |
| `extractErrorMessage` | `(err: unknown, fallback?) => string` | Extracts human-readable message from any error type |

### `lib/hooks/` -- Shared Hooks

| Hook | Signature | Description |
|------|-----------|-------------|
| `useElapsedSeconds` | `(start: string \| null) => number` | Returns seconds elapsed since an ISO timestamp. Updates every 250ms for visible ticking. Returns 0 when start is null. |

### `lib/types/` -- Shared Types

- **`common.ts`**: `ProcessingStatus` (`"pending" \| "running" \| "completed" \| "failed" \| "skipped"`) and `PhaseId` (`"phase_1" \| "phase_2" \| "phase_3"`).

### `lib/utils/` -- Utilities

- **`format.ts`**: Formatting helpers for durations and timestamps.

| Function | Signature | Description |
|----------|-----------|-------------|
| `formatDuration` | `(totalSeconds?) => string` | Formats seconds as `"Xms"`, `"Xs"`, `"Xm XXs"`, or `"Xh XXm"` |
| `formatRelative` | `(iso?, now?) => string` | Relative time: `"just now"`, `"Xs ago"`, `"Xm ago"`, `"Xh ago"`, `"Xd ago"` |
| `formatTimestamp` | `(iso?) => string` | Absolute time: locale-formatted `YYYY/MM/DD HH:MM:SS` |
