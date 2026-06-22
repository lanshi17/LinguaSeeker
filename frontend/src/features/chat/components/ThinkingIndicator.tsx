
import { useEffect, useState } from "react";

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

const dotBase: React.CSSProperties = {
  width: 6,
  height: 6,
  borderRadius: "50%",
  backgroundColor: "var(--color-primary-600, #0891b2)",
};

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
      className={className}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        borderRadius: 16,
        border: "1px solid #f3f4f6",
        background: "linear-gradient(to bottom right, #ffffff, #f9fafb)",
        padding: "12px 16px",
        boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
      }}
    >
      <span style={{ display: "flex", alignItems: "flex-end", gap: 4 }} aria-hidden="true">
        <span className="thinking-dot" style={{ ...dotBase, animationDelay: "-0.32s" }} />
        <span className="thinking-dot" style={{ ...dotBase, animationDelay: "-0.16s" }} />
        <span className="thinking-dot" style={dotBase} />
      </span>
      <div style={{ display: "flex", minWidth: 0, flexDirection: "column" }}>
        <span
          style={{
            fontSize: 11,
            fontWeight: 500,
            textTransform: "uppercase",
            letterSpacing: "0.12em",
            color: "#9ca3af",
          }}
        >
          {label}
        </span>
        <span
          key={hintIndex}
          className="thinking-hint"
          style={{
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            fontSize: 14,
            color: "#4b5563",
          }}
        >
          {hints[hintIndex]}
        </span>
      </div>
    </div>
  );
}
