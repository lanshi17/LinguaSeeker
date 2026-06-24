/**
 * Synchronous scrolling utility for bilingual document comparison.
 *
 * Uses scroll-ratio (0–1) rather than absolute pixels so panels with
 * different content lengths stay proportionally aligned.
 *
 *   ratio = scrollTop / (scrollHeight - clientHeight)
 *   target.scrollTop = ratio × (target.scrollHeight - target.clientHeight)
 *
 * A `MutableRefObject<boolean>` guard prevents the A→B→A feedback loop:
 * when we programmatically set `scrollTop` on the target, the target's
 * `onScroll` fires — the guard short-circuits it, then resets on the
 * next animation frame.
 */

import type { MutableRefObject, UIEvent } from "react";

/**
 * Core sync: copy scroll position from `source` to `target` by ratio.
 * The `guard` ref prevents recursive scroll events.
 */
export function handleScrollSync(
  source: HTMLElement,
  target: HTMLElement,
  guard: MutableRefObject<boolean>,
): void {
  if (guard.current) return;
  guard.current = true;

  const maxSrc = source.scrollHeight - source.clientHeight;
  const ratio = maxSrc > 0 ? source.scrollTop / maxSrc : 0;
  const maxTgt = target.scrollHeight - target.clientHeight;
  target.scrollTop = ratio * (maxTgt > 0 ? maxTgt : 0);

  // Reset on next frame so the target's synthetic scroll event is absorbed.
  requestAnimationFrame(() => {
    guard.current = false;
  });
}

/**
 * Build a scroll handler that syncs `source` → `targetRef.current`.
 * Returns a stable handler given the same inputs.
 */
export function createScrollSyncHandler(
  targetRef: MutableRefObject<HTMLElement | null>,
  guard: MutableRefObject<boolean>,
  enabled: boolean,
) {
  return (e: UIEvent<HTMLElement>) => {
    if (!enabled || !targetRef.current || guard.current) return;
    handleScrollSync(e.currentTarget, targetRef.current, guard);
  };
}

/* ── localStorage persistence ───────────────────────────────────────────── */

const STORAGE_KEY = "bilingual:scrollSync";

export function loadScrollSyncSetting(): boolean {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? JSON.parse(saved) === true : false;
  } catch {
    return false;
  }
}

export function saveScrollSyncSetting(enabled: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(enabled));
  } catch {
    // ignore quota / privacy-mode errors
  }
}
