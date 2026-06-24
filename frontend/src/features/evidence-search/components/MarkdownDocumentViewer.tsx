import { useEffect, useRef } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { categoryLabel } from "../utils/categoryStyles";
import { CATEGORY_COLORS, type EvidenceDocumentHighlight } from "../utils/evidenceDocument";
import { AnnotationLayer } from "./annotationLayer";
import type { AnnotationTrack, UserAnnotation } from "../types/annotations";

interface MarkdownDocumentViewerProps {
  markdown: string;
  highlights: EvidenceDocumentHighlight[];
  /** Stable id of the paragraph this viewer renders (for annotation anchoring). */
  paragraphId: string;
  /** Which track (original/translated) — attached to created annotations. */
  track: AnnotationTrack;
  /** Source document id — used to rewrite relative image paths to the API. */
  sourceDocumentId?: string;
  /** User-authored annotations anchored to this paragraph's visible text. */
  annotations?: UserAnnotation[];
  onCreateAnnotation?: (payload: {
    paragraph_id: string;
    track: AnnotationTrack;
    start_offset: number;
    end_offset: number;
    color: string;
  }) => void;
  onUpdateAnnotation?: (
    id: string,
    payload: { color?: string | null; note?: string | null },
  ) => void;
  onDeleteAnnotation?: (id: string) => void;
}

/** Rewrite a relative image src (e.g. "images/xxx.jpg") to the document
 *  image API endpoint. Absolute URLs and data URIs are left untouched. */
function resolveImageSrc(src: string | undefined, sourceDocumentId: string): string | undefined {
  if (!src) return src;
  if (/^(https?:|data:|\/)/.test(src)) return src;
  // Relative path like "images/<hash>.jpg" → extract basename, hit API.
  const basename = src.split("/").pop() ?? src;
  const base = import.meta.env.VITE_API_BASE_URL || `${import.meta.env.BASE_URL}api/v1`;
  return `${base}/documents/${encodeURIComponent(sourceDocumentId)}/images/${encodeURIComponent(basename)}`;
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
 * Render markdown content (GFM tables, LaTeX math via KaTeX) with evidence
 * highlight overlays, plus an optional user-annotation layer.
 *
 * Evidence highlights use raw-Markdown character offsets: after react-markdown
 * renders the DOM, text nodes are walked and mapped back to raw positions via
 * `indexOf`, then matching ranges are wrapped with `<mark>`. User annotations
 * use a separate visible-text offset coordinate system rendered as absolutely
 * positioned overlay divs (see AnnotationLayer) — the two never share DOM
 * mutations, so they coexist without conflict.
 */
export function MarkdownDocumentViewer({
  markdown,
  highlights,
  paragraphId,
  track,
  sourceDocumentId,
  annotations = [],
  onCreateAnnotation,
  onUpdateAnnotation,
  onDeleteAnnotation,
}: MarkdownDocumentViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // ---- Evidence highlight pass (raw-Markdown offsets) ----
  useEffect(() => {
    const el = containerRef.current;
    if (!el || highlights.length === 0) return;

    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
    const textNodes: Text[] = [];
    let walkNode: Text | null;
    while ((walkNode = walker.nextNode() as Text | null)) {
      if (walkNode.textContent) textNodes.push(walkNode);
    }

    const marks: HTMLElement[] = [];
    let rawPos = 0;

    for (const textNode of textNodes) {
      const content = textNode.textContent ?? "";
      if (!content) continue;

      const idx = markdown.indexOf(content, rawPos);
      if (idx < 0) continue;

      const nodeStart = idx;
      const nodeEnd = idx + content.length;
      rawPos = nodeEnd;

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

      for (let i = splits.length - 1; i >= 0; i--) {
        const offset = splits[i];
        const currentLength = textNode.length;
        if (offset <= 0 || offset >= currentLength) continue;
        textNode.splitText(offset);
      }

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
    <div
      ref={containerRef}
      className="edb-markdown-viewer"
      data-paragraph-id={paragraphId}
      style={{ position: "relative" }}
    >
      <Markdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={
          sourceDocumentId
            ? {
                img: ({ src, alt, ...rest }) => {
                  const resolved = resolveImageSrc(src, sourceDocumentId);
                  return <img src={resolved} alt={alt} {...rest} />;
                },
              }
            : undefined
        }
      >
        {markdown}
      </Markdown>
      <AnnotationLayer
        containerRef={containerRef}
        paragraphId={paragraphId}
        track={track}
        annotations={annotations}
        recomputeDeps={[markdown, highlights]}
        onCreateAnnotation={onCreateAnnotation}
        onUpdateAnnotation={onUpdateAnnotation}
        onDeleteAnnotation={onDeleteAnnotation}
      />
    </div>
  );
}
