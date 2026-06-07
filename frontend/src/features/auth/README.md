# Auth Feature Module

> User authentication and session management for the ACMG Lingua frontend. Handles login, registration, token persistence, and auth-gated navigation.

## Quick Start

```typescript
import { useAuth } from "@/features/auth";

function MyComponent() {
  const { user, isAuthenticated, login, logout, isLoggingIn } = useAuth();

  if (!isAuthenticated) {
    return <button onClick={() => login({ email: "user@example.com", password: "secret" })}>Sign In</button>;
  }

  return <button onClick={logout}>Sign Out ({user.email})</button>;
}
```

## Architecture

```
features/auth/
├── types/auth.ts           # TypeScript interfaces (LoginRequest, LoginResponse, RegisterRequest, AuthUser)
├── services/auth.ts        # API calls (currently stubbed — backend auth routes not yet implemented)
├── hooks/useAuth.ts        # Main auth hook: login/register mutations + localStorage token management
├── components/
│   ├── LoginForm.tsx       # Email/password sign-in form with toast feedback
│   └── RegisterForm.tsx    # Email/password/confirm registration form
└── index.ts                # Barrel exports
```

### Data Flow

1. User submits credentials via `LoginForm` or `RegisterForm`
2. Component calls `useAuth()` hook
3. Hook invokes `useMutation` -> `services/auth.ts`
4. On success: token stored in `localStorage`, user state updated
5. `apiClient` request interceptor reads token from `localStorage` on every API call
6. On 401 response: `apiClient` clears token and redirects to `/login`

### Token Persistence

Tokens are stored in `localStorage` under the key `access_token`. The companion key `auth_email` stores the user email for display purposes. Both are cleared on logout or 401 response.

## Public API

### `useAuth()` Hook

Primary interface for authentication. Returns the following:

| Property | Type | Description |
|----------|------|-------------|
| `user` | `AuthUser \| null` | Current authenticated user (email only) |
| `isAuthenticated` | `boolean` | Whether a valid token exists |
| `login` | `(body: LoginRequest) => Promise<LoginResponse>` | Trigger login mutation |
| `register` | `(body: RegisterRequest) => Promise<void>` | Trigger registration mutation |
| `logout` | `() => void` | Clear token and user state |
| `isLoggingIn` | `boolean` | Login mutation in progress |
| `isRegistering` | `boolean` | Registration mutation in progress |
| `loginError` | `Error \| null` | Login mutation error |
| `registerError` | `Error \| null` | Registration mutation error |

### Types

| Type | Description |
|------|-------------|
| `LoginRequest` | `{ email: string; password: string }` |
| `LoginResponse` | `{ access_token: string; token_type: string }` |
| `RegisterRequest` | `{ email: string; password: string; password_confirm: string }` |
| `AuthUser` | `{ email: string }` |

### Components

| Component | Description |
|-----------|-------------|
| `<LoginForm />` | Standalone sign-in form. Navigates to `/pipeline` on success. |
| `<RegisterForm />` | Standalone registration form. Navigates to `/login` on success. |

## Internal Design

### Service Layer (Stubbed)

The `services/auth.ts` module currently returns stub responses because the backend auth endpoints (`POST /auth/login`, `POST /auth/register`) are not yet implemented. Replace the stub functions with real `apiClient` calls once the backend is ready:

```typescript
// Current stub — replace with:
export async function login(body: LoginRequest): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>("/auth/login", body);
  return data;
}
```

### Integration with apiClient

The `apiClient` (`@/lib/api/client`) request interceptor automatically reads `localStorage.access_token` and attaches it as a Bearer token. The response interceptor handles 401 by clearing the token and redirecting to `/login`, with a guard (`isRedirectingToLogin`) to prevent duplicate navigations from concurrent failed requests.

## Usage Patterns

### Gate a component behind authentication

```typescript
import { useAuth } from "@/features/auth";
import { redirect } from "next/navigation";

function ProtectedPage() {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) redirect("/login");
  return <div>Protected content</div>;
}
```

### Show different UI based on auth state

```typescript
const { user, isAuthenticated, logout } = useAuth();

return isAuthenticated ? (
  <div>
    <span>Welcome, {user.email}</span>
    <button onClick={logout}>Sign Out</button>
  </div>
) : (
  <LoginForm />
);
```

### Handle login errors

```typescript
const { login, loginError } = useAuth();

return (
  <form onSubmit={async (e) => {
    e.preventDefault();
    try {
      await login({ email, password });
    } catch {
      // loginError is populated automatically
    }
  }}>
    {loginError && <p className="text-red-600">{loginError.message}</p>}
    ...
  </form>
);
```

## Extension Guide

### Adding social login

1. Add a new mutation in `useAuth.ts` (e.g., `socialLoginMutation`)
2. Add a service function in `services/auth.ts` calling the backend OAuth callback endpoint
3. The token storage and `apiClient` integration remain unchanged

### Adding token refresh

1. Add a `refreshToken()` function in `services/auth.ts`
2. Modify the `apiClient` response interceptor to catch 401, attempt refresh, and retry the original request before redirecting
3. Store the refresh token alongside `access_token` in `localStorage`

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `@tanstack/react-query` | ^5.50.0 | `useMutation` for login/register async operations |
| `next/navigation` | (Next.js built-in) | `useRouter` for post-auth navigation |

## Testing

Tests live in `frontend/tests/features/auth/`.

```bash
cd frontend
npm run test -- --testPathPattern=auth
```

Current test gaps:
- Service layer is stubbed; integration tests require backend auth endpoints
- Token expiry and refresh scenarios not yet covered
