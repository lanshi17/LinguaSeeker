import { useEffect, useRef } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import "katex/dist/katex.min.css";
import { categoryLabel } from "../utils/categoryStyles";
import { CATEGORY_COLORS, type EvidenceDocumentHighlight } from "../utils/evidenceDocument";
import type { AlignmentTextHighlight } from "../utils/translationAlignment";
import { AnnotationLayer, type FieldTypeOption } from "./annotationLayer";
import { openFieldReviewMenu } from "./fieldReviewMenuBus";
import type { ReviewContextMap } from "./fieldReviewMenuBus";
import type { AnnotationTrack, UserAnnotation } from "../types/annotations";

type AnnotationOperation = void | Promise<void>;

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
  reviewContexts?: ReviewContextMap;
  alignmentHighlights?: AlignmentTextHighlight[];
  onAlignmentHover?: (pairId: string) => void;
  onAlignmentLeave?: () => void;
  onAlignmentToggle?: (pairId: string) => void;
  onCreateAnnotation?: (payload: {
    paragraph_id: string;
    track: AnnotationTrack;
    start_offset: number;
    end_offset: number;
    color: string;
  }) => AnnotationOperation;
  onUpdateAnnotation?: (
    id: string,
    payload: { color?: string | null; note?: string | null },
  ) => AnnotationOperation;
  onDeleteAnnotation?: (id: string) => AnnotationOperation;
  onAssignField?: (selectedText: string, fieldType: string) => AnnotationOperation;
  fieldTypes?: FieldTypeOption[];
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
  mark.style.backgroundColor = hex ? hex + "40" : "var(--color-border)";
  mark.style.color = hex ? hex : "var(--color-text)";
  mark.style.boxShadow = hex ? `0 0 0 1px ${hex}50` : "0 0 0 1px var(--color-text-muted)";
  if (selected) {
    mark.style.outline = "2px solid var(--color-primary-700, #0e7490)";
    mark.style.outlineOffset = "2px";
  }
}

function applyAlignmentStyle(element: HTMLElement, alignment: AlignmentTextHighlight, hasEvidence: boolean) {
  const activeColor = alignment.pinned ? "#7C3AED" : "#0891B2";
  element.dataset.alignmentPairId = alignment.pairId;
  element.dataset.alignmentActive = alignment.active ? "true" : "false";
  element.addEventListener("mouseenter", () => {
    element.dispatchEvent(new CustomEvent("alignment-hover", {
      bubbles: true,
      detail: alignment.pairId,
    }));
  });
  element.addEventListener("mouseleave", () => {
    element.dispatchEvent(new CustomEvent("alignment-leave", { bubbles: true }));
  });
  element.addEventListener("click", () => {
    element.dispatchEvent(new CustomEvent("alignment-toggle", {
      bubbles: true,
      detail: alignment.pairId,
    }));
  });
  if (hasEvidence) {
    if (alignment.active) {
      element.style.outline = `2px solid ${activeColor}`;
      element.style.outlineOffset = "2px";
    }
    return;
  }
  element.style.borderRadius = "3px";
  element.style.padding = "0 2px";
  element.style.backgroundColor = alignment.active ? `${activeColor}30` : "rgba(8, 145, 178, 0.12)";
  element.style.boxShadow = alignment.active ? `0 0 0 1px ${activeColor}70` : "0 0 0 1px rgba(8, 145, 178, 0.22)";
  element.style.cursor = "pointer";
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
  reviewContexts,
  alignmentHighlights = [],
  onAlignmentHover,
  onAlignmentLeave,
  onAlignmentToggle,
  onCreateAnnotation,
  onUpdateAnnotation,
  onDeleteAnnotation,
  onAssignField,
  fieldTypes,
}: MarkdownDocumentViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // ---- Evidence highlight pass (raw-Markdown offsets) ----
  useEffect(() => {
    const el = containerRef.current;
    if (!el || (highlights.length === 0 && alignmentHighlights.length === 0)) return;

    const handleAlignmentHover = (event: Event) => {
      onAlignmentHover?.((event as CustomEvent<string>).detail);
    };
    const handleAlignmentLeave = () => {
      onAlignmentLeave?.();
    };
    const handleAlignmentToggle = (event: Event) => {
      onAlignmentToggle?.((event as CustomEvent<string>).detail);
    };
    el.addEventListener("alignment-hover", handleAlignmentHover);
    el.addEventListener("alignment-leave", handleAlignmentLeave);
    el.addEventListener("alignment-toggle", handleAlignmentToggle);

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
      const evidenceCovering: Array<{ hlIndex: number; start: number; end: number }> = [];
      const alignmentCovering: Array<{ hlIndex: number; start: number; end: number }> = [];

      for (let hi = 0; hi < highlights.length; hi++) {
        const hl = highlights[hi];
        if (hl.end <= nodeStart || hl.start >= nodeEnd) continue;

        const localStart = Math.max(0, hl.start - nodeStart);
        const localEnd = Math.min(content.length, hl.end - nodeStart);
        if (localEnd <= localStart) continue;

        if (localStart > 0) splitSet.add(localStart);
        if (localEnd < content.length) splitSet.add(localEnd);
        evidenceCovering.push({ hlIndex: hi, start: localStart, end: localEnd });
      }

      for (let hi = 0; hi < alignmentHighlights.length; hi++) {
        const alignment = alignmentHighlights[hi];
        if (alignment.end <= nodeStart || alignment.start >= nodeEnd) continue;

        const localStart = Math.max(0, alignment.start - nodeStart);
        const localEnd = Math.min(content.length, alignment.end - nodeStart);
        if (localEnd <= localStart) continue;

        if (localStart > 0) splitSet.add(localStart);
        if (localEnd < content.length) splitSet.add(localEnd);
        alignmentCovering.push({ hlIndex: hi, start: localStart, end: localEnd });
      }

      if (evidenceCovering.length === 0 && alignmentCovering.length === 0) continue;

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
        const evidenceCover = evidenceCovering.find(
          (c) => c.start < seg.end && c.end > seg.start,
        );
        const alignmentCover = alignmentCovering.find(
          (c) => c.start < seg.end && c.end > seg.start,
        );
        if (!evidenceCover && !alignmentCover) continue;
        if (!seg.node.parentNode) continue;

        const element = evidenceCover
          ? document.createElement("mark")
          : document.createElement("span");
        if (evidenceCover) {
          const hl = highlights[evidenceCover.hlIndex];
          const reviewInfo = reviewContexts?.get(hl.evidenceId);
          applyMarkStyle(element, hl.category, hl.selected);
          element.setAttribute(
            "aria-label",
            `${categoryLabel(hl.category)} evidence: ${hl.label}`,
          );
          element.dataset.evidenceId = hl.evidenceId;
          if (reviewInfo) {
            element.dataset.reviewable = "true";
            element.style.cursor = "pointer";
            element.addEventListener("click", (event) => {
              openFieldReviewMenu(event, reviewInfo);
            });
            element.addEventListener("contextmenu", (event) => {
              openFieldReviewMenu(event, reviewInfo);
            });
          }
        }
        if (alignmentCover) {
          applyAlignmentStyle(
            element,
            alignmentHighlights[alignmentCover.hlIndex],
            Boolean(evidenceCover),
          );
        }
        seg.node.parentNode.insertBefore(element, seg.node);
        element.appendChild(seg.node);
        marks.push(element);
      }
    }

    return () => {
      el.removeEventListener("alignment-hover", handleAlignmentHover);
      el.removeEventListener("alignment-leave", handleAlignmentLeave);
      el.removeEventListener("alignment-toggle", handleAlignmentToggle);
      for (const mark of marks) {
        if (!mark.parentNode) continue;
        while (mark.firstChild) {
          mark.parentNode.insertBefore(mark.firstChild, mark);
        }
        mark.parentNode.removeChild(mark);
      }
    };
  }, [
    markdown,
    highlights,
    reviewContexts,
    alignmentHighlights,
    onAlignmentHover,
    onAlignmentLeave,
    onAlignmentToggle,
  ]);

  return (
    <div
      ref={containerRef}
      className="edb-markdown-viewer"
      data-paragraph-id={paragraphId}
      style={{ position: "relative" }}
    >
      <style>{`
        .edb-markdown-viewer table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 13px; }
        .edb-markdown-viewer th, .edb-markdown-viewer td { border: 1px solid var(--color-text-muted); padding: 6px 10px; text-align: left; vertical-align: top; }
        .edb-markdown-viewer th { background-color: var(--color-bg-muted); font-weight: 600; }
        .edb-markdown-viewer tr:nth-child(even) td { background-color: var(--color-bg); }
      `}</style>
      <Markdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeRaw, rehypeKatex]}
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
        recomputeDeps={[markdown, highlights, alignmentHighlights]}
        onCreateAnnotation={onCreateAnnotation}
        onUpdateAnnotation={onUpdateAnnotation}
        onDeleteAnnotation={onDeleteAnnotation}
        onAssignField={onAssignField}
        fieldTypes={fieldTypes}
      />
    </div>
  );
}
