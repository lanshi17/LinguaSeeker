import { useMemo } from "react";
import { CATEGORY_COLORS } from "@/features/evidence-search/utils/evidenceDocument";
import type { EvidenceDocumentParagraph } from "@/features/evidence-search/utils/evidenceDocument";

/* ── Style helpers (replace Tailwind-based categoryMarkStyle / categoryChipStyle) ── */

export function markInlineStyle(category?: string | null, selected?: boolean): React.CSSProperties {
  const hex = category && CATEGORY_COLORS[category]
    ? CATEGORY_COLORS[category].hex
    : "#9CA3AF";
  const base: React.CSSProperties = {
    backgroundColor: `${hex}50`,
    color: `${hex}f0`,
    boxShadow: `0 0 0 1px ${hex}60`,
    borderRadius: 2,
    padding: "0 2px",
    cursor: "help",
    transition: "all 0.15s",
  };
  if (selected) {
    base.boxShadow = `0 0 0 2px var(--color-primary-500), 0 0 0 3px white, 0 0 0 1px ${hex}60`;
  }
  return base;
}

/* ── Highlighted Text Renderer ──────────────────────────── */

export function HighlightedText({ paragraph }: { paragraph: EvidenceDocumentParagraph }) {
  const sorted = useMemo(
    () => [...paragraph.highlights].sort((a, b) => a.start - b.start),
    [paragraph.highlights],
  );
  if (sorted.length === 0) {
    return (
      <p style={{
        fontSize: 14,
        lineHeight: 1.625,
        color: "#374151",
        whiteSpace: "pre-wrap",
        margin: 0,
      }}>
        {paragraph.text}
      </p>
    );
  }

  const segments: React.ReactNode[] = [];
  let cursor = 0;

  for (const hl of sorted) {
    const start = Math.max(0, Math.min(hl.start, paragraph.text.length));
    const end = Math.max(start, Math.min(hl.end, paragraph.text.length));
    if (start > end) continue;

    if (cursor < start) {
      segments.push(
        <span key={`plain-${cursor}`}>
          {paragraph.text.slice(cursor, start)}
        </span>,
      );
    }

    segments.push(
      <mark
        key={`hl-${hl.evidenceId}-${start}`}
        style={markInlineStyle(hl.category, hl.selected)}
        title={`${hl.label} (${hl.fieldId})`}
      >
        {paragraph.text.slice(start, end)}
      </mark>,
    );
    cursor = end;
  }

  if (cursor < paragraph.text.length) {
    segments.push(
      <span key={`tail-${cursor}`}>{paragraph.text.slice(cursor)}</span>,
    );
  }

  return (
    <p style={{
      fontSize: 14,
      lineHeight: 1.625,
      color: "#374151",
      whiteSpace: "pre-wrap",
      margin: 0,
    }}>
      {segments}
    </p>
  );
}
