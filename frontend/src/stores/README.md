# Global State Stores

> Zustand stores for cross-cutting application state. Feature-specific state belongs in feature-local hooks; these stores are reserved for truly global UI state that cannot be scoped to a single component or feature.

## Stores

### `appStore` — Application UI State

Minimal global state for the dashboard shell.

```typescript
import { useAppStore } from "@/stores/appStore";

function Sidebar() {
  const collapsed = useAppStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);

  return <aside className={collapsed ? "w-16" : "w-60"}>...</aside>;
}
```

| Property | Type | Description |
|----------|------|-------------|
| `sidebarCollapsed` | `boolean` | Whether the sidebar is in collapsed (icon-only) mode |
| `toggleSidebar()` | `() => void` | Toggle collapsed state |
| `setSidebarCollapsed(collapsed)` | `(collapsed: boolean) => void` | Set collapsed state explicitly |

### `toastStore` — Toast Notifications

Global notification queue. Any component can push toasts; the root layout renders them.

```typescript
import { useToastStore } from "@/stores/toastStore";

function MyComponent() {
  const addToast = useToastStore((s) => s.addToast);

  function handleSuccess() {
    addToast({ level: "success", title: "Pipeline started", ttl: 3000 });
  }

  function handleError() {
    addToast({ level: "error", title: "Failed", message: "Check your connection." });
  }
}
```

| Property | Type | Description |
|----------|------|-------------|
| `toasts` | `Toast[]` | Current toast queue |
| `addToast(toast)` | `(toast: Omit<Toast, "id">) => void` | Push a toast (auto-removes after `ttl`) |
| `removeToast(id)` | `(id: string) => void` | Manually dismiss a toast |

#### Toast Interface

```typescript
interface Toast {
  id: string;              // Auto-generated
  level: ToastLevel;       // "info" | "success" | "warning" | "error"
  title: string;           // Required heading
  message?: string;        // Optional detail
  ttl?: number;            // Auto-dismiss after ms (default 4000)
}
```

**Auto-dismiss:** Toasts with `ttl > 0` are automatically removed after the timeout. Set `ttl: 0` for persistent toasts that require manual dismissal.

## Architecture

```
Root Layout (app/layout.tsx)
  └── <NotificationToast /> ← subscribes to toastStore.toasts

Any Component
  └── useToastStore((s) => s.addToast) ← pushes to toastStore.toasts

DashboardLayout
  └── <Sidebar /> ← subscribes to appStore.sidebarCollapsed
  └── <button onClick={toggleSidebar} /> ← mutates appStore
```

### Why Zustand?

- **Lightweight**: ~1KB, no boilerplate
- **No providers**: No need to wrap the app in `<StoreProvider>`
- **Selective subscriptions**: Components re-render only when the specific slice they subscribe to changes
- **Mutable**: Direct state updates via `set()` — no reducers or dispatch

### When to Use These Stores

**Use `appStore` for:**
- Sidebar collapsed state (affects layout across all pages)

**Use `toastStore` for:**
- Global notifications that need to appear regardless of the current page
- Success/error feedback from async operations

**Do NOT use these stores for:**
- Feature-specific state (e.g., pipeline run data, search filters) — use feature-local hooks
- Form state — use React `useState` or `useReducer`
- Data fetching — use TanStack Query

## Usage Patterns

### Toast from a service function

```typescript
import { useToastStore } from "@/stores/toastStore";

// In a hook or component:
const addToast = useToastStore((s) => s.addToast);

try {
  await startPipelineRun(body);
  addToast({ level: "success", title: "Pipeline started" });
} catch (error) {
  addToast({ level: "error", title: "Failed", message: error.message });
}
```

### Toast from outside React (e.g., API interceptor)

```typescript
// lib/api/client.ts (Axios interceptor)
import { useToastStore } from "@/stores/toastStore";

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 500) {
      useToastStore.getState().addToast({
        level: "error",
        title: "Server error",
        message: "Please try again later.",
      });
    }
    return Promise.reject(error);
  }
);
```

### Persistent sidebar state

To persist sidebar collapsed state across page reloads:

```typescript
// stores/appStore.ts
export const useAppStore = create<AppState>((set) => ({
  sidebarCollapsed: typeof window !== "undefined"
    ? localStorage.getItem("sidebar_collapsed") === "true"
    : false,

  toggleSidebar: () =>
    set((state) => {
      const next = !state.sidebarCollapsed;
      localStorage.setItem("sidebar_collapsed", String(next));
      return { sidebarCollapsed: next };
    }),
}));
```

## Extension Guide

### Adding a new global store

1. Create `stores/myStore.ts`
2. Define the state interface and actions
3. Export via `create()`:

```typescript
import { create } from "zustand";

interface MyState {
  value: number;
  increment: () => void;
}

export const useMyStore = create<MyState>((set) => ({
  value: 0,
  increment: () => set((s) => ({ value: s.value + 1 })),
}));
```

4. Export from `stores/index.ts`
5. Document in this README

### Adding toast actions (undo, retry)

Extend the `Toast` interface with an optional `action` field:

```typescript
interface Toast {
  // ... existing fields
  action?: { label: string; onClick: () => void };
}
```

Update `NotificationToast` to render the action button.

## Testing

```bash
cd frontend
npm run test -- --testPathPattern=stores
```

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `zustand` | ^4.5.0 | Lightweight state management |
