# Frontend Config

> Typed access to layered Vite environment settings for app, API, and feature flags.

## Quick Start

```ts
import { apiConfig, appConfig, featureFlags } from "@/lib/config";

console.log(appConfig.name);
console.log(apiConfig.baseUrl);
if (featureFlags.enableChat) {
  // render chat UI
}
```

## Architecture

```text
.env files -> Vite env loader -> import.meta.env -> typed config singletons
                                           |
                                           +-> appConfig
                                           +-> apiConfig
                                           +-> featureFlags
```

The module keeps raw `import.meta.env` reads in one place and exposes typed objects to the rest of the frontend. This makes API clients, hooks, and feature gates consume the same source of truth.

## Public API

### `appConfig`

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | Application display name. |
| `version` | `string` | Semantic version string. |
| `environment` | `"development" \| "production"` | Derived from `NODE_ENV`. |
| `debug` | `boolean` | Enables verbose frontend behavior. |

### `featureFlags`

| Field | Type | Description |
|-------|------|-------------|
| `enableChat` | `boolean` | Toggles chat and SSE streaming UI. |
| `enableGraph` | `boolean` | Toggles knowledge graph UI. |

### `apiConfig`

| Field | Type | Description |
|-------|------|-------------|
| `baseUrl` | `string` | API base path or absolute URL. In production, MUST be relative (e.g. `/api/v1`) so requests pass through `middleware.ts` which injects `X-API-Key`. Absolute URLs in production trigger a console warning. |
| `timeout` | `number` | Shared request timeout in milliseconds (default 30 000). |
| `healthEndpoint` | `string` | Backend health check path (default `/health`). |
| `healthPollInterval` | `number` | React Query polling interval in milliseconds (default 30 000). |

### `AppConfig`, `ApiConfig`, `FeatureFlags`

TypeScript interfaces exported for consumers that need to type local helpers or tests.

## Internal Design

- `app.ts` reads app metadata and feature toggles.
- `api.ts` reads API connection settings.
- `index.ts` re-exports the typed singletons and interfaces.
- `types.ts` defines the shared contract and documents the expected env mapping.

The module intentionally avoids a factory function. These values are static for a given client session and are cheap to read once at module load.

## Usage Patterns

### API client

```ts
import { apiConfig } from "@/lib/config";
import axios from "axios";

export const client = axios.create({
  baseURL: apiConfig.baseUrl,
  timeout: apiConfig.timeout,
});
```

### Health polling

```ts
import { apiConfig } from "@/lib/config";

const interval = apiConfig.healthPollInterval;
const endpoint = apiConfig.healthEndpoint;
```

### Feature gating

```ts
import { featureFlags } from "@/lib/config";

if (featureFlags.enableChat) {
  // mount chat experience
}
```

## Extension Guide

- Add a new env-backed value in `types.ts`.
- Read it in `app.ts` or `api.ts` depending on scope.
- Re-export it from `index.ts`.
- Consume it from UI or service code instead of reading `process.env` directly.

Avoid expanding this module into a generic config framework. It is meant to be a thin typed boundary over Next.js env loading.

## Dependencies

| Dependency | Purpose |
|------------|---------|
| Next.js env loader | Loads `.env`, `.env.development`, `.env.production`, `.env.local` automatically. |
| TypeScript | Enforces the config contract. |
| React Query / Axios consumers | Use `apiConfig` for shared network settings. |

## Testing

- `bun run type-check`
- `bun run lint`
- `bun run test`

The current test coverage checks that:

- `apiClient` consumes `apiConfig.baseUrl` and `apiConfig.timeout`
- `import.meta.env.VITE_*` reads stay inside `src/lib/config/`
