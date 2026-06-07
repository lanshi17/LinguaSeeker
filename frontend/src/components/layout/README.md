# Layout Components

> Application shell components that provide the dashboard structure: sidebar navigation, top bar with backend connectivity status, and page header.

## Components

### DashboardLayout

Main application shell. Wraps all authenticated pages with a sidebar, top bar, and scrollable content area.

```typescript
import { DashboardLayout } from "@/components/layout/DashboardLayout";

<DashboardLayout>
  <YourPageContent />
</DashboardLayout>
```

**Structure:**
```
┌─────────────────────────────────────────────┐
│ Sidebar │ Top Bar (hamburger + conn status) │
│         ├─────────────────────────────────── │
│  Nav    │                                   │
│  Items  │  Main Content (scrollable)        │
│         │  max-w-7xl, p-6                   │
│         │                                   │
└─────────┴───────────────────────────────────┘
```

- Sidebar is collapsible via the hamburger button (top-left)
- `useAppStore` manages sidebar collapsed state
- Content area has `max-w-7xl` constraint for readability

### Sidebar

Collapsible navigation sidebar with route-aware active states.

```typescript
import { Sidebar } from "@/components/layout/Sidebar";
```

**Navigation items** (defined in `NAV_ITEMS`):

| Label | Route | Icon |
|-------|-------|------|
| Pipeline | `/pipeline` | `Workflow` |
| Evidence | `/evidence` | `Search` |
| AI Chat | `/chat` | `MessageSquare` |

**Active state detection:**
- Exact match: `pathname === item.href`
- Prefix match: `pathname.startsWith(item.href + "/")` (e.g., `/pipeline/run-123` activates Pipeline)

**Collapsed state:**
- Width shrinks from `w-60` to `w-16`
- Labels hidden, only icons visible
- Brand text fades out
- Transition: 200ms width animation

### ConnectionStatus

Backend connectivity indicator. Polls `GET /health` every 30s and shows a colored dot with tooltip.

```typescript
import { ConnectionStatus } from "@/components/layout/ConnectionStatus";
```

| Status | Dot | Pulse | Tooltip |
|--------|-----|-------|---------|
| `connected` | Green | Yes | "Backend connected" + latency |
| `disconnected` | Red | Yes | "Backend disconnected" |
| `checking` | Gray | No | "Checking connection…" |

**Tooltip details:**
- Latency in ms (e.g., "Latency: 42ms")
- Time since last check (e.g., "Checked: 5s ago")
- Shown on hover

### PageHeader

Page title and description with optional action buttons.

```typescript
import { PageHeader } from "@/components/layout/PageHeader";

<PageHeader
  title="Evidence Search"
  description="Search evidence cards by gene, variant, disease, or PMID."
  actions={<Button>Export</Button>}
/>
```

| Prop | Type | Description |
|------|------|-------------|
| `title` | `string` | Page title (h1, 2xl font) |
| `description` | `string` | Subtitle (sm, gray) |
| `actions` | `ReactNode` | Right-aligned action buttons |

## Usage Patterns

### Dashboard group layout

All routes under `app/(dashboard)/` automatically use `DashboardLayout` via the group layout file:

```typescript
// app/(dashboard)/layout.tsx
import { DashboardLayout } from "@/components/layout/DashboardLayout";

export default function Layout({ children }) {
  return <DashboardLayout>{children}</DashboardLayout>;
}
```

### Adding a new nav item

1. Import the icon from `lucide-react`
2. Add to `NAV_ITEMS` in `Sidebar.tsx`:

```typescript
const NAV_ITEMS: NavItem[] = [
  { label: "Pipeline", href: "/pipeline", icon: Workflow },
  { label: "Evidence", href: "/evidence", icon: Search },
  { label: "AI Chat", href: "/chat", icon: MessageSquare },
  { label: "New Feature", href: "/new-feature", icon: NewIcon }, // Add here
];
```

3. Create the route: `app/(dashboard)/new-feature/page.tsx`

## Internal Design

### Sidebar State Management

Sidebar collapsed state is stored in `useAppStore` (Zustand):

```typescript
const collapsed = useAppStore((s) => s.sidebarCollapsed);
const toggleSidebar = useAppStore((s) => s.toggleSidebar);
```

This keeps the state global but lightweight — no need for React Context or prop drilling.

### Backend Health Polling

`ConnectionStatus` uses `useBackendHealth` from `@/lib/hooks`, which:
- Polls `GET /health` every 30s (configurable via `NEXT_PUBLIC_HEALTH_POLL_INTERVAL`)
- Measures latency via `Date.now()` before/after request
- Returns `connected`, `disconnected`, or `checking` status
- Uses TanStack Query with `retry: false` and `staleTime` just below the poll interval

## Extension Guide

### Adding a user menu

Add a user avatar + dropdown to the top-right of `DashboardLayout`:

```typescript
<header className="...">
  <button onClick={toggleSidebar}>...</button>
  <div className="flex items-center gap-4">
    <ConnectionStatus />
    <UserMenu /> {/* Add here */}
  </div>
</header>
```

### Adding breadcrumbs

For deeply nested routes, add a `<Breadcrumbs>` component below the top bar:

```typescript
<header>...</header>
<Breadcrumbs items={[{ label: "Pipeline", href: "/pipeline" }, { label: runId }]} />
<main>...</main>
```

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `lucide-react` | ^1.17.0 | Navigation icons |
| `next/link` | (Next.js built-in) | Client-side navigation |
| `next/navigation` | (Next.js built-in) | `usePathname` for active state detection |
| `zustand` | ^4.5.0 | `useAppStore` for sidebar state |

## Testing

```bash
cd frontend
npm run test -- --testPathPattern=components/layout
```
