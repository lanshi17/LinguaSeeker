import { useMemo } from "react";
import type { ContentBlock } from "@/features/evidence-search/types/evidenceSearch";
import { CATEGORY_COLORS } from "@/features/evidence-search/utils/evidenceDocument";

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
}: {
  text: string;
  globalStart: number;
  highlights: BlockHighlight[];
}) {
  const localHighlights = useMemo(() => {
    return highlights
      .map((h) => {
        const start = Math.max(0, h.globalStart - globalStart);
        const end = Math.min(text.length, h.globalEnd - globalStart);
        if (start >= text.length || end <= 0 || start >= end) return null;
        return { ...h, start, end };
      })
      .filter(Boolean)
      .sort((a, b) => a!.start - b!.start);
  }, [text, globalStart, highlights]);

  if (localHighlights.length === 0) {
    return <>{text}</>;
  }

  const segments: React.ReactNode[] = [];
  let cursor = 0;

  for (const hl of localHighlights) {
    if (!hl) continue;
    if (cursor < hl.start) {
      segments.push(<span key={`p-${cursor}`}>{text.slice(cursor, hl.start)}</span>);
    }
    const hex = hl.category && CATEGORY_COLORS[hl.category]
      ? CATEGORY_COLORS[hl.category].hex
      : "#9CA3AF";
    segments.push(
      <mark
        key={`h-${hl.evidenceId}-${hl.start}`}
        style={{
          backgroundColor: `${hex}50`,
          color: `${hex}f0`,
          boxShadow: `0 0 0 1px ${hex}60`,
          borderRadius: 2,
          padding: "0 2px",
          cursor: "help",
        }}
        title={`${hl.label} (${hl.fieldId})`}
      >
        {text.slice(hl.start, hl.end)}
      </mark>,
    );
    cursor = hl.end;
  }

  if (cursor < text.length) {
    segments.push(<span key={`t-${cursor}`}>{text.slice(cursor)}</span>);
  }

  return <>{segments}</>;
}

/* ── Individual block renderers ─────────────────────────── */

function HeadingBlock({
  block,
  text,
  globalStart,
  highlights,
}: {
  block: ContentBlock;
  text: string;
  globalStart: number;
  highlights: BlockHighlight[];
}) {
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
    <Tag style={{ ...style, color: "#111827", margin: 0, lineHeight: 1.4 }}>
      <HighlightedSegment text={text} globalStart={globalStart} highlights={highlights} />
    </Tag>
  );
}

function TextBlock({
  text,
  globalStart,
  highlights,
}: {
  text: string;
  globalStart: number;
  highlights: BlockHighlight[];
}) {
  return (
    <p style={{ fontSize: 14, lineHeight: 1.7, color: "#374151", margin: 0, whiteSpace: "pre-wrap" }}>
      <HighlightedSegment text={text} globalStart={globalStart} highlights={highlights} />
    </p>
  );
}

function TableBlock({
  block,
  text,
  globalStart,
  highlights,
}: {
  block: ContentBlock;
  text: string;
  globalStart: number;
  highlights: BlockHighlight[];
}) {
  return (
    <div style={{ overflowX: "auto" }}>
      {block.table_caption && block.table_caption.length > 0 && (
        <p style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 8, fontStyle: "italic" }}>
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
          color: "#374151",
          whiteSpace: "pre-wrap",
          fontFamily: "var(--font-mono)",
          backgroundColor: "#f9fafb",
          padding: 12,
          borderRadius: 6,
          border: "1px solid #e5e7eb",
          margin: 0,
        }}>
          <HighlightedSegment text={text} globalStart={globalStart} highlights={highlights} />
        </pre>
      )}
      {block.table_footnote && block.table_footnote.length > 0 && (
        <p style={{ fontSize: 11, color: "#6b7280", marginTop: 4 }}>
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
}: {
  block: ContentBlock;
  globalStart: number;
  highlights: BlockHighlight[];
}) {
  const items = block.list_items ?? [];
  let offset = globalStart;
  return (
    <ul style={{ fontSize: 14, lineHeight: 1.7, color: "#374151", paddingLeft: 20, margin: 0 }}>
      {items.map((item, i) => {
        const itemStart = offset;
        offset += item.length + 1; // +1 for \n
        return (
          <li key={i} style={{ marginBottom: 4 }}>
            <HighlightedSegment text={item} globalStart={itemStart} highlights={highlights} />
          </li>
        );
      })}
    </ul>
  );
}

function FigureBlock({
  block,
  text,
  globalStart,
  highlights,
}: {
  block: ContentBlock;
  text: string;
  globalStart: number;
  highlights: BlockHighlight[];
}) {
  const captions = block.image_caption ?? block.chart_caption ?? [];
  return (
    <figure style={{ margin: 0 }}>
      {block.img_path && (
        <div style={{
          backgroundColor: "#f3f4f6",
          borderRadius: 8,
          padding: 24,
          textAlign: "center",
          color: "#6b7280",
          fontSize: 13,
          marginBottom: 8,
        }}>
          📊 {block.sub_type || "Figure"}
        </div>
      )}
      {captions.length > 0 && (
        <figcaption style={{ fontSize: 13, color: "#374151", fontStyle: "italic", lineHeight: 1.5 }}>
          {captions.join(" ")}
        </figcaption>
      )}
      {block.content && (
        <p style={{ fontSize: 13, color: "#4b5563", marginTop: 4 }}>
          <HighlightedSegment text={block.content} globalStart={globalStart} highlights={highlights} />
        </p>
      )}
    </figure>
  );
}

function CodeBlock({ block }: { block: ContentBlock }) {
  return (
    <div>
      {block.code_caption && block.code_caption.length > 0 && (
        <p style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 4 }}>
          {block.code_caption.join(" ")}
        </p>
      )}
      <pre style={{
        fontSize: 13,
        lineHeight: 1.5,
        fontFamily: "var(--font-mono)",
        backgroundColor: "#1f2937",
        color: "#e5e7eb",
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
      color: "#374151",
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
      color: "#9ca3af",
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
}: {
  blocks: ContentBlock[];
  highlights: BlockHighlight[];
}) {
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

        const props = { block, text, globalStart: globalOffset, highlights: blockHighlights };

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
