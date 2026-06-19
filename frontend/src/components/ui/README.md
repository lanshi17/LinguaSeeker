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
| **MetricTile** | Compact label/value tile for quantitative facts. Tones: `default`, `primary`, `success`, `warning`, `error`. Optimised for tabular display inside phase cards. | `label`, `value`, `unit`, `tone`, `icon` |
| **LivePulse** | Small live indicator: solid dot + expanding ring animation. Communicates "in progress" without full spinner noise. Tones: `primary`, `success`, `warning`, `error`, `neutral`. | `tone`, `label` |
| **Skeleton** | Animated shimmer placeholder block. Variants: `text`, `line`, `circle`, `block`, `pill`. 1.6s gradient animation. | `variant`, `width`, `height` |

## Styling Convention

All components use `cn()` from `@/lib/utils/cn` for class composition with Tailwind conflict resolution. Accept `className` for external overrides.

## Adding a Component

1. Create `components/ui/Name.tsx`.
2. Use `forwardRef` where needed; extend native HTML attributes.
3. Use `cn()` for class composition.
4. Import by file path (no barrel index needed).
