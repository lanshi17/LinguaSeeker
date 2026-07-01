import { useMemo } from "react";
import { CATEGORY_COLORS } from "@/features/evidence-search/utils/evidenceDocument";
import type { EvidenceDocumentParagraph } from "@/features/evidence-search/utils/evidenceDocument";
import type { AlignmentTextHighlight } from "@/features/evidence-search/utils/translationAlignment";
import { openFieldReviewMenu } from "@/features/evidence-search/components/FieldReviewPopover";
import type { FieldReviewInfo } from "@/features/evidence-search/components/FieldReviewPopover";

/* ── Style helpers (replace Tailwind-based categoryMarkStyle / categoryChipStyle) ── */

export function markInlineStyle(category?: string | null, selected?: boolean): React.CSSProperties {
  const hex = category && CATEGORY_COLORS[category]
    ? CATEGORY_COLORS[category].hex
    : "var(--color-text-muted)";
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

/** Map from canonical_evidence_id → review info, used to enable hover-to-review. */
export type ReviewContextMap = Map<string, FieldReviewInfo>;

interface HighlightedTextProps {
  paragraph: EvidenceDocumentParagraph;
  /** If provided, <mark> elements get click-to-review handlers. */
  reviewContexts?: ReviewContextMap;
  alignmentHighlights?: AlignmentTextHighlight[];
  onAlignmentHover?: (pairId: string) => void;
  onAlignmentLeave?: () => void;
  onAlignmentToggle?: (pairId: string) => void;
}

function alignmentInlineStyle(
  alignment: AlignmentTextHighlight,
  hasEvidence: boolean,
): React.CSSProperties {
  const activeColor = alignment.pinned ? "#7C3AED" : "#0891B2";
  if (hasEvidence) {
    return alignment.active
      ? {
          outline: `2px solid ${activeColor}`,
          outlineOffset: "2px",
        }
      : {};
  }
  return {
    borderRadius: 3,
    padding: "0 2px",
    backgroundColor: alignment.active ? `${activeColor}30` : "rgba(8, 145, 178, 0.12)",
    boxShadow: alignment.active ? `0 0 0 1px ${activeColor}70` : "0 0 0 1px rgba(8, 145, 178, 0.22)",
    cursor: "pointer",
    transition: "background-color 0.12s, box-shadow 0.12s",
  };
}

function alignmentProps(
  alignment: AlignmentTextHighlight | undefined,
  onAlignmentHover?: (pairId: string) => void,
  onAlignmentLeave?: () => void,
  onAlignmentToggle?: (pairId: string) => void,
) {
  if (!alignment) {
    return {};
  }
  return {
    "data-alignment-pair-id": alignment.pairId,
    "data-alignment-active": alignment.active ? "true" : "false",
    onMouseEnter: () => onAlignmentHover?.(alignment.pairId),
    onMouseLeave: () => onAlignmentLeave?.(),
    onClick: () => onAlignmentToggle?.(alignment.pairId),
  };
}

export function HighlightedText({
  paragraph,
  reviewContexts,
  alignmentHighlights = [],
  onAlignmentHover,
  onAlignmentLeave,
  onAlignmentToggle,
}: HighlightedTextProps) {
  const sorted = useMemo(
    () => [...paragraph.highlights].sort((a, b) => a.start - b.start),
    [paragraph.highlights],
  );
  const sortedAlignment = useMemo(
    () => [...alignmentHighlights].sort((a, b) => a.start - b.start),
    [alignmentHighlights],
  );
  if (sorted.length === 0 && sortedAlignment.length === 0) {
    return (
      <p style={{
        fontSize: 14,
        lineHeight: 1.625,
        color: "var(--color-text-strong)",
        whiteSpace: "pre-wrap",
        margin: 0,
      }}>
        {paragraph.text}
      </p>
    );
  }

  const segments: React.ReactNode[] = [];
  const boundaries = new Set<number>([0, paragraph.text.length]);
  for (const hl of sorted) {
    boundaries.add(Math.max(0, Math.min(hl.start, paragraph.text.length)));
    boundaries.add(Math.max(0, Math.min(hl.end, paragraph.text.length)));
  }
  for (const alignment of sortedAlignment) {
    boundaries.add(Math.max(0, Math.min(alignment.start, paragraph.text.length)));
    boundaries.add(Math.max(0, Math.min(alignment.end, paragraph.text.length)));
  }

  const orderedBoundaries = [...boundaries].sort((a, b) => a - b);
  for (let index = 0; index < orderedBoundaries.length - 1; index++) {
    const start = orderedBoundaries[index];
    const end = orderedBoundaries[index + 1];
    if (end <= start) {
      continue;
    }

    const text = paragraph.text.slice(start, end);
    const hl = sorted.find((candidate) => candidate.start < end && candidate.end > start);
    const alignment = sortedAlignment.find(
      (candidate) => candidate.start < end && candidate.end > start,
    );
    if (!hl && !alignment) {
      segments.push(<span key={`plain-${start}`}>{text}</span>);
      continue;
    }

    if (!hl && alignment) {
      segments.push(
        <span
          key={`align-${alignment.pairId}-${start}`}
          style={alignmentInlineStyle(alignment, false)}
          {...alignmentProps(alignment, onAlignmentHover, onAlignmentLeave, onAlignmentToggle)}
        >
          {text}
        </span>,
      );
      continue;
    }

    if (!hl) {
      continue;
    }
    const reviewInfo = reviewContexts?.get(hl.evidenceId);
    const markStyle = {
      ...markInlineStyle(hl.category, hl.selected),
      ...(alignment ? alignmentInlineStyle(alignment, true) : {}),
      ...(reviewInfo ? { cursor: "pointer" as const } : {}),
    };
    segments.push(
      <mark
        key={`hl-${hl.evidenceId}-${start}`}
        data-reviewable={reviewInfo ? "true" : undefined}
        style={markStyle}
        {...alignmentProps(alignment, onAlignmentHover, onAlignmentLeave, onAlignmentToggle)}
        onClick={(e) => {
          if (alignment) {
            onAlignmentToggle?.(alignment.pairId);
          }
          if (reviewInfo) {
            openFieldReviewMenu(e, reviewInfo);
          }
        }}
        onContextMenu={reviewInfo ? (e) => openFieldReviewMenu(e, reviewInfo) : undefined}
      >
        {text}
      </mark>,
    );
  }

  return (
    <p style={{
      fontSize: 14,
      lineHeight: 1.625,
      color: "var(--color-text-strong)",
      whiteSpace: "pre-wrap",
      margin: 0,
    }}>
      {segments}
    </p>
  );
}
