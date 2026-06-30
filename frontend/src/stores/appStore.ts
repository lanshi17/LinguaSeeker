/**
 * Minimal global application state.
 *
 * Only cross-cutting UI state that cannot be scoped to a single feature.
 * Feature-specific state belongs in feature-local stores.
 */

import { create } from "zustand";
import { devtools } from "zustand/middleware";

const LANG_COOKIE = "ls_lang";
const THEME_COOKIE = "ls_theme";
const COOKIE_MAX_AGE = 365 * 24 * 60 * 60; // 1 year

function readCookie(name: string): string | null {
  const m = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return m ? decodeURIComponent(m[1]) : null;
}

/** Detect locale: cookie → browser language → "en". */
function detectLocale(): "en" | "zh" {
  const saved = readCookie(LANG_COOKIE);
  if (saved === "en" || saved === "zh") return saved;
  const browser = navigator.language.toLowerCase();
  return browser.startsWith("zh") ? "zh" : "en";
}

/** Detect theme: cookie → prefers-color-scheme → "light". Side-effects: sets data-theme. */
function detectMode(): "light" | "dark" {
  const saved = readCookie(THEME_COOKIE);
  const mode = saved === "light" || saved === "dark"
    ? saved
    : window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", mode);
  return mode;
}

interface AppState {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  locale: "en" | "zh";
  setLocale: (lang: "en" | "zh") => void;
  mode: "light" | "dark";
  setMode: (mode: "light" | "dark") => void;
}

export const useAppStore = create<AppState>()(
  devtools(
    (set) => ({
      sidebarCollapsed: false,

      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),

      locale: detectLocale(),

      setLocale: (lang) => {
        document.cookie = `${LANG_COOKIE}=${lang}; Max-Age=${COOKIE_MAX_AGE}; Path=/; SameSite=Lax`;
        set({ locale: lang });
      },

      mode: detectMode(),

      setMode: (mode) => {
        document.cookie = `${THEME_COOKIE}=${mode}; Max-Age=${COOKIE_MAX_AGE}; Path=/; SameSite=Lax`;
        document.documentElement.setAttribute("data-theme", mode);
        set({ mode });
      },
    }),
    { name: "app-store" },
  ),
);
