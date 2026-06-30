# Layout Components

> Application shell components: sidebar, top bar, page header.

## Components

### DashboardLayout

Main shell wrapping all `(dashboard)` routes. Responsive layout with:
- **Desktop**: sidebar + top bar (h-56) + scrollable main content (`max-w-1280px`, centered).
- **Mobile**: hamburger menu opens a sidebar overlay (240px) with backdrop. Desktop collapse toggle hides inline sidebar.
- Sidebar state persisted in `useAppStore` (`sidebarCollapsed`).
- Uses `<AnimatedOutlet />` for page transition animations on route change.

### Sidebar

Collapsible navigation with route-aware active states. Accepts `mobile` prop (always expanded when mobile overlay) and `onNavigate` callback. Width: 240px (expanded) / 80px (collapsed).

| Label | Route | Icon |
|-------|-------|------|
| AI Chat | `/chat` | `MessageSquare` |
| Tasks | `/pipeline` | `ClipboardList` |
| Evidence DB | `/evidence-db` | `Database` |
| Audit | `/audit` | `ShieldCheck` |

### PageHeader

Page title (`Typography.Title` level 3), optional description, and right-aligned `actions` slot. Accepts `className` for external overrides.

| Prop | Type | Description |
|------|------|-------------|
| `title` | `string` | Page title |
| `description` | `ReactNode` | Optional subtitle |
| `actions` | `ReactNode` | Right-aligned action buttons |
| `className` | `string` | External CSS class |

## Adding a Nav Item

Import icon from `lucide-react`, add to `NAV_ITEMS` in `Sidebar.tsx`, create the route page.
