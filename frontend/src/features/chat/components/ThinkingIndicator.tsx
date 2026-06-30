import { useI18n } from "@/lib/i18n";
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

function getDefaultHints(t: (key: string) => string): string[] {
  return [
    t("chat.thinking.reading"),
    t("chat.thinking.retrieving"),
    t("chat.thinking.reasoning"),
    t("chat.thinking.drafting"),
  ];
}

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
  hints: hintsProp,
  rotateMs = 2800,
  label: labelProp,
  className,
}: ThinkingIndicatorProps) {
  const { t } = useI18n();
  const hints = hintsProp ?? getDefaultHints(t);
  const label = labelProp ?? t("chat.thinking.label");
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
        border: "1px solid var(--color-bg-muted)",
        background: "linear-gradient(to bottom right, var(--color-surface), var(--color-bg))",
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
            color: "var(--color-text-muted)",
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
            color: "var(--color-text-strong)",
          }}
        >
          {hints[hintIndex]}
        </span>
      </div>
    </div>
  );
}
