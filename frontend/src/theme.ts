import type { ThemeConfig } from "antd";

/**
 * Ant Design theme mapped from the former Tailwind design tokens.
 *
 * Primary teal (#0891B2) and success green (#22C55E) drive all
 * antd component colors. Pathogenicity colors and the display
 * font are exposed as CSS custom properties (see globals.css).
 */
export const theme: ThemeConfig = {
  token: {
    colorPrimary: "#0891b2",
    colorSuccess: "#22c55e",
    colorError: "#DC2626",
    colorWarning: "#F59E0B",
    colorInfo: "#0891b2",
    fontFamily: "Figtree, 'Noto Sans', system-ui, -apple-system, sans-serif",
    fontFamilyCode: "'JetBrains Mono', Menlo, monospace",
    borderRadius: 8,
    colorBgContainer: "#ffffff",
    colorBgLayout: "#f9fafb",
  },
};

/**
 * Pathogenicity classification colors — consumed via CSS variables
 * since antd has no built-in token for domain-specific palettes.
 */
export const pathoColors: Record<string, string> = {
  pathogenic: "#B91C1C",
  likely_pathogenic: "#DC2626",
  uncertain: "#6B7280",
  likely_benign: "#0D9488",
  benign: "#0F766E",
};
