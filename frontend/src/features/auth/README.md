# Auth Feature

> Public-default account controls for switching between the shared public workspace and personal username accounts.

## Quick Start

```tsx
import { AccountControl } from "@/features/auth";

export function HeaderActions() {
  return <AccountControl />;
}
```

`AccountControl` calls `/auth/me` on mount, shows the current account in the dashboard header, and opens login/logout actions. The login action also creates the account when the username is new.

## Architecture

```text
AccountControl
  -> useAuthAccount()
     -> getAuthMe()
        -> apiClient GET /auth/me
  -> login/logout mutations
     -> apiClient POST /auth/*
     -> resetAccountScopedQueries(queryClient, account)
```

The backend treats `owner_user_id = null` as the public scope and a UUID as a personal account scope. The frontend mirrors that by clearing React Query state whenever the account changes, then seeding `["auth", "me"]` with the new account.

## Public API

### Components

| Export | Signature | Description |
| --- | --- | --- |
| `AccountControl` | `function AccountControl()` | Header account dropdown plus username/password login-or-create modal. |

### Hooks

| Export | Signature | Description |
| --- | --- | --- |
| `useAuthAccount` | `function useAuthAccount()` | React Query hook for `GET /auth/me`, initialized to the public account. |
| `resetAccountScopedQueries` | `function resetAccountScopedQueries(queryClient: QueryClient, account: AuthAccount): void` | Clears query cache on account switch and restores the current auth query. |

### Services

| Export | Signature | Description |
| --- | --- | --- |
| `getAuthMe` | `async function getAuthMe(): Promise<AuthAccount>` | Loads the current public or personal account. |
| `login` | `async function login(body: LoginRequest): Promise<AuthResponse>` | Logs in with username/password, creating the account if the username is new. |
| `logout` | `async function logout(): Promise<LogoutResponse>` | Clears the session cookie server-side. |

### Types

| Type | Shape | Description |
| --- | --- | --- |
| `AuthAccount` | `{ authenticated, account_type, user_id, username, display_name }` | Current account returned by `/auth/me`. |
| `LoginRequest` | `{ username: string; password: string }` | Username login-or-create request. |

## Internal Design

- `apiClient` uses `withCredentials: true` so the signed `ce_session` cookie is sent through the Vite proxy and same-origin deployments.
- `apiClient` no longer sends a global `X-API-Key`; that header maps to the public backend scope and would override a personal session cookie.
- `/auth/*` is excluded from the Axios response cache, and account-changing mutations clear cached GET responses through the shared adapter mutation behavior.
- `resetAccountScopedQueries()` calls `queryClient.clear()` to prevent public/personal task, evidence, chat, audit, and annotation data from remaining visible after an account switch.

## Usage Patterns

```tsx
import { useAuthAccount } from "@/features/auth";

export function AccountBadge() {
  const { data: account } = useAuthAccount();
  return <span>{account.account_type === "user" ? account.username : "Public"}</span>;
}
```

```tsx
import { login } from "@/features/auth/services/auth";

await login({
  username: "clinician",
  password: "correct horse battery staple",
});
```

## Extension Guide

- Add new account fields in `types/auth.ts`, then update `AccountControl` display logic and backend `AuthMeResponse` together.
- If a new feature stores account-scoped data in React Query, no extra invalidation hook is needed because account switching clears the whole query cache.
- If a new auth endpoint is added, keep it under `/auth` so the response-cache bypass rule continues to apply.

## Dependencies

| Dependency | Purpose |
| --- | --- |
| `antd` | Dropdown, modal, form, inputs, messages. |
| `@tanstack/react-query` | `/auth/me` query and login/logout mutations. |
| `lucide-react` | Header and menu icons. |
| `axios` | Shared API client through `apiClient`. |

## Testing

Run focused auth/cache tests:

```bash
cd frontend
bun run test tests/features/auth/authService.test.tsx tests/api/responseCache.test.tsx
```

Run type and lint checks:

```bash
cd frontend
bun run type-check
bun run lint
```
