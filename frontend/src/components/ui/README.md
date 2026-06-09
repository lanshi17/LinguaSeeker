# UI Components

> Shared presentation-only primitives. Styled with Tailwind via `cn()`.

## Components

| Component | Description | Key Props |
|-----------|-------------|-----------|
| **Button** | Variants: `primary`, `secondary`, `ghost`, `danger`. Sizes: `sm`, `md`, `lg`. Built-in loading spinner. | `variant`, `size`, `loading` |
| **Card** | Content container with border and shadow. | `noPadding` |
| **Modal** | Accessible dialog with focus trap, Escape close, overlay click close. Body scroll locked. | `open`, `onClose`, `title` |
| **Spinner** | Animated SVG loading indicator. | `size: "sm" \| "md" \| "lg"` |
| **Badge** | Inline status indicator. Variants: `default`, `success`, `warning`, `error`, `info`. | `variant` |
| **Select** | Dropdown with options array. | `label`, `options`, `error`, `placeholder` |
| **Input** | Text input with optional label and error. | `label`, `error` + native input props |
| **Toast** | Global notification renderer (reads `toastStore`). Levels: `info`, `success`, `warning`, `error`. | Mounted in root layout |
| **ErrorBoundary** | React error boundary with fallback UI and "Try again" button. | `fallback`, `onError` |

## Styling Convention

All components use `cn()` from `@/lib/utils/cn` for class composition with Tailwind conflict resolution. Accept `className` for external overrides.

## Adding a Component

1. Create `components/ui/Name.tsx`.
2. Use `forwardRef` where needed; extend native HTML attributes.
3. Use `cn()` for class composition.
4. Import by file path (no barrel index needed).
