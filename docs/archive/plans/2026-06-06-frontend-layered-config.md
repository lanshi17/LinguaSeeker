# Frontend Layered Configuration (Ansible Architecture)

**Date**: 2026-06-06
**Status**: Completed
**Created**: 2026-06-06
**Completed**: 2026-06-11
**PR**: merged

---

## Goal

Mirror the backend's Ansible-inspired layered config pattern for the frontend, using Next.js built-in `.env` file support with typed TypeScript wrappers.

---

## Layering (matches backend priority)

| Priority | File | Git | Purpose |
|----------|------|-----|---------|
| 1 (lowest) | `.env` | ✅ committed | Safe defaults (API base URL, feature flags) |
| 2 | `.env.development` / `.env.production` | ✅ committed | Environment-specific structural overrides |
| 3 | `.env.local` | ❌ git-ignored | Developer-local overrides + secrets |
| 4 (highest) | `.env.production.local` | ❌ git-ignored | Production secrets |

Next.js loads these automatically in this order. Later files override earlier ones.
OS environment variables (Docker, CI) always win over file-based values.

---

## Directory Structure

```
frontend/
├── .env                              # Layer 1: defaults (committed)
├── .env.development                  # Layer 2: dev overrides (committed)
├── .env.production                   # Layer 2: prod overrides (committed)
├── .env.local                        # Layer 3: local overrides (git-ignored)
├── .env.production.local             # Layer 4: prod secrets (git-ignored)
├── .env.example                      # Template for onboarding
├── src/
│   └── lib/
│       └── config/
│           ├── index.ts              # Barrel export
│           ├── app.ts                # App-level config (name, debug, env)
│           ├── api.ts                # API config (base URL, timeout, health)
│           └── types.ts              # Typed config interfaces
```

---

## Config Files Content

### `.env` (committed defaults)
```env
# ─── App ───
NEXT_PUBLIC_APP_NAME=ACMG Lingua
NEXT_PUBLIC_APP_VERSION=0.1.0

# ─── API ───
# Relative URL → goes through Next.js proxy (next.config.ts rewrites)
NEXT_PUBLIC_API_BASE_URL=/api/v1
NEXT_PUBLIC_API_TIMEOUT=30000
NEXT_PUBLIC_HEALTH_ENDPOINT=/health
NEXT_PUBLIC_HEALTH_POLL_INTERVAL=30000

# ─── Feature Flags ───
NEXT_PUBLIC_ENABLE_CHAT=true
NEXT_PUBLIC_ENABLE_GRAPH=true
```

### `.env.development` (committed dev overrides)
```env
# Dev-specific: verbose logging, faster polling
NEXT_PUBLIC_DEBUG=true
NEXT_PUBLIC_HEALTH_POLL_INTERVAL=15000
```

### `.env.production` (committed prod overrides)
```env
NEXT_PUBLIC_DEBUG=false
NEXT_PUBLIC_HEALTH_POLL_INTERVAL=60000
```

### `.env.example` (onboarding template)
```env
# Copy to .env.local and fill in values
# NEXT_PUBLIC_API_BASE_URL=/api/v1
```

### `.env.local` (git-ignored, per-developer)
```env
# Developer overrides — do NOT commit
# Only add values that differ from defaults
```

---

## Typed Config Module

### `src/lib/config/types.ts`
```typescript
export interface ApiConfig {
  baseUrl: string;
  timeout: number;
  healthEndpoint: string;
  healthPollInterval: number;
}

export interface AppConfig {
  name: string;
  version: string;
  environment: "development" | "production";
  debug: boolean;
}

export interface FeatureFlags {
  enableChat: boolean;
  enableGraph: boolean;
}
```

### `src/lib/config/app.ts`
Reads `NEXT_PUBLIC_*` vars into a typed `AppConfig` object.

### `src/lib/config/api.ts`
Reads API-related vars into a typed `ApiConfig` object. Used by `apiClient` and `useBackendHealth` instead of reading `process.env` directly.

---

## Changes Required

| File | Change |
|------|--------|
| Create `.env` | Default config values |
| Create `.env.development` | Dev overrides |
| Create `.env.production` | Prod overrides |
| Create `.env.example` | Onboarding template |
| Create `src/lib/config/types.ts` | Config type definitions |
| Create `src/lib/config/app.ts` | Typed app config accessor |
| Create `src/lib/config/api.ts` | Typed API config accessor |
| Create `src/lib/config/index.ts` | Barrel export |
| Update `src/lib/api/client.ts` | Use `apiConfig.baseUrl` instead of `process.env` |
| Update `src/lib/hooks/useBackendHealth.ts` | Use `apiConfig.healthEndpoint` and `apiConfig.healthPollInterval` |
| Update `src/components/layout/ConnectionStatus.tsx` | No change needed (uses hook) |
| Update `next.config.ts` | No change needed (rewrites stay) |
| Update `.gitignore` | Add `.env.local`, `.env.*.local` |

---

## Verification

1. `npm run type-check` — 0 errors
2. `npm run lint` — 0 warnings
3. `npm run dev` — app loads, health check uses `/health` from config
4. No `process.env.NEXT_PUBLIC_*` reads outside `src/lib/config/`
