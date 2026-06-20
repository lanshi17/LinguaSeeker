import type { Config } from "tailwindcss";

/**
 * Cross Evidence Design System
 *
 * Based on UI/UX Pro Max "Accessible & Ethical" style:
 * - Medical teal primary (#0891B2)
 * - Health green CTA (#22C55E)
 * - High contrast, WCAG compliant
 * - Figtree / Noto Sans typography
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx}", "./index.html"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#ecfeff",
          100: "#cffafe",
          200: "#a5f3fc",
          300: "#67e8f9",
          400: "#22d3ee",
          500: "#06b6d4",
          600: "#0891b2",
          700: "#0e7490",
          800: "#155e75",
          900: "#164e63",
          950: "#083344",
        },
        success: {
          50: "#f0fdf4",
          100: "#dcfce7",
          200: "#bbf7d0",
          300: "#86efac",
          400: "#4ade80",
          500: "#22c55e",
          600: "#16a34a",
          700: "#15803d",
          800: "#166534",
          900: "#14532d",
        },
        patho: {
          pathogenic: "#B91C1C",
          likely_pathogenic: "#DC2626",
          uncertain: "#6B7280",
          likely_benign: "#0D9488",
          benign: "#0F766E",
        },
      },
      fontFamily: {
        sans: [
          "Figtree",
          "Noto Sans",
          "system-ui",
          "-apple-system",
          "sans-serif",
        ],
        display: ["Fraunces", "Georgia", "serif"],
        mono: ["JetBrains Mono", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
