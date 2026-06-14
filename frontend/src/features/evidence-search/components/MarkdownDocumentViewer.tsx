"use client";

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

    // Collect text nodes in document order
    const walker = document.createTreeWalker(
      el,
      NodeFilter.SHOW_TEXT,
      null,
    );
    const textNodes: Text[] = [];
    let node: Text | null;
    while ((node = walker.nextNode() as Text | null)) {
      if (node.textContent) textNodes.push(node);
    }

    // Map each text node's rendered content to a position in the raw text.
    // Markdown syntax (##, **, [], etc.) is stripped in the DOM, so we search
    // for each DOM text substring in the raw text to find the true offset.
    let rawPos = 0;
    const marks: HTMLElement[] = [];

    for (const textNode of textNodes) {
      const content = textNode.textContent ?? "";
      if (!content) continue;

      const idx = markdown.indexOf(content, rawPos);
      if (idx < 0) continue;

      const nodeStart = idx;
      const nodeEnd = idx + content.length;
      rawPos = nodeEnd;

      // Find highlights that overlap with this text node
      for (const hl of highlights) {
        if (hl.end <= nodeStart || hl.start >= nodeEnd) continue;

        const localStart = Math.max(0, hl.start - nodeStart);
        const localEnd = Math.min(content.length, hl.end - nodeStart);
        if (localEnd <= localStart) continue;

        // Split the text node at highlight boundaries
        if (localEnd < content.length) {
          textNode.splitText(localEnd);
        }
        const middleNode =
          localStart > 0 ? textNode.splitText(localStart) : textNode;

        const mark = document.createElement("mark");
        mark.className = cn(
          "rounded px-1 py-0.5 font-semibold",
          categoryMarkStyle(hl.category),
          hl.selected && "outline outline-2 outline-offset-2 outline-primary-700",
        );
        mark.setAttribute(
          "aria-label",
          `${categoryLabel(hl.category)} evidence: ${hl.label}`,
        );
        mark.dataset.evidenceId = hl.evidenceId;
        middleNode.parentNode?.insertBefore(mark, middleNode);
        mark.appendChild(middleNode);
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
