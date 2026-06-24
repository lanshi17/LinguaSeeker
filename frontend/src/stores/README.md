# Global State Stores

> Zustand stores for cross-cutting UI state. Feature-specific state belongs in feature hooks.

## Stores

### `appStore.ts` -- Application UI State

| Property | Type | Description |
|----------|------|-------------|
| `sidebarCollapsed` | `boolean` | Whether the sidebar is in icon-only collapsed mode |
| `toggleSidebar()` | `() => void` | Toggle collapsed state |
| `setSidebarCollapsed(v)` | `(v: boolean) => void` | Set collapsed state explicitly |

Used by `DashboardLayout` (collapse toggle) and `Sidebar` (width and label rendering).

## When NOT to Use Zustand

- **Feature-specific data** -- use feature hooks with TanStack Query.
- **Form state** -- use `useState` / `useReducer` in components.
- **Server state** -- use TanStack Query (`useQuery`, `useMutation`).
- **Notifications** -- use antd `App.useApp()` `message` / `notification` API.
