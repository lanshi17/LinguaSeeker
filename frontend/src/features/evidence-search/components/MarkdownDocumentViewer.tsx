
import { useEffect, useRef } from "react";
import Markdown from "react-markdown";
import { cn } from "@/lib/utils/cn";
import { categoryMarkStyle, categoryLabel } from "../utils/categoryStyles";
import type { EvidenceDocumentHighlight } from "../utils/evidenceDocument";

interface MarkdownDocumentViewerProps {
  markdown: string;
  highlights: EvidenceDocumentHighlight[];
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
        mark.className = cn(
          "rounded px-1 py-0.5 font-semibold",
          categoryMarkStyle(hl.category),
          hl.selected &&
            "outline outline-2 outline-offset-2 outline-primary-700",
        );
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
    <div
      ref={containerRef}
      className="prose prose-sm max-w-none prose-headings:text-gray-900 prose-p:text-gray-800 prose-p:leading-7 prose-a:text-primary-700 prose-strong:text-gray-900 prose-code:text-pink-700 prose-code:bg-gray-100 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-li:text-gray-800 prose-table:text-sm"
    >
      <Markdown>{markdown}</Markdown>
    </div>
  );
}
