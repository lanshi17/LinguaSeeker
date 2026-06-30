import type { CSSProperties } from "react";
import type {
  EvidenceChainHighlight,
  EvidenceHighlightTone,
} from "../types/evidenceSearch";

export type { EvidenceHighlightTone } from "../types/evidenceSearch";

interface EvidenceHighlightTextProps {
  highlight?: EvidenceChainHighlight | null;
  active?: boolean;
  anchorValue?: string | null;
  label?: string;
  tone?: EvidenceHighlightTone;
  category?: string | null;
}

const TONE_STYLES: Record<EvidenceHighlightTone, CSSProperties> = {
  classification: {
    backgroundColor: "#fde68a",
    color: "var(--color-text-strong)",
    boxShadow: "0 0 0 1px #fcd34d",
  },
  disease: {
    backgroundColor: "#fecdd3",
    color: "var(--color-text-strong)",
    boxShadow: "0 0 0 1px #fda4af",
  },
  functional: {
    backgroundColor: "var(--color-success-200)",
    color: "var(--color-text-strong)",
    boxShadow: "0 0 0 1px var(--color-success-300)",
  },
  gene: {
    backgroundColor: "var(--color-primary-200)",
    color: "var(--color-primary-950)",
    boxShadow: "0 0 0 1px var(--color-primary-300)",
  },
  neutral: {
    backgroundColor: "var(--color-border)",
    color: "var(--color-text)",
    boxShadow: "0 0 0 1px var(--color-text-muted)",
  },
  variant: {
    backgroundColor: "#a5f3fc",
    color: "var(--color-text-strong)",
    boxShadow: "0 0 0 1px #67e8f9",
  },
};

/** Inline-style equivalents for CATEGORY_COLORS mark classes. */
const CATEGORY_MARK_STYLES: Record<string, CSSProperties> = {
  A: { backgroundColor: "#fde68a", color: "var(--color-text-strong)", boxShadow: "0 0 0 1px #fcd34d" },
  B: { backgroundColor: "#bfdbfe", color: "var(--color-text-strong)", boxShadow: "0 0 0 1px #93c5fd" },
  C: { backgroundColor: "#ddd6fe", color: "var(--color-text-strong)", boxShadow: "0 0 0 1px #c4b5fd" },
  D: { backgroundColor: "#a5f3fc", color: "var(--color-text-strong)", boxShadow: "0 0 0 1px #67e8f9" },
  E: { backgroundColor: "#a7f3d0", color: "var(--color-text-strong)", boxShadow: "0 0 0 1px #6ee7b7" },
  F: { backgroundColor: "#bbf7d0", color: "var(--color-text-strong)", boxShadow: "0 0 0 1px #86efac" },
  G: { backgroundColor: "#fed7aa", color: "var(--color-text-strong)", boxShadow: "0 0 0 1px #fdba74" },
  H: { backgroundColor: "var(--color-error-border)", color: "var(--color-text-strong)", boxShadow: "0 0 0 1px #fca5a5" },
  I: { backgroundColor: "#99f6e4", color: "var(--color-text-strong)", boxShadow: "0 0 0 1px #5eead4" },
  J: { backgroundColor: "#fbcfe8", color: "var(--color-text-strong)", boxShadow: "0 0 0 1px #f9a8d4" },
};

const INACTIVE_MARK_STYLE: CSSProperties = {
  backgroundColor: "#fef9c3",
  color: "var(--color-text)",
};

function escapedRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function findAnchorRange(text: string, rawValue?: string | null) {
  const value = rawValue?.trim();
  if (!value || value.length === 1) {
    return null;
  }
  if (value.length === 2) {
    if (value !== value.toUpperCase()) {
      return null;
    }
    const match = new RegExp(
      `(^|[^A-Za-z0-9])(${escapedRegExp(value)})(?![A-Za-z0-9])`,
    ).exec(text);
    if (!match) {
      return null;
    }
    const start = match.index + match[1].length;
    return { start, end: start + value.length };
  }
  const index = text.toLowerCase().indexOf(value.toLowerCase());
  if (index < 0) {
    return null;
  }
  return { start: index, end: index + value.length };
}

export function EvidenceHighlightText({
  highlight,
  active = false,
  anchorValue,
  label,
  tone = "neutral",
  category,
}: EvidenceHighlightTextProps) {
  if (!highlight || !highlight.text) {
    return (
      <div style={{
        borderRadius: 8,
        border: "1px dashed var(--color-text-muted)",
        backgroundColor: "var(--color-bg)",
        padding: 16,
        fontSize: 14,
        color: "var(--color-text-secondary)",
      }}>
        No source span available.
      </div>
    );
  }

  let start = Math.max(0, Math.min(highlight.highlight_start, highlight.text.length));
  let end = Math.max(start, Math.min(highlight.highlight_end, highlight.text.length));
  if (end === start) {
    const anchor = findAnchorRange(highlight.text, anchorValue);
    if (anchor) {
      start = anchor.start;
      end = anchor.end;
    }
  }
  const before = highlight.text.slice(0, start);
  const marked = highlight.text.slice(start, end);
  const after = highlight.text.slice(end);
  const hasMark = end > start;

  const markStyle: CSSProperties = active
    ? (category && CATEGORY_MARK_STYLES[category]) || TONE_STYLES[tone]
    : INACTIVE_MARK_STYLE;

  return (
    <div style={{
      borderRadius: 8,
      border: "1px solid var(--color-border)",
      backgroundColor: "var(--color-surface)",
      padding: 16,
      fontSize: 14,
      lineHeight: "28px",
      color: "var(--color-code-text)",
      boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
    }}>
      <div style={{ marginBottom: 12, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, fontSize: 12, color: "var(--color-text-secondary)" }}>
        {label && (
          <span style={{
            borderRadius: 6,
            backgroundColor: "var(--color-bg-muted)",
            padding: "4px 8px",
            fontWeight: 500,
            color: "var(--color-text-strong)",
          }}>
            {label}
          </span>
        )}
        <span>Page {highlight.page ?? "\u2014"}</span>
        {!hasMark && (
          <span
            data-testid="highlight-unavailable"
            style={{
              borderRadius: 4,
              backgroundColor: "var(--color-bg-muted)",
              padding: "2px 6px",
              color: "var(--color-text-muted)",
            }}
          >
            highlight unavailable
          </span>
        )}
      </div>
      <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>
        {before}
        {hasMark ? (
          <mark
            style={{
              borderRadius: 4,
              padding: "2px 4px",
              fontWeight: 500,
              ...markStyle,
            }}
          >
            {marked}
          </mark>
        ) : null}
        {!hasMark ? marked : null}
        {after}
      </p>
    </div>
  );
}
