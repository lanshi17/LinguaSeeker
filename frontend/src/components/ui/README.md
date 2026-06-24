# UI Components

> Reusable presentation components built on top of Ant Design.

## Components

| Component | File | Description | Key Props |
|-----------|------|-------------|-----------|
| **Badge** | `Badge.tsx` | Semantic status tag wrapping antd `Tag`. Variants: `default`, `success`, `warning`, `error`, `info`. | `variant` |
| **Spinner** | `Spinner.tsx` | Animated SVG loading indicator. | `size: "sm" \| "md" \| "lg"` |
| **ErrorBoundary** | `ErrorBoundary.tsx` | React class error boundary with fallback UI and "Try again" reset button. | `fallback`, `onError` |
| **MetricTile** | `MetricTile.tsx` | Compact label/value tile for quantitative facts. Tones: `default`, `primary`, `success`, `warning`, `error`. | `label`, `value`, `unit`, `tone`, `icon` |
| **LivePulse** | `LivePulse.tsx` | Small live indicator: solid dot + expanding ring animation. Tones: `primary`, `success`, `warning`, `error`, `neutral`. | `tone`, `label` |
| **Skeleton** | `Skeleton.tsx` | Animated shimmer placeholder. Variants: `text`, `line`, `circle`, `block`, `pill`. | `variant`, `width`, `height` |
| **AnimatedOutlet** | `PageTransition.tsx` | Drop-in `<Outlet />` replacement with fade-in animation on route change. Uses pathname as key. Respects `prefers-reduced-motion`. | -- |

## Styling Convention

Components use inline styles and antd theme tokens. CSS custom properties defined in `globals.css` provide the design system. Components accept `className` and `style` for external overrides.

## Adding a Component

1. Create `components/ui/Name.tsx`.
2. Use `forwardRef` where needed; extend native HTML attributes.
3. Use inline styles or antd theme tokens for styling.
4. Import by file path (no barrel index).
