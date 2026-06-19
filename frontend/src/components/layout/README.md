# Layout Components

> Application shell components: sidebar, top bar, page header.

## Components

### DashboardLayout

Main shell wrapping all `(dashboard)` routes. Responsive layout with:
- **Desktop**: sidebar + top bar (h-14) + scrollable main content (`max-w-7xl`, responsive padding `p-4 md:p-6`).
- **Mobile**: hamburger menu opens a sidebar overlay (`w-60`) with backdrop. Desktop collapse toggle hides inline sidebar.
- Sidebar state persisted in `useAppStore` (`sidebarCollapsed`).

### Sidebar

Collapsible navigation with route-aware active states. Accepts `mobile` prop (always expanded when mobile overlay) and `onNavigate` callback. Width: `w-60` (expanded) / `w-16` (collapsed).

| Label | Route | Icon |
|-------|-------|------|
| AI Chat | `/chat` | `MessageSquare` |
| Evidence | `/evidence` | `Search` |

Active detection: exact match or prefix match (e.g., `/evidence/detail` activates Evidence). Footer shows "Cross Evidencev0.1.0" when expanded.

### ConnectionStatus

Backend health indicator. Polls `GET /health` every 30s via `useBackendHealth`. Clickable status dot toggles a tooltip showing latency and relative last-checked time.

| Status | Dot | Tooltip |
|--------|-----|---------|
| connected | Green (pulse) | "Backend connected" + latency + "Xs/Xm ago" |
| disconnected | Red (pulse) | "Backend disconnected" + latency + "Xs/Xm ago" |
| checking | Gray | "Checking connection..." |

### PageHeader

Page title (`h1`), optional description (`p`), and right-aligned `actions` slot. Accepts `className` for external overrides.

## Adding a Nav Item

Import icon from `lucide-react`, add to `NAV_ITEMS` in `Sidebar.tsx`, create the route page.
