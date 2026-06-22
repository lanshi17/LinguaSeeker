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

## When NOT to Use

- Feature-specific data -> feature hooks / TanStack Query.
- Form state -> `useState` / `useReducer`.
- Server state -> TanStack Query.
- Notifications -> antd `App.useApp()` message/notification API.
