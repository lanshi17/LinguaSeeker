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

// ── ResizeObserver ───────────────────────────────────────────────────
// Used by antd input/textarea components. jsdom does not implement it.

class ResizeObserverMock {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}

Object.defineProperty(window, "ResizeObserver", {
  writable: true,
  value: ResizeObserverMock,
});
