import { useMemo } from "react";
import type { ContentBlock } from "@/features/evidence-search/types/evidenceSearch";
import { CATEGORY_COLORS } from "@/features/evidence-search/utils/evidenceDocument";
import type { AlignmentTextHighlight } from "@/features/evidence-search/utils/translationAlignment";

/* ── Types ──────────────────────────────────────────────── */

export interface BlockHighlight {
  evidenceId: string;
  fieldId: string;
  label: string;
  tone: string;
  category?: string | null;
  /** Global character offset in the full formatted text. */
  globalStart: number;
  globalEnd: number;
  selected?: boolean;
}

interface BlockWithRange {
  block: ContentBlock;
  /** Start offset of this block's text in the full formatted text. */
  globalOffset: number;
  /** Extracted display text for this block. */
  text: string;
}

interface AlignmentHandlers {
  onAlignmentHover?: (pairId: string) => void;
  onAlignmentLeave?: () => void;
  onAlignmentToggle?: (pairId: string) => void;
}

/* ── Text extraction from blocks ────────────────────────── */

function blockDisplayText(block: ContentBlock): string {
  switch (block.type) {
    case "table":
      return [
        ...(block.table_caption ?? []),
        block.text ?? "",
        ...(block.table_footnote ?? []),
      ].filter(Boolean).join("\n");
    case "list":
      return (block.list_items ?? []).join("\n");
    case "code":
      return [
        ...(block.code_caption ?? []),
        block.code_body ?? "",
      ].filter(Boolean).join("\n");
    case "image":
    case "chart":
      return [
        ...(block.image_caption ?? block.chart_caption ?? []),
        block.content ?? "",
        ...(block.image_footnote ?? block.chart_footnote ?? []),
      ].filter(Boolean).join("\n");
    default:
      return block.text ?? "";
  }
}

/* ── Build block-to-offset mapping ──────────────────────── */

function buildBlockRanges(blocks: ContentBlock[]): BlockWithRange[] {
  const ranges: BlockWithRange[] = [];
  let offset = 0;
  for (const block of blocks) {
    const text = blockDisplayText(block);
    if (text) {
      ranges.push({ block, globalOffset: offset, text });
      offset += text.length + 2; // +2 for "\n\n" separator between blocks
    }
  }
  return ranges;
}

/* ── Highlight overlay for a text segment ───────────────── */

function HighlightedSegment({
  text,
  globalStart,
  highlights,
  alignmentHighlights = [],
  onAlignmentHover,
  onAlignmentLeave,
  onAlignmentToggle,
}: {
  text: string;
  globalStart: number;
  highlights: BlockHighlight[];
  alignmentHighlights?: AlignmentTextHighlight[];
  onAlignmentHover?: (pairId: string) => void;
  onAlignmentLeave?: () => void;
  onAlignmentToggle?: (pairId: string) => void;
}) {
  const localHighlights = useMemo(() => {
    return highlights
      .map((h) => {
        const start = Math.max(0, h.globalStart - globalStart);
        const end = Math.min(text.length, h.globalEnd - globalStart);
        if (start >= text.length || end <= 0 || start >= end) return null;
        return { ...h, start, end };
      })
      .filter((h): h is BlockHighlight & { start: number; end: number } => h !== null)
      .sort((a, b) => a!.start - b!.start);
  }, [text, globalStart, highlights]);
  const localAlignmentHighlights = useMemo(() => {
    return alignmentHighlights
      .map((h) => {
        const start = Math.max(0, h.start - globalStart);
        const end = Math.min(text.length, h.end - globalStart);
        if (start >= text.length || end <= 0 || start >= end) return null;
        return { ...h, start, end };
      })
      .filter((h): h is AlignmentTextHighlight => h !== null)
      .sort((a, b) => a!.start - b!.start);
  }, [text, globalStart, alignmentHighlights]);

  if (localHighlights.length === 0 && localAlignmentHighlights.length === 0) {
    return <>{text}</>;
  }

  const segments: React.ReactNode[] = [];
  const boundaries = new Set<number>([0, text.length]);
  for (const hl of localHighlights) {
    if (!hl) continue;
    boundaries.add(hl.start);
    boundaries.add(hl.end);
  }
  for (const alignment of localAlignmentHighlights) {
    if (!alignment) continue;
    boundaries.add(alignment.start);
    boundaries.add(alignment.end);
  }

  const orderedBoundaries = [...boundaries].sort((a, b) => a - b);
  for (let index = 0; index < orderedBoundaries.length - 1; index++) {
    const start = orderedBoundaries[index];
    const end = orderedBoundaries[index + 1];
    if (end <= start) {
      continue;
    }
    const evidence = localHighlights.find((hl) => hl && hl.start < end && hl.end > start);
    const alignment = localAlignmentHighlights.find(
      (hl) => hl && hl.start < end && hl.end > start,
    );
    const segmentText = text.slice(start, end);
    if (!evidence && !alignment) {
      segments.push(<span key={`p-${start}`}>{segmentText}</span>);
      continue;
    }
    if (!evidence && alignment) {
      segments.push(
        <span
          key={`a-${alignment.pairId}-${start}`}
          data-alignment-pair-id={alignment.pairId}
          data-alignment-active={alignment.active ? "true" : "false"}
          onMouseEnter={() => onAlignmentHover?.(alignment.pairId)}
          onMouseLeave={() => onAlignmentLeave?.()}
          onClick={() => onAlignmentToggle?.(alignment.pairId)}
          style={alignmentSegmentStyle(alignment, false)}
        >
          {segmentText}
        </span>,
      );
      continue;
    }
    if (!evidence) {
      continue;
    }
    const hex = evidence.category && CATEGORY_COLORS[evidence.category]
      ? CATEGORY_COLORS[evidence.category].hex
      : "var(--color-text-muted)";
    segments.push(
      <mark
        key={`h-${evidence.evidenceId}-${start}`}
        data-alignment-pair-id={alignment?.pairId}
        data-alignment-active={alignment?.active ? "true" : undefined}
        onMouseEnter={alignment ? () => onAlignmentHover?.(alignment.pairId) : undefined}
        onMouseLeave={alignment ? () => onAlignmentLeave?.() : undefined}
        onClick={alignment ? () => onAlignmentToggle?.(alignment.pairId) : undefined}
        style={{
          backgroundColor: `${hex}50`,
          color: `${hex}f0`,
          boxShadow: `0 0 0 1px ${hex}60`,
          borderRadius: 2,
          padding: "0 2px",
          cursor: "help",
          ...alignmentSegmentStyle(alignment, true),
        }}
        title={`${evidence.label} (${evidence.fieldId})`}
      >
        {segmentText}
      </mark>,
    );
  }

  return <>{segments}</>;
}

function alignmentSegmentStyle(
  alignment: AlignmentTextHighlight | undefined,
  hasEvidence: boolean,
): React.CSSProperties {
  if (!alignment) {
    return {};
  }
  const activeColor = alignment.pinned ? "#7C3AED" : "#0891B2";
  if (hasEvidence) {
    return alignment.active
      ? { outline: `2px solid ${activeColor}`, outlineOffset: 2 }
      : {};
  }
  return {
    borderRadius: 3,
    padding: "0 2px",
    backgroundColor: alignment.active ? `${activeColor}30` : "rgba(8, 145, 178, 0.12)",
    boxShadow: alignment.active ? `0 0 0 1px ${activeColor}70` : "0 0 0 1px rgba(8, 145, 178, 0.22)",
    cursor: "pointer",
  };
}

/* ── Individual block renderers ─────────────────────────── */

function HeadingBlock({
  block,
  text,
  globalStart,
  highlights,
  alignmentHighlights,
  onAlignmentHover,
  onAlignmentLeave,
  onAlignmentToggle,
}: {
  block: ContentBlock;
  text: string;
  globalStart: number;
  highlights: BlockHighlight[];
  alignmentHighlights: AlignmentTextHighlight[];
} & AlignmentHandlers) {
  const level = block.text_level ?? 2;
  const Tag = `h${Math.min(Math.max(level, 1), 6)}` as keyof React.JSX.IntrinsicElements;
  const sizes: Record<number, { fontSize: number; fontWeight: number }> = {
    1: { fontSize: 20, fontWeight: 700 },
    2: { fontSize: 17, fontWeight: 600 },
    3: { fontSize: 15, fontWeight: 600 },
    4: { fontSize: 14, fontWeight: 600 },
  };
  const style = sizes[level] ?? sizes[3];
  return (
    <Tag style={{ ...style, color: "var(--color-text)", margin: 0, lineHeight: 1.4 }}>
      <HighlightedSegment
        text={text}
        globalStart={globalStart}
        highlights={highlights}
        alignmentHighlights={alignmentHighlights}
        onAlignmentHover={onAlignmentHover}
        onAlignmentLeave={onAlignmentLeave}
        onAlignmentToggle={onAlignmentToggle}
      />
    </Tag>
  );
}

function TextBlock({
  text,
  globalStart,
  highlights,
  alignmentHighlights,
  onAlignmentHover,
  onAlignmentLeave,
  onAlignmentToggle,
}: {
  text: string;
  globalStart: number;
  highlights: BlockHighlight[];
  alignmentHighlights: AlignmentTextHighlight[];
} & AlignmentHandlers) {
  return (
    <p style={{ fontSize: 14, lineHeight: 1.7, color: "var(--color-text-strong)", margin: 0, whiteSpace: "pre-wrap" }}>
      <HighlightedSegment
        text={text}
        globalStart={globalStart}
        highlights={highlights}
        alignmentHighlights={alignmentHighlights}
        onAlignmentHover={onAlignmentHover}
        onAlignmentLeave={onAlignmentLeave}
        onAlignmentToggle={onAlignmentToggle}
      />
    </p>
  );
}

function TableBlock({
  block,
  text,
  globalStart,
  highlights,
  alignmentHighlights,
  onAlignmentHover,
  onAlignmentLeave,
  onAlignmentToggle,
}: {
  block: ContentBlock;
  text: string;
  globalStart: number;
  highlights: BlockHighlight[];
  alignmentHighlights: AlignmentTextHighlight[];
} & AlignmentHandlers) {
  return (
    <div style={{ overflowX: "auto" }}>
      {block.table_caption && block.table_caption.length > 0 && (
        <p style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text-strong)", marginBottom: 8, fontStyle: "italic" }}>
          {block.table_caption.join(" ")}
        </p>
      )}
      {block.table_body ? (
        <div
          dangerouslySetInnerHTML={{ __html: block.table_body }}
          style={{ fontSize: 13, lineHeight: 1.5 }}
        />
      ) : (
        <pre style={{
          fontSize: 13,
          lineHeight: 1.5,
          color: "var(--color-text-strong)",
          whiteSpace: "pre-wrap",
          fontFamily: "var(--font-mono)",
          backgroundColor: "var(--color-bg)",
          padding: 12,
          borderRadius: 6,
          border: "1px solid var(--color-border)",
          margin: 0,
        }}>
          <HighlightedSegment
            text={text}
            globalStart={globalStart}
            highlights={highlights}
            alignmentHighlights={alignmentHighlights}
            onAlignmentHover={onAlignmentHover}
            onAlignmentLeave={onAlignmentLeave}
            onAlignmentToggle={onAlignmentToggle}
          />
        </pre>
      )}
      {block.table_footnote && block.table_footnote.length > 0 && (
        <p style={{ fontSize: 11, color: "var(--color-text-secondary)", marginTop: 4 }}>
          {block.table_footnote.join(" ")}
        </p>
      )}
    </div>
  );
}

function ListBlock({
  block,
  globalStart,
  highlights,
  alignmentHighlights,
  onAlignmentHover,
  onAlignmentLeave,
  onAlignmentToggle,
}: {
  block: ContentBlock;
  globalStart: number;
  highlights: BlockHighlight[];
  alignmentHighlights: AlignmentTextHighlight[];
} & AlignmentHandlers) {
  const items = block.list_items ?? [];
  let offset = globalStart;
  return (
    <ul style={{ fontSize: 14, lineHeight: 1.7, color: "var(--color-text-strong)", paddingLeft: 20, margin: 0 }}>
      {items.map((item, i) => {
        const itemStart = offset;
        offset += item.length + 1; // +1 for \n
        return (
          <li key={i} style={{ marginBottom: 4 }}>
            <HighlightedSegment
              text={item}
              globalStart={itemStart}
              highlights={highlights}
              alignmentHighlights={alignmentHighlights}
              onAlignmentHover={onAlignmentHover}
              onAlignmentLeave={onAlignmentLeave}
              onAlignmentToggle={onAlignmentToggle}
            />
          </li>
        );
      })}
    </ul>
  );
}

function FigureBlock({
  block,
  globalStart,
  highlights,
  alignmentHighlights,
  onAlignmentHover,
  onAlignmentLeave,
  onAlignmentToggle,
}: {
  block: ContentBlock;
  globalStart: number;
  highlights: BlockHighlight[];
  alignmentHighlights: AlignmentTextHighlight[];
} & AlignmentHandlers) {
  const captions = block.image_caption ?? block.chart_caption ?? [];
  return (
    <figure style={{ margin: 0 }}>
      {block.img_path && (
        <div style={{
          backgroundColor: "var(--color-bg-muted)",
          borderRadius: 8,
          padding: 24,
          textAlign: "center",
          color: "var(--color-text-secondary)",
          fontSize: 13,
          marginBottom: 8,
        }}>
          📊 {block.sub_type || "Figure"}
        </div>
      )}
      {captions.length > 0 && (
        <figcaption style={{ fontSize: 13, color: "var(--color-text-strong)", fontStyle: "italic", lineHeight: 1.5 }}>
          {captions.join(" ")}
        </figcaption>
      )}
      {block.content && (
        <p style={{ fontSize: 13, color: "var(--color-text-strong)", marginTop: 4 }}>
          <HighlightedSegment
            text={block.content}
            globalStart={globalStart}
            highlights={highlights}
            alignmentHighlights={alignmentHighlights}
            onAlignmentHover={onAlignmentHover}
            onAlignmentLeave={onAlignmentLeave}
            onAlignmentToggle={onAlignmentToggle}
          />
        </p>
      )}
    </figure>
  );
}

function CodeBlock({ block }: { block: ContentBlock }) {
  return (
    <div>
      {block.code_caption && block.code_caption.length > 0 && (
        <p style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text-strong)", marginBottom: 4 }}>
          {block.code_caption.join(" ")}
        </p>
      )}
      <pre style={{
        fontSize: 13,
        lineHeight: 1.5,
        fontFamily: "var(--font-mono)",
        backgroundColor: "var(--color-code-text)",
        color: "var(--color-border)",
        padding: 16,
        borderRadius: 8,
        overflowX: "auto",
        margin: 0,
      }}>
        {block.code_body ?? block.text ?? ""}
      </pre>
    </div>
  );
}

function EquationBlock({ block }: { block: ContentBlock }) {
  return (
    <div style={{
      textAlign: "center",
      padding: "12px 0",
      fontSize: 15,
      fontStyle: "italic",
      color: "var(--color-text-strong)",
    }}>
      {block.text ?? ""}
    </div>
  );
}

function MetaBlock({ block }: { block: ContentBlock }) {
  // header, footer, page_number, aside_text, page_footnote
  return (
    <p style={{
      fontSize: 11,
      color: "var(--color-text-muted)",
      fontStyle: "italic",
      margin: 0,
    }}>
      {block.text ?? ""}
    </p>
  );
}

/* ── Main Renderer ──────────────────────────────────────── */

export function StructuredBlockRenderer({
  blocks,
  highlights,
  alignmentHighlights = [],
  onAlignmentHover,
  onAlignmentLeave,
  onAlignmentToggle,
}: {
  blocks: ContentBlock[];
  highlights: BlockHighlight[];
  alignmentHighlights?: AlignmentTextHighlight[];
} & AlignmentHandlers) {
  const blockRanges = useMemo(() => buildBlockRanges(blocks), [blocks]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {blockRanges.map((br, index) => {
        const { block, globalOffset, text } = br;
        if (!text.trim()) return null;

        // Filter highlights relevant to this block
        const blockHighlights = highlights.filter(
          (h) => h.globalStart < globalOffset + text.length && h.globalEnd > globalOffset,
        );
        const blockAlignmentHighlights = alignmentHighlights.filter(
          (h) => h.start < globalOffset + text.length && h.end > globalOffset,
        );

        const props = {
          block,
          text,
          globalStart: globalOffset,
          highlights: blockHighlights,
          alignmentHighlights: blockAlignmentHighlights,
          onAlignmentHover,
          onAlignmentLeave,
          onAlignmentToggle,
        };

        switch (block.type) {
          case "title":
            return <div key={index}><HeadingBlock {...props} /></div>;
          case "table":
            return <div key={index}><TableBlock {...props} /></div>;
          case "list":
            return <div key={index}><ListBlock {...props} /></div>;
          case "image":
          case "chart":
            return <div key={index}><FigureBlock {...props} /></div>;
          case "code":
            return <div key={index}><CodeBlock {...props} /></div>;
          case "equation":
            return <div key={index}><EquationBlock {...props} /></div>;
          case "header":
          case "footer":
          case "page_number":
          case "aside_text":
          case "page_footnote":
            return <div key={index}><MetaBlock {...props} /></div>;
          default:
            return <div key={index}><TextBlock {...props} /></div>;
        }
      })}
    </div>
  );
}
