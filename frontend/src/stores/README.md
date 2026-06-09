# Global State Stores

> Zustand stores for cross-cutting UI state. Feature-specific state belongs in feature hooks.

## Stores

### `appStore` — Application UI State

| Property | Type | Description |
|----------|------|-------------|
| `sidebarCollapsed` | `boolean` | Sidebar icon-only mode |
| `toggleSidebar()` | `() => void` | Toggle collapsed state |
| `setSidebarCollapsed(v)` | `(v: boolean) => void` | Set explicitly |

Used by `DashboardLayout` and `Sidebar` components.

### `toastStore` — Toast Notifications

| Property | Type | Description |
|----------|------|-------------|
| `toasts` | `Toast[]` | Current toast queue |
| `addToast(toast)` | `(toast: Omit<Toast, "id">) => void` | Push a toast (auto-removes after `ttl`) |
| `removeToast(id)` | `(id: string) => void` | Manually dismiss |

```typescript
// Toast shape
{ id, level: "info"|"success"|"warning"|"error", title, message?, ttl? }  // default ttl: 4000ms
```

Rendered globally by `<NotificationToast />` in the root layout.

## When NOT to Use

- Feature-specific data -> feature hooks / TanStack Query.
- Form state -> `useState` / `useReducer`.
- Server state -> TanStack Query.
