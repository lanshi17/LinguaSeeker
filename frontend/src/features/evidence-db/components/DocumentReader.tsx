import { useRef, type MutableRefObject, type UIEvent } from "react";
import { Languages, BookOpen } from "lucide-react";
import type { EvidenceDocument } from "@/features/evidence-search/utils/evidenceDocument";
import type { ContentBlock } from "@/features/evidence-search/types/evidenceSearch";
import { HighlightedText } from "./HighlightedText";
import { StructuredBlockRenderer, type BlockHighlight } from "./StructuredBlockRenderer";
import { MarkdownDocumentViewer } from "@/features/evidence-search/components/MarkdownDocumentViewer";
import { AnnotationLayer, type FieldTypeOption } from "@/features/evidence-search/components/annotationLayer";
import type { ReviewContextMap } from "@/features/evidence-search/components/fieldReviewMenuBus";
import type { AnnotationTrack, UserAnnotation } from "@/features/evidence-search/types/annotations";
import type {
  AlignmentHighlightMap,
  AlignmentTextHighlight,
} from "@/features/evidence-search/utils/translationAlignment";
import { useI18n } from "@/lib/i18n";

/** Shared CRUD handler shape for user annotations. */
interface AnnotationHandlers {
  onCreateAnnotation?: (payload: {
    paragraph_id: string;
    track: AnnotationTrack;
    start_offset: number;
    end_offset: number;
    color: string;
  }) => void | Promise<void>;
  onUpdateAnnotation?: (
    id: string,
    payload: { color?: string | null; note?: string | null },
  ) => void | Promise<void>;
  onDeleteAnnotation?: (id: string) => void | Promise<void>;
}

/* ── Document Reader Panel ──────────────────────────────── */

export function DocumentReader({
  title,
  track,
  document,
  accentColor,
  blocks,
  blockHighlights,
  blockAlignmentHighlights = [],
  alignmentHighlightsByParagraph = {},
  sourceDocumentId,
  annotations = [],
  reviewContexts,
  scrollContainerRef,
  onContainerScroll,
  onCreateAnnotation,
  onUpdateAnnotation,
  onDeleteAnnotation,
  onAlignmentHover,
  onAlignmentLeave,
  onAlignmentToggle,
  onAssignField,
  fieldTypes,
}: {
  title: string;
  track: AnnotationTrack;
  document: EvidenceDocument;
  accentColor: string;
  blocks?: ContentBlock[] | null;
  blockHighlights?: BlockHighlight[];
  blockAlignmentHighlights?: AlignmentTextHighlight[];
  alignmentHighlightsByParagraph?: AlignmentHighlightMap;
  sourceDocumentId?: string;
  annotations?: UserAnnotation[];
  reviewContexts?: ReviewContextMap;
  scrollContainerRef?: MutableRefObject<HTMLDivElement | null>;
  onContainerScroll?: (e: UIEvent<HTMLDivElement>) => void;
  onAlignmentHover?: (pairId: string) => void;
  onAlignmentLeave?: () => void;
  onAlignmentToggle?: (pairId: string) => void;
  onAssignField?: (selectedText: string, fieldType: string) => void | Promise<void>;
  fieldTypes?: FieldTypeOption[];
} & AnnotationHandlers) {
  const { t } = useI18n();
  const contentRef = useRef<HTMLDivElement | null>(null);
  const hasBlocks = blocks && blocks.length > 0;
  const paragraphId = `${track}-document`;
  const annotationsForParagraph = (id: string) =>
    annotations.filter((a) => a.paragraph_id === id);
  const docAnnotations = annotationsForParagraph(paragraphId);
  const fullTextPara = document.paragraphs.find((p) => p.id.endsWith("-full-text"));
  const snippetParas = fullTextPara
    ? document.paragraphs.filter((p) => p !== fullTextPara)
    : document.paragraphs;

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      borderRadius: 12,
      border: "1px solid var(--color-border)",
      backgroundColor: "var(--color-surface)",
      overflow: "hidden",
    }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "10px 16px",
          borderBottom: "1px solid var(--color-bg-muted)",
          backgroundColor: `${accentColor}08`,
        }}
      >
        <Languages style={{ width: 16, height: 16, color: accentColor }} />
        <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--color-code-text)", margin: 0 }}>{title}</h3>
        <span style={{
          marginLeft: "auto",
          fontSize: 11,
          textTransform: "capitalize",
          color: "var(--color-text-secondary)",
        }}>
          {track}{t("evidenceDb.doc.trackSuffix")}{hasBlocks ? t("evidenceDb.doc.structured") : ""}
        </span>
      </div>
      <div
        ref={(el: HTMLDivElement | null) => {
          contentRef.current = el;
          if (scrollContainerRef) scrollContainerRef.current = el;
        }}
        onScroll={onContainerScroll}
        className="edb-scroll"
        style={{ maxHeight: 600, overflowY: "auto", padding: 16, position: "relative" }}
      >
        {hasBlocks ? (
          <StructuredBlockRenderer
            blocks={blocks}
            highlights={blockHighlights ?? []}
            alignmentHighlights={blockAlignmentHighlights}
            reviewContexts={reviewContexts}
            onAlignmentHover={onAlignmentHover}
            onAlignmentLeave={onAlignmentLeave}
            onAlignmentToggle={onAlignmentToggle}
          />
        ) : document.paragraphs.length === 0 ? (
          <div style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "48px 0",
            textAlign: "center",
          }}>
            <BookOpen style={{ width: 32, height: 32, color: "var(--color-text-muted)", marginBottom: 8 }} />
            <p style={{ fontSize: 14, color: "var(--color-text-secondary)", margin: 0 }}>
              {t("evidenceDb.doc.noText", { track })}
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
                annotations={annotationsForParagraph(fullTextPara.id)}
                reviewContexts={reviewContexts}
                alignmentHighlights={alignmentHighlightsByParagraph[fullTextPara.id] ?? []}
                onAlignmentHover={onAlignmentHover}
                onAlignmentLeave={onAlignmentLeave}
                onAlignmentToggle={onAlignmentToggle}
                onCreateAnnotation={onCreateAnnotation}
                onUpdateAnnotation={onUpdateAnnotation}
                onDeleteAnnotation={onDeleteAnnotation}
                onAssignField={onAssignField}
                fieldTypes={fieldTypes}
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
                    color: "var(--color-text-muted)",
                    fontFamily: "var(--font-mono)",
                  }}>
                    {t("evidenceDb.doc.page", { page: String(para.page) })}
                  </span>
                )}
                <HighlightedText
                  paragraph={para}
                  reviewContexts={reviewContexts}
                  alignmentHighlights={alignmentHighlightsByParagraph[para.id] ?? []}
                  onAlignmentHover={onAlignmentHover}
                  onAlignmentLeave={onAlignmentLeave}
                  onAlignmentToggle={onAlignmentToggle}
                />
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
          onAssignField={onAssignField}
          fieldTypes={fieldTypes}
        />
      </div>
    </div>
  );
}
