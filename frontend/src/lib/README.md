# Shared Library (`src/lib/`)

> Infrastructure utilities shared across all feature modules.

## Modules

### `lib/api/` — API Client

- **`client.ts`**: Axios instance. Base URL from `VITE_API_BASE_URL` (default `/api/v1`), 30s timeout. Response interceptor normalizes errors into `ApiError`. Vite proxy injects API key server-side.
- **`error.ts`**: `ApiError` class with `status`, `backendMessage`. `normalizeError()` converts Axios errors.

### `lib/utils/` — Utilities

- **`format.ts`**: `formatDuration()`, `formatRelative()`, `formatTimestamp()` helpers.

### `lib/types/` — Shared Types

- **`common.ts`**: `ProcessingStatus`, `PhaseId` union types.

### `lib/hooks/` — Shared Hooks

| Hook | Description |
|------|-------------|
| `useBackendHealth()` | Polls `GET /health` via React Query; returns `status`, `latencyMs`, `lastChecked` |
| `useElapsedSeconds(since)` | Returns seconds elapsed since a timestamp, updates every 250ms |
