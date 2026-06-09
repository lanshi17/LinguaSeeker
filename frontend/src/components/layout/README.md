# Layout Components

> Application shell components: sidebar, top bar, page header.

## Components

### DashboardLayout

Main shell wrapping all `(dashboard)` routes: sidebar, top bar, scrollable content (`max-w-7xl`, `p-6`). Sidebar collapsible via hamburger button; state in `useAppStore`.

### Sidebar

Collapsible navigation with route-aware active states. Width: `w-60` (expanded) / `w-16` (collapsed).

| Label | Route | Icon |
|-------|-------|------|
| Pipeline | `/pipeline` | `Workflow` |
| Evidence | `/evidence` | `Search` |
| AI Chat | `/chat` | `MessageSquare` |

Active detection: exact match or prefix match (e.g., `/pipeline/run-123` activates Pipeline).

### ConnectionStatus

Backend health indicator. Polls `GET /health` every 30s via `useBackendHealth`.

| Status | Dot | Tooltip |
|--------|-----|---------|
| connected | Green (pulse) | "Backend connected" + latency |
| disconnected | Red (pulse) | "Backend disconnected" |
| checking | Gray | "Checking connection..." |

### PageHeader

Page title and optional description + right-aligned action buttons.

## Adding a Nav Item

Import icon from `lucide-react`, add to `NAV_ITEMS` in `Sidebar.tsx`, create the route page.
