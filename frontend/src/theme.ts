import type { ThemeConfig } from "antd";
import { theme as antdTheme } from "antd";

/**
 * Ant Design theme mapped from the former Tailwind design tokens.
 *
 * Primary teal (#0891B2) and success green (#22C55E) drive all
 * antd component colors. Pathogenicity colors and the display
 * font are exposed as CSS custom properties (see globals.css).
 */

const sharedTokens: ThemeConfig["token"] = {
  colorPrimary: "#0891b2",
  colorSuccess: "#22c55e",
  colorError: "#DC2626",
  colorWarning: "#F59E0B",
  colorInfo: "#0891b2",
  fontFamily: "Figtree, 'Noto Sans', system-ui, -apple-system, sans-serif",
  fontFamilyCode: "'JetBrains Mono', Menlo, monospace",
  borderRadius: 8,
};

export const lightTheme: ThemeConfig = {
  token: {
    ...sharedTokens,
    colorBgContainer: "#ffffff",
    colorBgLayout: "#f9fafb",
  },
};

export const darkTheme: ThemeConfig = {
  algorithm: antdTheme.darkAlgorithm,
  token: {
    ...sharedTokens,
    colorBgContainer: "#16162a",
    colorBgLayout: "#0f0f1a",
    colorBgElevated: "#1e1e36",
    colorBorder: "#2a2a42",
    colorBorderSecondary: "#22223a",
    colorText: "#e4e4ef",
    colorTextSecondary: "#a0a0b8",
    colorTextTertiary: "#6b6b85",
    colorTextQuaternary: "#4a4a65",
  },
};

