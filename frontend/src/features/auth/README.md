# Auth Feature

> User authentication: login, registration, token persistence.

## Structure

```
features/auth/
├── components/
│   ├── LoginForm.tsx       Email/password sign-in, redirects to /pipeline on success
│   └── RegisterForm.tsx    Email/password/confirm registration, redirects to /login
├── hooks/useAuth.ts        Login/register mutations + localStorage token management
├── services/auth.ts        API calls (POST /auth/login, /auth/register)
├── types/auth.ts           LoginRequest, LoginResponse, RegisterRequest, AuthUser
└── index.ts                Barrel exports
```

## `useAuth()` Hook

| Property | Type | Description |
|----------|------|-------------|
| `user` | `AuthUser \| null` | Current user (email) |
| `isAuthenticated` | `boolean` | Valid token exists |
| `login` | `(body: LoginRequest) => Promise` | Login mutation |
| `register` | `(body: RegisterRequest) => Promise` | Registration mutation |
| `logout` | `() => void` | Clear token and user |
| `isLoggingIn` / `isRegistering` | `boolean` | Mutation progress |
| `loginError` / `registerError` | `Error \| null` | Mutation errors |

## Token Flow

1. User submits credentials via form component.
2. `useAuth()` calls service function via `useMutation`.
3. On success: token stored in `localStorage`, `apiClient` attaches it as Bearer header.
4. On 401: `apiClient` clears token and redirects to `/login`.
