
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils/cn";

interface ThinkingIndicatorProps {
  /** Rotating hint phrases. Defaults to generic reasoning hints. */
  hints?: string[];
  /** Rotation interval in ms. Default 2800. */
  rotateMs?: number;
  /** Optional leading label (non-rotating). */
  label?: string;
  className?: string;
}

const DEFAULT_HINTS = [
  "Reading your message",
  "Retrieving relevant literature",
  "Reasoning over the evidence",
  "Drafting a grounded reply",
];

/**
 * Typing-style "thinking" indicator shown while the assistant is generating.
 *
 * - Three bouncing dots (cheap, GPU-friendly CSS animation).
 * - A rotating hint phrase that fades every `rotateMs` ms so the wait
 *   feels like progress rather than a frozen spinner.
 * - Respects `prefers-reduced-motion` — dots collapse to a static dot row.
 */
export function ThinkingIndicator({
  hints = DEFAULT_HINTS,
  rotateMs = 2800,
  label = "Thinking",
  className,
}: ThinkingIndicatorProps) {
  const [hintIndex, setHintIndex] = useState(0);

  useEffect(() => {
    if (hints.length <= 1) return;
    const id = window.setInterval(() => {
      setHintIndex((i) => (i + 1) % hints.length);
    }, rotateMs);
    return () => window.clearInterval(id);
  }, [hints, rotateMs]);

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={label}
      className={cn(
        "flex items-center gap-3 rounded-2xl border border-gray-100",
        "bg-gradient-to-br from-white to-gray-50 px-4 py-3 shadow-sm",
        className,
      )}
    >
      <span className="flex items-end gap-1" aria-hidden="true">
        <span className="thinking-dot h-1.5 w-1.5 rounded-full bg-primary-500 [animation-delay:-0.32s]" />
        <span className="thinking-dot h-1.5 w-1.5 rounded-full bg-primary-500 [animation-delay:-0.16s]" />
        <span className="thinking-dot h-1.5 w-1.5 rounded-full bg-primary-500" />
      </span>
      <div className="flex min-w-0 flex-col">
        <span className="text-[11px] font-medium uppercase tracking-[0.12em] text-gray-400">
          {label}
        </span>
        <span
          key={hintIndex}
          className="thinking-hint truncate text-sm text-gray-600"
        >
          {hints[hintIndex]}
        </span>
      </div>
    </div>
  );
}
