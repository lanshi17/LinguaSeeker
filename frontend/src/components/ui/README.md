# UI Components

> Reusable presentation components built on top of Ant Design.

## Components

| Component | Description | Key Props |
|-----------|-------------|-----------|
| **Badge** | Semantic status tag wrapping antd `Tag`. Variants: `default`, `success`, `warning`, `error`, `info`. | `variant` |
| **Spinner** | Animated SVG loading indicator. | `size: "sm" \| "md" \| "lg"` |
| **ErrorBoundary** | React error boundary with fallback UI and "Try again" button. | `fallback`, `onError` |
| **MetricTile** | Compact label/value tile for quantitative facts. Tones: `default`, `primary`, `success`, `warning`, `error`. | `label`, `value`, `unit`, `tone`, `icon` |
| **LivePulse** | Small live indicator: solid dot + expanding ring animation. Tones: `primary`, `success`, `warning`, `error`, `neutral`. | `tone`, `label` |
| **Skeleton** | Animated shimmer placeholder block. Variants: `text`, `line`, `circle`, `block`, `pill`. 1.6s gradient animation. | `variant`, `width`, `height` |
| **PageTransition** | Route-level fade-in animation wrapper. | `AnimatedOutlet` |

## Styling Convention

Components use inline styles and antd theme tokens. CSS custom properties defined in `globals.css` provide the design system. Accept `className` and `style` for external overrides.

## Adding a Component

1. Create `components/ui/Name.tsx`.
2. Use `forwardRef` where needed; extend native HTML attributes.
3. Use inline styles or antd theme tokens for styling.
4. Import by file path (no barrel index needed).
