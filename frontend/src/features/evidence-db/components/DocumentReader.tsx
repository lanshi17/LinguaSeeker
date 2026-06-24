import { useRef } from "react";
import { Languages, BookOpen } from "lucide-react";
import type { EvidenceDocument } from "@/features/evidence-search/utils/evidenceDocument";
import type { ContentBlock } from "@/features/evidence-search/types/evidenceSearch";
import { HighlightedText } from "./HighlightedText";
import { StructuredBlockRenderer, type BlockHighlight } from "./StructuredBlockRenderer";
import { MarkdownDocumentViewer } from "@/features/evidence-search/components/MarkdownDocumentViewer";
import { AnnotationLayer } from "@/features/evidence-search/components/annotationLayer";
import type { AnnotationTrack, UserAnnotation } from "@/features/evidence-search/types/annotations";

/** Shared CRUD handler shape for user annotations. */
interface AnnotationHandlers {
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

/* ── Document Reader Panel ──────────────────────────────── */

export function DocumentReader({
  title,
  track,
  document,
  accentColor,
  blocks,
  blockHighlights,
  sourceDocumentId,
  annotations = [],
  onCreateAnnotation,
  onUpdateAnnotation,
  onDeleteAnnotation,
}: {
  title: string;
  track: AnnotationTrack;
  document: EvidenceDocument;
  accentColor: string;
  /** Structured blocks for formatted rendering (preferred over flat paragraphs). */
  blocks?: ContentBlock[] | null;
  /** Highlights mapped to global character offsets for block rendering. */
  blockHighlights?: BlockHighlight[];
  /** Source document id — used to resolve relative image paths. */
  sourceDocumentId?: string;
  /** User-authored annotations for this track's document. */
  annotations?: UserAnnotation[];
} & AnnotationHandlers) {
  const contentRef = useRef<HTMLDivElement>(null);
  const hasBlocks = blocks && blocks.length > 0;
  // The whole document (structured blocks or flat paragraphs) is one
  // annotation unit anchored to the rendered visible text of this panel.
  const paragraphId = `${track}-document`;
  const docAnnotations = annotations.filter((a) => a.paragraph_id === paragraphId);
  const fullTextPara = document.paragraphs.find((p) => p.id.endsWith("-full-text"));
  const snippetParas = fullTextPara
    ? document.paragraphs.filter((p) => p !== fullTextPara)
    : document.paragraphs;


  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      borderRadius: 12,
      border: "1px solid #e5e7eb",
      backgroundColor: "#fff",
      overflow: "hidden",
    }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "10px 16px",
          borderBottom: "1px solid #f3f4f6",
          backgroundColor: `${accentColor}08`,
        }}
      >
        <Languages style={{ width: 16, height: 16, color: accentColor }} />
        <h3 style={{ fontSize: 14, fontWeight: 600, color: "#1f2937", margin: 0 }}>{title}</h3>
        <span style={{
          marginLeft: "auto",
          fontSize: 11,
          textTransform: "capitalize",
          color: "#6b7280",
        }}>
          {track} track{hasBlocks ? " · structured" : ""}
        </span>
      </div>
      <div
        ref={contentRef}
        className="edb-scroll"
        style={{ maxHeight: 600, overflowY: "auto", padding: 16, position: "relative" }}
      >
        {hasBlocks ? (
          <StructuredBlockRenderer blocks={blocks} highlights={blockHighlights ?? []} />
        ) : document.paragraphs.length === 0 ? (
          <div style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "48px 0",
            textAlign: "center",
          }}>
            <BookOpen style={{ width: 32, height: 32, color: "#9ca3af", marginBottom: 8 }} />
            <p style={{ fontSize: 14, color: "#6b7280", margin: 0 }}>
              No {track} text available
            </p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {fullTextPara && (
              <MarkdownDocumentViewer
                markdown={fullTextPara.text}
                highlights={fullTextPara.highlights}
                paragraphId={fullTextPara.id}
                track={track}
                sourceDocumentId={sourceDocumentId}
              />
            )}
            {snippetParas.map((para) => (
              <div key={para.id} style={{ position: "relative" }}>
                {para.page && (
                  <span style={{
                    position: "absolute",
                    left: -8,
                    top: 0,
                    fontSize: 10,
                    color: "#9ca3af",
                    fontFamily: "var(--font-mono)",
                  }}>
                    p.{para.page}
                  </span>
                )}
                <HighlightedText paragraph={para} />
              </div>
            ))}
          </div>
        )}
        <AnnotationLayer
          containerRef={contentRef}
          paragraphId={paragraphId}
          track={track}
          annotations={docAnnotations}
          recomputeDeps={[blocks, blockHighlights, document]}
          onCreateAnnotation={onCreateAnnotation}
          onUpdateAnnotation={onUpdateAnnotation}
          onDeleteAnnotation={onDeleteAnnotation}
        />
      </div>
    </div>
  );
}
