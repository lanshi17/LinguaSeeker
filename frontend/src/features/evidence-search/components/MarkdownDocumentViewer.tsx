import { useEffect, useRef } from "react";
import Markdown from "react-markdown";
import { categoryLabel } from "../utils/categoryStyles";
import { CATEGORY_COLORS, type EvidenceDocumentHighlight } from "../utils/evidenceDocument";

interface MarkdownDocumentViewerProps {
  markdown: string;
  highlights: EvidenceDocumentHighlight[];
}

/** Derive mark inline styles from a category's hex color. */
function applyMarkStyle(mark: HTMLElement, category?: string | null, selected?: boolean) {
  const hex = category ? CATEGORY_COLORS[category]?.hex : undefined;
  mark.style.borderRadius = "4px";
  mark.style.padding = "2px 4px";
  mark.style.fontWeight = "600";
  mark.style.backgroundColor = hex ? hex + "40" : "#e5e7eb";
  mark.style.color = hex ? hex : "#030712";
  mark.style.boxShadow = hex ? `0 0 0 1px ${hex}50` : "0 0 0 1px #d1d5db";
  if (selected) {
    mark.style.outline = "2px solid var(--color-primary-700, #0e7490)";
    mark.style.outlineOffset = "2px";
  }
}

/**
 * Render markdown content with evidence highlight overlays.
 *
 * Highlights are positioned by character offsets in the raw (pre-render) text.
 * After react-markdown renders the DOM, we walk text nodes to map rendered
 * positions back to raw positions, then wrap matching ranges with `<mark>`.
 */
export function MarkdownDocumentViewer({
  markdown,
  highlights,
}: MarkdownDocumentViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || highlights.length === 0) return;

    // Collect text nodes in document order.
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
    const textNodes: Text[] = [];
    let walkNode: Text | null;
    while ((walkNode = walker.nextNode() as Text | null)) {
      if (walkNode.textContent) textNodes.push(walkNode);
    }

    const marks: HTMLElement[] = [];

    // Walk text nodes and, for each one, plan every split offset required by
    // the overlapping highlights. Apply splits in descending order so that
    // earlier (smaller) offsets remain valid after later (larger) splits.
    let rawPos = 0;

    for (const textNode of textNodes) {
      const content = textNode.textContent ?? "";
      if (!content) continue;

      const idx = markdown.indexOf(content, rawPos);
      if (idx < 0) continue;

      const nodeStart = idx;
      const nodeEnd = idx + content.length;
      rawPos = nodeEnd;

      // Plan: collect every distinct split offset inside this text node,
      // and which highlights cover each resulting segment.
      const splitSet = new Set<number>();
      const covering: Array<{ hlIndex: number; start: number; end: number }> = [];

      for (let hi = 0; hi < highlights.length; hi++) {
        const hl = highlights[hi];
        if (hl.end <= nodeStart || hl.start >= nodeEnd) continue;

        const localStart = Math.max(0, hl.start - nodeStart);
        const localEnd = Math.min(content.length, hl.end - nodeStart);
        if (localEnd <= localStart) continue;

        if (localStart > 0) splitSet.add(localStart);
        if (localEnd < content.length) splitSet.add(localEnd);
        covering.push({ hlIndex: hi, start: localStart, end: localEnd });
      }

      if (covering.length === 0) continue;

      const splits = Array.from(splitSet).sort((a, b) => a - b);

      // Apply splits from largest offset to smallest so each splitText call
      // operates on a node whose length still exceeds the offset.
      for (let i = splits.length - 1; i >= 0; i--) {
        const offset = splits[i];
        const currentLength = textNode.length; // live; reflects prior splits
        if (offset <= 0 || offset >= currentLength) continue;
        textNode.splitText(offset);
      }

      // After splitting, `textNode` holds [0, splits[0]), its next sibling
      // holds [splits[0], splits[1]), etc. Walk segments in document order.
      const segments: Array<{ node: Text; start: number; end: number }> = [];
      let cursor: Text | null = textNode;
      let segmentStart = 0;
      const boundaries = [...splits, content.length];

      for (const boundary of boundaries) {
        if (!cursor) break;
        if (boundary <= segmentStart) {
          cursor = cursor.nextSibling as Text | null;
          continue;
        }
        segments.push({ node: cursor, start: segmentStart, end: boundary });
        segmentStart = boundary;
        cursor = cursor.nextSibling as Text | null;
      }

      // Wrap each segment in a single <mark> for the first covering highlight.
      // Overlapping highlights share segments; we pick the topmost to keep the
      // DOM flat and avoid the IndexSizeError that occurs when a second
      // highlight tries to split a node already shortened by the first.
      for (const seg of segments) {
        const cover = covering.find(
          (c) => c.start < seg.end && c.end > seg.start,
        );
        if (!cover) continue;
        if (!seg.node.parentNode) continue;

        const hl = highlights[cover.hlIndex];
        const mark = document.createElement("mark");
        applyMarkStyle(mark, hl.category, hl.selected);
        mark.setAttribute(
          "aria-label",
          `${categoryLabel(hl.category)} evidence: ${hl.label}`,
        );
        mark.dataset.evidenceId = hl.evidenceId;
        seg.node.parentNode.insertBefore(mark, seg.node);
        mark.appendChild(seg.node);
        marks.push(mark);
      }
    }

    return () => {
      for (const mark of marks) {
        if (!mark.parentNode) continue;
        while (mark.firstChild) {
          mark.parentNode.insertBefore(mark.firstChild, mark);
        }
        mark.parentNode.removeChild(mark);
      }
    };
  }, [markdown, highlights]);

  return (
    <>
      <style>{`
        .edb-markdown-viewer {
          max-width: none;
          font-size: 14px;
          line-height: 1.75;
          color: #1f2937;
        }
        .edb-markdown-viewer h1,
        .edb-markdown-viewer h2,
        .edb-markdown-viewer h3,
        .edb-markdown-viewer h4,
        .edb-markdown-viewer h5,
        .edb-markdown-viewer h6 {
          color: #111827;
          font-weight: 600;
          margin-top: 1.5em;
          margin-bottom: 0.5em;
        }
        .edb-markdown-viewer h1 { font-size: 1.5em; }
        .edb-markdown-viewer h2 { font-size: 1.25em; }
        .edb-markdown-viewer h3 { font-size: 1.1em; }
        .edb-markdown-viewer p {
          color: #1f2937;
          line-height: 1.75;
          margin-top: 0.75em;
          margin-bottom: 0.75em;
        }
        .edb-markdown-viewer a {
          color: var(--color-primary-700, #0e7490);
          text-decoration: underline;
        }
        .edb-markdown-viewer strong {
          color: #111827;
          font-weight: 700;
        }
        .edb-markdown-viewer code {
          color: #be185d;
          background: #f3f4f6;
          padding: 2px 4px;
          border-radius: 4px;
          font-size: 12px;
        }
        .edb-markdown-viewer pre code {
          display: block;
          padding: 12px;
          overflow-x: auto;
        }
        .edb-markdown-viewer li {
          color: #1f2937;
          margin-top: 0.25em;
          margin-bottom: 0.25em;
        }
        .edb-markdown-viewer ul,
        .edb-markdown-viewer ol {
          padding-left: 1.5em;
          margin-top: 0.5em;
          margin-bottom: 0.5em;
        }
        .edb-markdown-viewer table {
          font-size: 14px;
          width: 100%;
          border-collapse: collapse;
          margin-top: 1em;
          margin-bottom: 1em;
        }
        .edb-markdown-viewer th,
        .edb-markdown-viewer td {
          border: 1px solid #e5e7eb;
          padding: 6px 12px;
          text-align: left;
        }
        .edb-markdown-viewer th {
          background: #f9fafb;
          font-weight: 600;
        }
        .edb-markdown-viewer blockquote {
          border-left: 3px solid #d1d5db;
          padding-left: 1em;
          margin-left: 0;
          color: #6b7280;
        }
      `}</style>
      <div
        ref={containerRef}
        className="edb-markdown-viewer"
      >
        <Markdown>{markdown}</Markdown>
      </div>
    </>
  );
}
