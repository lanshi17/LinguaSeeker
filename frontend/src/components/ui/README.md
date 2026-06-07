# UI Components

> Shared, presentation-only UI primitives used across all feature modules. Stateless (except Modal and ErrorBoundary), composable, and styled with Tailwind CSS via the `cn()` utility.

## Components

### Button

Versatile button with variant and size options, plus a built-in loading spinner.

```typescript
import { Button } from "@/components/ui/Button";

<Button variant="primary" size="md" loading={isPending} onClick={handleClick}>
  Submit
</Button>
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `variant` | `"primary" \| "secondary" \| "ghost" \| "danger"` | `"primary"` | Color scheme |
| `size` | `"sm" \| "md" \| "lg"` | `"md"` | Height and padding |
| `loading` | `boolean` | `false` | Shows spinner, disables interaction |
| All native `<button>` props | `ButtonHTMLAttributes` | — | `disabled`, `type`, `onClick`, etc. |

### Input

Text input with optional label and error message.

```typescript
import { Input } from "@/components/ui/Input";

<Input
  label="Email"
  type="email"
  value={email}
  onChange={(e) => setEmail(e.target.value)}
  error={errors.email}
  required
/>
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `label` | `string` | — | Label above the input |
| `error` | `string` | — | Error message below the input, red border |
| All native `<input>` props | `InputHTMLAttributes` | — | `type`, `value`, `onChange`, etc. |

### Select

Dropdown select with options array.

```typescript
import { Select } from "@/components/ui/Select";

<Select
  label="Source Type"
  value={sourceType}
  onChange={(e) => setSourceType(e.target.value)}
  options={[
    { label: "Online Search", value: "online" },
    { label: "Local File", value: "local" },
  ]}
/>
```

| Prop | Type | Description |
|------|------|-------------|
| `label` | `string` | Label above the select |
| `error` | `string` | Error message |
| `options` | `Array<{ label: string; value: string }>` | Dropdown options |
| `placeholder` | `string` | Disabled placeholder option |

### Card

Content container with border, shadow, and optional padding.

```typescript
import { Card } from "@/components/ui/Card";

<Card>
  <h3>Title</h3>
  <p>Content</p>
</Card>

<Card noPadding>Custom padding control</Card>
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `noPadding` | `boolean` | `false` | Remove default `p-6` padding |

### Badge

Inline status indicator with color-coded variants.

```typescript
import { Badge } from "@/components/ui/Badge";

<Badge variant="success">Completed</Badge>
<Badge variant="error">Failed</Badge>
```

| Variant | Color |
|---------|-------|
| `default` | Gray |
| `success` | Green |
| `warning` | Yellow |
| `error` | Red |
| `info` | Blue |

### Modal

Accessible dialog with focus trap, Escape-to-close, and overlay click-to-close.

```typescript
import { Modal } from "@/components/ui/Modal";

<Modal open={isOpen} onClose={() => setIsOpen(false)} title="Confirm Action">
  <p>Are you sure?</p>
  <Button onClick={handleConfirm}>Yes</Button>
</Modal>
```

| Prop | Type | Description |
|------|------|-------------|
| `open` | `boolean` | Visibility control |
| `onClose` | `() => void` | Close callback (Escape, overlay click, X button) |
| `title` | `string` | Optional header with close button |
| `children` | `ReactNode` | Modal body content |

Accessibility features:
- `role="dialog"` + `aria-modal="true"`
- Focus trap (Tab cycles within modal)
- Escape key closes
- Body scroll locked when open

### Spinner

Animated SVG loading indicator.

```typescript
import { Spinner } from "@/components/ui/Spinner";

<Spinner size="lg" />
```

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `size` | `"sm" \| "md" \| "lg"` | `"md"` | Icon dimensions |

### NotificationToast

Global toast notification renderer. Reads from `useToastStore` and renders a stack of toasts in the bottom-right corner.

```typescript
// In app/layout.tsx (already mounted globally):
<NotificationToast />

// From anywhere:
import { useToastStore } from "@/stores/toastStore";
const addToast = useToastStore((s) => s.addToast);
addToast({ level: "success", title: "Saved", ttl: 3000 });
```

| Toast Level | Color |
|-------------|-------|
| `info` | Blue |
| `success` | Green |
| `warning` | Yellow |
| `error` | Red |

### ErrorBoundary

React class component that catches rendering errors in its subtree and shows a fallback UI instead of crashing the page.

```typescript
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";

<ErrorBoundary onError={(error) => console.error(error)}>
  <DataDrivenComponent />
</ErrorBoundary>
```

| Prop | Type | Description |
|------|------|-------------|
| `fallback` | `ReactNode` | Custom fallback UI (optional) |
| `onError` | `(error: Error, info: ErrorInfo) => void` | Error callback for logging |

Default fallback shows "Something went wrong" with a "Try again" reset button.

## Styling Convention

All components use `cn()` (from `@/lib/utils/cn`) for class name composition with Tailwind conflict resolution:

```typescript
import { cn } from "@/lib/utils/cn";

cn("px-4 py-2", isActive && "bg-primary-600", className)
```

## Extension Guide

### Adding a new component

1. Create `components/ui/NewComponent.tsx`
2. Use `forwardRef` for components that need ref forwarding
3. Export from the file directly (no barrel `index.ts` needed — import by path)
4. Use `cn()` for class composition, accept `className` for external overrides
5. Follow the existing prop pattern: extend native HTML attributes + custom props

### Adding a new variant

1. Add the variant to the type union
2. Add styles to the `Record<Variant, string>` map
3. Update this README's variant table

## Testing

UI components are tested via `frontend/tests/components/ui/`.

```bash
cd frontend
npm run test -- --testPathPattern=components/ui
```
