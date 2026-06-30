/**
 * Vitest global setup file.
 *
 * Provides browser API mocks that jsdom does not implement natively.
 * Referenced by vitest.config.ts → test.setupFiles.
 */

import { vi } from "vitest";

// ── window.matchMedia ────────────────────────────────────────────────
// appStore.ts calls window.matchMedia("(prefers-color-scheme: dark)")
// at import time. jsdom does not implement it, so we polyfill here.

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),            // deprecated
    removeListener: vi.fn(),         // deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});
