import { STATUS_VARIANT } from "@/lib/constants/statusVariant";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  Columns2,
  FileText,
  Highlighter,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Hash,
  Link2,
  TrendingUp,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import type {
  EvidenceGroupDetailResponse,
  EvidenceGroupItem,
  EvidenceHighlightTone,
} from "../types/evidenceSearch";
import {
  buildEvidenceDocument,
  CATEGORY_COLORS,
  EVIDENCE_CATEGORIES,
  countEvidenceCategories,
  hasTranslatedDocumentText,
  type EvidenceDocumentHighlight,
  type EvidenceDocumentParagraph,
} from "../utils/evidenceDocument";
import {
  buildAlignmentHighlightMap,
  type AlignmentHighlightMap,
  type AlignmentInteractionState,
  type AlignmentTextHighlight,
} from "../utils/translationAlignment";
import { categoryLabel } from "../utils/categoryStyles";
import { MarkdownDocumentViewer } from "./MarkdownDocumentViewer";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createAnnotation,
  deleteAnnotation,
  listAnnotations,
  updateAnnotation,
} from "@/features/evidence-search/services/annotations";
import type { AnnotationCreateRequest, AnnotationTrack, AnnotationUpdateRequest, UserAnnotation } from "../types/annotations";
import { AnnotationLayer, type FieldTypeOption } from "./annotationLayer";
import { openFieldReviewMenu, FieldReviewMenu } from "./FieldReviewPopover";
import type { FieldReviewInfo } from "./FieldReviewPopover";
import type { ReviewContextMap } from "@/features/evidence-db/components/HighlightedText";
import { useI18n } from "@/lib/i18n";
import { patchEvidence } from "../services/evidenceCorrection";
import { EVIDENCE_FIELD_SPECS } from "@/lib/constants/evidenceFields";

/* ---- Constants ---- */

const HIGHLIGHT_TONES: EvidenceHighlightTone[] = [
  "gene",
  "variant",
  "disease",
  "classification",
  "functional",
  "neutral",
];

/* ---- Inline style helpers ---- */

function chipInlineStyle(hex?: string): React.CSSProperties {
  if (!hex) return { borderColor: "var(--color-border)", backgroundColor: "var(--color-bg)", color: "var(--color-text-strong)" };
  return { borderColor: hex + "60", backgroundColor: hex + "15", color: hex };
}

function markInlineStyle(hex?: string, selected?: boolean): React.CSSProperties {
  const base: React.CSSProperties = hex
    ? { backgroundColor: hex + "40", color: hex, boxShadow: `0 0 0 1px ${hex}50` }
    : { backgroundColor: "var(--color-border)", color: "var(--color-text)", boxShadow: "0 0 0 1px var(--color-text-muted)" };
  if (selected) {
    base.outline = "2px solid var(--color-primary-700, #0e7490)";
    base.outlineOffset = "2px";
  }
  return base;
}

function alignmentInlineStyle(
  alignment: AlignmentTextHighlight,
  hasEvidence: boolean,
): React.CSSProperties {
  const activeColor = alignment.pinned ? "#7C3AED" : "#0891B2";
  if (hasEvidence) {
    return alignment.active
      ? { outline: `2px solid ${activeColor}`, outlineOffset: "2px" }
      : {};
  }
  return {
    borderRadius: 4,
    padding: "2px 4px",
    backgroundColor: alignment.active ? `${activeColor}30` : "rgba(8, 145, 178, 0.12)",
    boxShadow: alignment.active ? `0 0 0 1px ${activeColor}70` : "0 0 0 1px rgba(8, 145, 178, 0.22)",
    cursor: "pointer",
    transition: "background-color 0.12s, box-shadow 0.12s",
  };
}

/* ---- Utility functions ---- */

function formatPercent(value?: number | null) {
  if (value == null) {
    return "\u2014";
  }
  return `${(value * 100).toFixed(0)}%`;
}

function categoryFromItem(item?: EvidenceGroupItem | null) {
  if (!item) {
    return null;
  }
  if (item.category) {
    return item.category;
  }
  return item.field_id.includes(".") ? item.field_id.split(".", 1)[0] : null;
}

function itemLabel(item: EvidenceGroupItem) {
  return item.field_name ?? item.field_id;
}

function selectedTraceFor(
  detail: EvidenceGroupDetailResponse,
  selectedEvidenceId: string | null,
) {
  if (!selectedEvidenceId) {
    return detail.traces[0] ?? null;
  }

  const selectedItem = detail.items.find(
    (item) => item.canonical_evidence_id === selectedEvidenceId,
  );
  return (
    detail.traces.find(
      (trace) => trace.canonical_evidence_id === selectedEvidenceId,
    ) ??
    detail.traces.find((trace) => trace.field_id === selectedItem?.field_id) ??
    detail.traces[0] ??
    null
  );
}

function detailTitle(detail: EvidenceGroupDetailResponse) {
  const title = detail.title?.trim();
  return title || "Untitled literature record";
}

/* ---- Sub-components ---- */

function MetadataToken({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value?: string | null;
  icon?: React.ComponentType<{ style?: React.CSSProperties }>;
}) {
  return (
    <span
      style={{
        display: "inline-flex",
        maxWidth: "100%",
        alignItems: "center",
        gap: 6,
        borderRadius: 6,
        border: "1px solid var(--color-primary-200)",
        backgroundColor: "var(--color-surface)",
        padding: "4px 10px",
        fontSize: 12,
        color: "var(--color-primary-900, var(--color-primary-900))",
        boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
      }}
    >
      {Icon && <Icon style={{ width: 12, height: 12, flexShrink: 0, color: "var(--color-primary-500, var(--color-primary-500))" }} />}
      <span style={{ fontWeight: 600 }}>{label}</span>
      <span
        style={{
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          fontFamily: "monospace",
        }}
      >
        {value?.trim() || "\u2014"}
      </span>
    </span>
  );
}

function EvidenceTonePill({ item }: { item: EvidenceGroupItem }) {
  const cat = categoryFromItem(item);
  const hex = cat && CATEGORY_COLORS[cat] ? CATEGORY_COLORS[cat].hex : undefined;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        borderRadius: 6,
        border: "1px solid",
        padding: "4px 8px",
        fontSize: 12,
        fontWeight: 500,
        ...chipInlineStyle(hex),
      }}
    >
      {cat && CATEGORY_COLORS[cat] && (
        <span
          style={{
            display: "inline-block",
            width: 8,
            height: 8,
            flexShrink: 0,
            borderRadius: "50%",
            backgroundColor: CATEGORY_COLORS[cat].hex,
          }}
          aria-hidden="true"
        />
      )}
      {categoryLabel(cat)}
    </span>
  );
}

/* ---- Document reader components ---- */

function normalizedHighlights(paragraph: EvidenceDocumentParagraph) {
  const highlights = [...paragraph.highlights].sort((a, b) => a.start - b.start);
  const normalized: EvidenceDocumentHighlight[] = [];
  let cursor = 0;

  for (const highlight of highlights) {
    const start = Math.max(cursor, Math.max(0, Math.min(highlight.start, paragraph.text.length)));
    const end = Math.max(start, Math.min(highlight.end, paragraph.text.length));
    if (end <= start) {
      continue;
    }
    normalized.push({ ...highlight, start, end });
    cursor = end;
  }

  return normalized;
}

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

function HighlightedParagraph({
  paragraph,
  track,
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
}: {
  paragraph: EvidenceDocumentParagraph;
  track: AnnotationTrack;
  annotations?: UserAnnotation[];
  reviewContexts?: ReviewContextMap;
  alignmentHighlights?: AlignmentTextHighlight[];
  onAlignmentHover?: (pairId: string) => void;
  onAlignmentLeave?: () => void;
  onAlignmentToggle?: (pairId: string) => void;
  onAssignField?: (selectedText: string, fieldType: string) => void;
  fieldTypes?: FieldTypeOption[];
} & AnnotationHandlers) {
  const contentRef = useRef<HTMLDivElement>(null);
  const highlights = normalizedHighlights(paragraph);
  const alignments = [...alignmentHighlights]
    .map((alignment) => ({
      ...alignment,
      start: Math.max(0, Math.min(alignment.start, paragraph.text.length)),
      end: Math.max(0, Math.min(alignment.end, paragraph.text.length)),
    }))
    .filter((alignment) => alignment.end > alignment.start)
    .sort((a, b) => a.start - b.start);
  const nodes: ReactNode[] = [];

  const boundaries = new Set<number>([0, paragraph.text.length]);
  for (const highlight of highlights) {
    boundaries.add(highlight.start);
    boundaries.add(highlight.end);
  }
  for (const alignment of alignments) {
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
    const text = paragraph.text.slice(start, end);
    const highlight = highlights.find((candidate) => candidate.start < end && candidate.end > start);
    const alignment = alignments.find((candidate) => candidate.start < end && candidate.end > start);

    if (!highlight && !alignment) {
      nodes.push(<span key={`plain-${start}`}>{text}</span>);
      continue;
    }

    if (!highlight && alignment) {
      nodes.push(
        <span
          key={`alignment-${alignment.pairId}-${start}`}
          data-alignment-pair-id={alignment.pairId}
          data-alignment-active={alignment.active ? "true" : "false"}
          style={alignmentInlineStyle(alignment, false)}
          onMouseEnter={() => onAlignmentHover?.(alignment.pairId)}
          onMouseLeave={() => onAlignmentLeave?.()}
          onClick={() => onAlignmentToggle?.(alignment.pairId)}
        >
          {text}
        </span>,
      );
      continue;
    }

    if (!highlight) {
      continue;
    }

    const hex = highlight.category && CATEGORY_COLORS[highlight.category]
      ? CATEGORY_COLORS[highlight.category].hex
      : undefined;
    const reviewInfo = reviewContexts?.get(highlight.evidenceId);
    const markStyle = {
      borderRadius: 4,
      padding: "2px 4px",
      fontWeight: 600,
      ...markInlineStyle(hex, highlight.selected),
      ...(alignment ? alignmentInlineStyle(alignment, true) : {}),
      ...(reviewInfo ? { cursor: "pointer" as const } : {}),
    };
    nodes.push(
      <mark
        key={`${highlight.evidenceId}-${start}-${index}`}
        data-reviewable={reviewInfo ? "true" : undefined}
        data-alignment-pair-id={alignment?.pairId}
        data-alignment-active={alignment?.active ? "true" : undefined}
        style={markStyle}
        onMouseEnter={alignment ? () => onAlignmentHover?.(alignment.pairId) : undefined}
        onMouseLeave={alignment ? () => onAlignmentLeave?.() : undefined}
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
    <div style={{ borderBottom: "1px solid var(--color-bg-muted)", padding: "16px 0" }}>
      <div style={{ marginBottom: 8, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, fontSize: 12, color: "var(--color-text-secondary)" }}>
        <span
          style={{
            borderRadius: 6,
            backgroundColor: "var(--color-bg-muted)",
            padding: "4px 8px",
            fontWeight: 500,
            color: "var(--color-text-strong)",
          }}
        >
          {paragraph.highlights[0]?.label ?? "Document text"}
        </span>
        <span>Page {paragraph.page ?? "\u2014"}</span>
      </div>
      <div ref={contentRef} style={{ position: "relative" }}>
        <p style={{ whiteSpace: "pre-wrap", fontSize: 14, lineHeight: "28px", color: "var(--color-code-text)" }}>
          {nodes.length > 0 ? nodes : paragraph.text}
        </p>
        <AnnotationLayer
          containerRef={contentRef}
          paragraphId={paragraph.id}
          track={track}
          annotations={annotations}
          recomputeDeps={[paragraph.text, paragraph.highlights]}
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

function EvidenceDocumentReader({
  title,
  paragraphs,
  track,
  annotations = [],
  reviewContexts,
  alignmentHighlightsByParagraph = {},
  onAlignmentHover,
  onAlignmentLeave,
  onAlignmentToggle,
  onCreateAnnotation,
  onUpdateAnnotation,
  onDeleteAnnotation,
  onAssignField,
  fieldTypes,
}: {
  title: string;
  paragraphs: EvidenceDocumentParagraph[];
  track: AnnotationTrack;
  annotations?: UserAnnotation[];
  reviewContexts?: ReviewContextMap;
  alignmentHighlightsByParagraph?: AlignmentHighlightMap;
  onAlignmentHover?: (pairId: string) => void;
  onAlignmentLeave?: () => void;
  onAlignmentToggle?: (pairId: string) => void;
  onAssignField?: (selectedText: string, fieldType: string) => void;
  fieldTypes?: FieldTypeOption[];
} & AnnotationHandlers) {
  const { t } = useI18n();
  const fullTextParagraph = paragraphs.find((p) => p.id.endsWith("-full-text"));
  const snippetParagraphs = paragraphs.filter((p) => p !== fullTextParagraph);
  const isFullText = Boolean(fullTextParagraph);
  const subtitle = t("evidence.bilingual.fullDoc", { count: paragraphs.length });

  const annotationsFor = (paraId: string) =>
    annotations.filter((a) => a.paragraph_id === paraId);

  return (
    <section style={{ overflow: "hidden", borderRadius: 12, border: "1px solid var(--color-border)", backgroundColor: "var(--color-surface)", boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)" }}>
      <div
        style={{
          position: "sticky",
          top: 0,
          zIndex: 10,
          borderBottom: "1px solid var(--color-bg-muted)",
          background: "linear-gradient(to right, var(--color-bg), var(--color-bg), var(--color-subtle-bg))",
          padding: "12px 20px",
          backdropFilter: "blur(4px)",
        }}
      >
        <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text)", margin: 0 }}>{title}</h3>
        <p style={{ marginTop: 2, fontSize: 12, color: "var(--color-text-secondary)" }}>
          {subtitle}
        </p>
      </div>
      <div style={{ maxHeight: 720, overflowY: "auto", padding: "0 20px" }}>
        {paragraphs.length > 0 ? (
          <>
            {isFullText && fullTextParagraph && (
              <MarkdownDocumentViewer
                markdown={fullTextParagraph.text}
                highlights={fullTextParagraph.highlights}
                paragraphId={fullTextParagraph.id}
                track={track}
                annotations={annotationsFor(fullTextParagraph.id)}
                alignmentHighlights={alignmentHighlightsByParagraph[fullTextParagraph.id] ?? []}
                onAlignmentHover={onAlignmentHover}
                onAlignmentLeave={onAlignmentLeave}
                onAlignmentToggle={onAlignmentToggle}
                onCreateAnnotation={onCreateAnnotation}
                onUpdateAnnotation={onUpdateAnnotation}
                onDeleteAnnotation={onDeleteAnnotation}
              />
            )}
            {snippetParagraphs.map((paragraph) => (
              <HighlightedParagraph
                key={paragraph.id}
                paragraph={paragraph}
                track={track}
                annotations={annotationsFor(paragraph.id)}
                reviewContexts={reviewContexts}
                alignmentHighlights={alignmentHighlightsByParagraph[paragraph.id] ?? []}
                onAlignmentHover={onAlignmentHover}
                onAlignmentLeave={onAlignmentLeave}
                onAlignmentToggle={onAlignmentToggle}
                onCreateAnnotation={onCreateAnnotation}
                onUpdateAnnotation={onUpdateAnnotation}
                onDeleteAnnotation={onDeleteAnnotation}
                onAssignField={onAssignField}
                fieldTypes={fieldTypes}
              />
            ))}
            {!isFullText && paragraphs.map((paragraph) => (
              <HighlightedParagraph
                key={paragraph.id}
                paragraph={paragraph}
                track={track}
                annotations={annotationsFor(paragraph.id)}
                reviewContexts={reviewContexts}
                alignmentHighlights={alignmentHighlightsByParagraph[paragraph.id] ?? []}
                onAlignmentHover={onAlignmentHover}
                onAlignmentLeave={onAlignmentLeave}
                onAlignmentToggle={onAlignmentToggle}
                onCreateAnnotation={onCreateAnnotation}
                onUpdateAnnotation={onUpdateAnnotation}
                onDeleteAnnotation={onDeleteAnnotation}
                onAssignField={onAssignField}
                fieldTypes={fieldTypes}
              />
            ))}
          </>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, padding: "48px 8px", textAlign: "center" }}>
            <div
              style={{
                display: "flex",
                height: 48,
                width: 48,
                alignItems: "center",
                justifyContent: "center",
                borderRadius: 12,
                backgroundColor: "var(--color-bg-muted)",
              }}
            >
              <FileText style={{ width: 24, height: 24, color: "var(--color-text-muted)" }} />
            </div>
            <p style={{ fontSize: 14, color: "var(--color-text-secondary)" }}>
              {t("evidence.bilingual.noDocText")}
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

function CategoryLayerToggle({
  checked,
  count,
  onChange,
  category,
}: {
  checked: boolean;
  count: number;
  onChange: () => void;
  category: string;
}) {
  const cat = CATEGORY_COLORS[category];
  const baseStyle: React.CSSProperties = {
    display: "flex",
    minHeight: 44,
    cursor: count === 0 ? "not-allowed" : "pointer",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    borderRadius: 8,
    border: "1px solid",
    padding: "8px 12px",
    transition: "color 0.15s, border-color 0.15s, background-color 0.15s",
    opacity: count === 0 ? 0.5 : 1,
  };

  if (checked && cat) {
    baseStyle.borderColor = cat.hex + "40";
    baseStyle.backgroundColor = cat.hex + "10";
  } else if (checked) {
    baseStyle.borderColor = "var(--color-primary-200, #a5f3fc)";
    baseStyle.backgroundColor = "var(--color-primary-50, #ecfeff)";
  } else {
    baseStyle.borderColor = "var(--color-border)";
    baseStyle.backgroundColor = "var(--color-surface)";
  }

  return (
    <label className="edb-toggle-label" style={baseStyle}>
      <input
        type="checkbox"
        checked={checked}
        disabled={count === 0}
        onChange={onChange}
        className="edb-toggle-input"
        style={{ position: "absolute", width: 1, height: 1, padding: 0, margin: -1, overflow: "hidden", clip: "rect(0,0,0,0)", whiteSpace: "nowrap", borderWidth: 0 }}
      />
      <span style={{ display: "flex", minWidth: 0, alignItems: "center", gap: 8 }}>
        <span
          style={{
            display: "inline-block",
            width: 12,
            height: 12,
            flexShrink: 0,
            borderRadius: "50%",
            backgroundColor: cat?.hex ?? "#9CA3AF",
          }}
          aria-hidden="true"
        />
        <span style={{ minWidth: 0 }}>
          <span
            style={{
              display: "block",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              fontSize: 14,
              fontWeight: 500,
              color: "var(--color-text)",
            }}
          >
            {cat?.label ?? category}
          </span>
          <span style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>
            {count} item{count !== 1 ? "s" : ""}
          </span>
        </span>
      </span>
      <span
        className="edb-toggle-track"
        style={{
          position: "relative",
          height: 24,
          width: 44,
          flexShrink: 0,
          borderRadius: 9999,
          transition: "background-color 0.15s",
          backgroundColor: checked ? "var(--color-primary-700, var(--color-primary-700))" : "var(--color-text-muted)",
        }}
        aria-hidden="true"
      >
        <span
          style={{
            position: "absolute",
            left: 4,
            top: 4,
            height: 16,
            width: 16,
            borderRadius: "50%",
            backgroundColor: "var(--color-surface)",
            boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
            transition: "transform 0.15s",
            transform: checked ? "translateX(20px)" : "translateX(0)",
          }}
        />
      </span>
    </label>
  );
}

/* ---- BilingualCompareView ---- */

export function BilingualCompareView({
  detail,
  groupId,
  selectedEvidenceId,
  setSelectedEvidenceId,
}: {
  detail: EvidenceGroupDetailResponse;
  groupId: string;
  selectedEvidenceId: string | null;
  setSelectedEvidenceId: (value: string) => void;
}) {
  const [enabledTones] = useState<Set<EvidenceHighlightTone>>(
    () => new Set(HIGHLIGHT_TONES),
  );
  const [enabledCategories, setEnabledCategories] = useState<Set<string>>(
    () => new Set(EVIDENCE_CATEGORIES),
  );
  const [hoveredAlignmentPairId, setHoveredAlignmentPairId] = useState<string | null>(null);
  const [pinnedAlignmentPairId, setPinnedAlignmentPairId] = useState<string | null>(null);
  const alignmentState = useMemo<AlignmentInteractionState>(
    () => ({
      hoveredPairId: hoveredAlignmentPairId,
      pinnedPairId: pinnedAlignmentPairId,
    }),
    [hoveredAlignmentPairId, pinnedAlignmentPairId],
  );
  const handleAlignmentToggle = useCallback((pairId: string) => {
    setPinnedAlignmentPairId((current) => (current === pairId ? null : pairId));
  }, []);
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setHoveredAlignmentPairId(null);
        setPinnedAlignmentPairId(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);
  const selectedItem =
    detail.items.find(
      (item) => item.canonical_evidence_id === selectedEvidenceId,
    ) ??
    detail.items[0] ??
    null;
  const selectedTrace = selectedTraceFor(detail, selectedEvidenceId);
  const { t } = useI18n();
  const categoryCounts = useMemo(
    () => countEvidenceCategories(detail.items),
    [detail.items],
  );
  const originalDocument = useMemo(
    () =>
      buildEvidenceDocument(
        detail,
        "original",
        enabledTones,
        selectedEvidenceId,
        enabledCategories,
      ),
    [detail, enabledTones, selectedEvidenceId, enabledCategories],
  );
  const translatedDocument = useMemo(
    () =>
      buildEvidenceDocument(
        detail,
        "translated",
        enabledTones,
        selectedEvidenceId,
        enabledCategories,
      ),
    [detail, enabledTones, selectedEvidenceId, enabledCategories],
  );
  const originalAlignmentHighlights = useMemo(
    () => buildAlignmentHighlightMap(detail, originalDocument, "original", alignmentState),
    [alignmentState, detail, originalDocument],
  );
  const translatedAlignmentHighlights = useMemo(
    () => buildAlignmentHighlightMap(detail, translatedDocument, "translated", alignmentState),
    [alignmentState, detail, translatedDocument],
  );
  const showTranslatedDocument = hasTranslatedDocumentText(detail);
  const sourceDocumentId = detail.source_document_id;
  const queryClient = useQueryClient();
  const annotationsQuery = useQuery({
    queryKey: ["annotations", sourceDocumentId],
    queryFn: () => listAnnotations(sourceDocumentId),
    enabled: Boolean(sourceDocumentId),
  });
  const allAnnotations: UserAnnotation[] = annotationsQuery.data ?? [];

  const createMutation = useMutation({
    mutationFn: (payload: AnnotationCreateRequest) =>
      createAnnotation(sourceDocumentId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["annotations", sourceDocumentId] });
    },
  });
  const updateMutation = useMutation({
    mutationFn: (vars: { id: string; payload: AnnotationUpdateRequest }) =>
      updateAnnotation(sourceDocumentId, vars.id, vars.payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["annotations", sourceDocumentId] });
    },
  });
  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAnnotation(sourceDocumentId, id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["annotations", sourceDocumentId] });
    },
  });

  const handleCreateAnnotation = (payload: {
    paragraph_id: string;
    track: AnnotationTrack;
    start_offset: number;
    end_offset: number;
    color: string;
  }) => {
    void createMutation.mutate(payload);
  };
  const handleUpdateAnnotation = (
    id: string,
    payload: { color?: string | null; note?: string | null },
  ) => {
    void updateMutation.mutate({ id, payload });
  };
  const handleDeleteAnnotation = (id: string) => {
    void deleteMutation.mutate(id);
  };

  const handleAssignField = async (selectedText: string, fieldType: string) => {
    const targetItem = detail.items.find(
      (item) => item.field_id === fieldType || item.category === fieldType,
    ) ?? detail.items[0];
    if (!targetItem) return;
    try {
      await patchEvidence(targetItem.canonical_evidence_id, {
        fields: { [fieldType]: selectedText },
        change_reason: `Text selection assignment to ${fieldType}`,
      });
      void queryClient.invalidateQueries({ queryKey: ["evidence-group-detail", groupId] });
    } catch {
      // error handled by caller
    }
  };
  const fieldTypes = useMemo<FieldTypeOption[]>(
    () => EVIDENCE_FIELD_SPECS.map((spec) => ({
      fieldId: spec.fieldId,
      label: spec.fieldName,
      category: spec.categoryId,
    })),
    [],
  );

  const originalAnnotations = allAnnotations.filter((a) => a.track === "original");
  const translatedAnnotations = allAnnotations.filter((a) => a.track === "translated");

  // Build review context map for hover-to-review on highlight marks
  const reviewContexts = useMemo<ReviewContextMap>(() => {
    const map = new Map<string, FieldReviewInfo>();
    for (const item of detail.items) {
      map.set(item.canonical_evidence_id, {
        evidenceId: item.canonical_evidence_id,
        fieldId: item.field_id,
        label: item.field_name ?? item.field_id,
        category: item.category,
        currentStatus: item.review_status,
        value: item.value,
        groupId,
      });
    }
    return map;
  }, [detail.items, groupId]);



  const toggleCategory = (cat: string) => {
    setEnabledCategories((current) => {
      const next = new Set(current);
      if (next.has(cat)) {
        next.delete(cat);
      } else {
        next.add(cat);
      }
      return next;
    });
  };

  return (
      <div className="content-fade-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <FieldReviewMenu />
        <Link
          to={`/evidence/detail?groupId=${encodeURIComponent(groupId)}`}
          className="edb-back-link"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            fontSize: 14,
            fontWeight: 500,
            color: "var(--color-text-secondary)",
            textDecoration: "none",
            transition: "color 0.15s",
          }}
        >
          <ArrowLeft style={{ width: 16, height: 16 }} />
          {t("evidence.bilingual.backDetail")}
        </Link>

        <section style={{ overflow: "hidden", borderRadius: 12, border: "1px solid var(--color-border)", backgroundColor: "var(--color-surface)", boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)" }}>
          <div
            style={{
              position: "relative",
              borderBottom: "1px solid var(--color-purple-50)",
              background: "linear-gradient(to right, var(--color-purple-50), transparent)",
              padding: "20px 24px",
            }}
          >
            <div
              style={{
                position: "absolute",
                left: 0,
                top: 0,
                height: "100%",
                width: 4,
                background: "linear-gradient(to bottom, var(--color-purple-400), var(--color-purple-600))",
              }}
            />
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
              <div style={{ minWidth: 0 }}>
                <p
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    fontSize: 12,
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    color: "var(--color-purple-700)",
                    margin: 0,
                  }}
                >
                  <Columns2 style={{ width: 16, height: 16 }} />
                  {t("evidence.bilingual.header")}
                </p>
                <h2 style={{ marginTop: 8, maxWidth: 896, fontSize: 20, fontWeight: 600, lineHeight: "28px", color: "var(--color-text)" }}>
                  {detailTitle(detail)}
                </h2>
                <div style={{ marginTop: 12, display: "flex", maxWidth: 896, flexWrap: "wrap", gap: 8 }}>
                  <MetadataToken label={t("evidence.bilingual.uuid")} value={detail.source_document_id} icon={Hash} />
                  <MetadataToken label={t("evidence.bilingual.pmid")} value={detail.pmid} icon={FileText} />
                  <MetadataToken label={t("evidence.bilingual.doi")} value={detail.doi} icon={Link2} />
                </div>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
                {selectedItem && <EvidenceTonePill item={selectedItem} />}
                {selectedItem && (
                  <Badge variant={STATUS_VARIANT[selectedItem.review_status as keyof typeof STATUS_VARIANT] ?? "default"}>
                    {selectedItem.review_status}
                  </Badge>
                )}
              </div>
            </div>
          </div>

          <div className="edb-compare-stats-grid">
            {[
              { label: t("evidence.bilingual.itemConf"), value: formatPercent(selectedItem?.confidence), icon: TrendingUp },
              { label: t("evidence.bilingual.alignConf"), value: formatPercent(selectedTrace?.alignment_confidence), icon: ShieldCheck },
              { label: t("evidence.bilingual.sourcePage"), value: selectedTrace?.original?.page ?? selectedTrace?.translated?.page ?? selectedItem?.page ?? "\u2014", icon: FileText },
            ].map((stat) => (
              <div key={stat.label} className="edb-compare-stat-cell">
                <div
                  style={{
                    display: "flex",
                    height: 36,
                    width: 36,
                    flexShrink: 0,
                    alignItems: "center",
                    justifyContent: "center",
                    borderRadius: 8,
                    background: "linear-gradient(to bottom right, var(--color-purple-50), var(--color-purple-50))",
                  }}
                >
                  <stat.icon style={{ width: 16, height: 16, color: "var(--color-purple-700)" }} />
                </div>
                <div>
                  <p style={{ fontSize: 12, color: "var(--color-text-secondary)", margin: 0 }}>{stat.label}</p>
                  <p style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text)", margin: 0 }}>
                    {stat.value}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>

        <div className="edb-compare-layout">
          <aside style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <section style={{ borderRadius: 12, border: "1px solid var(--color-border)", backgroundColor: "var(--color-surface)", boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)" }}>
              <div style={{ borderBottom: "1px solid var(--color-bg-muted)", padding: "12px 16px" }}>
                <h3 style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 600, color: "var(--color-text)", margin: 0 }}>
                  <SlidersHorizontal style={{ width: 16, height: 16, color: "var(--color-primary-700, var(--color-primary-700))" }} />
                  {t("evidence.bilingual.categories")}
                </h3>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8, padding: 16 }}>
                {EVIDENCE_CATEGORIES.map((cat) => (
                  <CategoryLayerToggle
                    key={cat}
                    category={cat}
                    count={categoryCounts[cat] ?? 0}
                    checked={enabledCategories.has(cat)}
                    onChange={() => toggleCategory(cat)}
                  />
                ))}
              </div>
            </section>

            <section style={{ borderRadius: 12, border: "1px solid var(--color-border)", backgroundColor: "var(--color-surface)", boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)" }}>
              <div style={{ borderBottom: "1px solid var(--color-bg-muted)", padding: "12px 16px" }}>
                <h3 style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 600, color: "var(--color-text)", margin: 0 }}>
                  <Search style={{ width: 16, height: 16, color: "var(--color-primary-700, var(--color-primary-700))" }} />
                  {t("evidence.bilingual.navigator")}
                </h3>
              </div>
              <div style={{ maxHeight: 460, overflowY: "auto", padding: "16px 12px 16px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
                {detail.items.map((item) => {
                  const active =
                    item.canonical_evidence_id === selectedItem?.canonical_evidence_id;
                  const cat = categoryFromItem(item);
                  const catColor = cat && CATEGORY_COLORS[cat];
                  const navItemStyle: React.CSSProperties = {
                    width: "100%",
                    cursor: "pointer",
                    borderRadius: 8,
                    border: "1px solid",
                    padding: 12,
                    textAlign: "left",
                    transition: "all 0.15s",
                    background: "none",
                  };
                  if (active && catColor) {
                    navItemStyle.borderColor = catColor.hex + "60";
                    navItemStyle.backgroundColor = catColor.hex + "12";
                    navItemStyle.boxShadow = "0 1px 2px 0 rgba(0,0,0,0.05)";
                  } else if (active) {
                    navItemStyle.borderColor = "var(--color-primary-300, #67e8f9)";
                    navItemStyle.backgroundColor = "var(--color-primary-50, #ecfeff)";
                    navItemStyle.boxShadow = "0 1px 2px 0 rgba(0,0,0,0.05)";
                  } else {
                    navItemStyle.borderColor = "var(--color-border)";
                    navItemStyle.backgroundColor = "var(--color-surface)";
                  }
                  return (
                    <button
                      key={item.canonical_evidence_id}
                      type="button"
                      onClick={() => setSelectedEvidenceId(item.canonical_evidence_id)}
                      className="edb-nav-item edb-focusable-btn"
                      style={navItemStyle}
                    >
                      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
                        <EvidenceTonePill item={item} />
                        <span style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>
                          {formatPercent(item.confidence)}
                        </span>
                      </div>
                      <p className="edb-nav-item-title edb-line-clamp-2" style={{ marginTop: 8, fontSize: 14, fontWeight: 500, color: "var(--color-text)", transition: "color 0.15s" }}>
                        {itemLabel(item)}
                      </p>
                      <p className="edb-line-clamp-2" style={{ marginTop: 4, fontSize: 12, color: "var(--color-text-secondary)" }}>
                        {item.value ?? "\u2014"}
                      </p>
                    </button>
                  );
                })}
              </div>
            </section>
          </aside>

          <section style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ overflow: "hidden", borderRadius: 12, border: "1px solid var(--color-border)", backgroundColor: "var(--color-surface)", boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)" }}>
              <div
                style={{
                  position: "relative",
                  borderBottom: "1px solid var(--color-bg-muted)",
                  background: "linear-gradient(to right, var(--color-highlight), transparent)",
                  padding: "16px 20px",
                }}
              >
                <div
                  style={{
                    position: "absolute",
                    left: 0,
                    top: 0,
                    height: "100%",
                    width: 4,
                    background: "linear-gradient(to bottom, var(--color-primary-400, var(--color-primary-400)), var(--color-primary-600))",
                  }}
                />
                <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
                  <div>
                    <p
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        fontSize: 12,
                        fontWeight: 600,
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        color: "var(--color-primary-800, var(--color-primary-800))",
                        margin: 0,
                      }}
                    >
                      <Highlighter style={{ width: 16, height: 16 }} />
                      {t("evidence.bilingual.activeEvidence")}
                    </p>
                    <h3 style={{ marginTop: 8, fontSize: 14, fontWeight: 600, color: "var(--color-text)" }}>
                      {selectedItem ? itemLabel(selectedItem) : t("evidence.bilingual.noSelected")}
                    </h3>
                    <p style={{ marginTop: 4, fontFamily: "monospace", fontSize: 12, color: "var(--color-text-secondary)" }}>
                      {selectedItem?.field_id ?? "\u2014"}
                    </p>
                  </div>
                  {selectedItem && (
                    <Badge variant={STATUS_VARIANT[selectedItem.review_status as keyof typeof STATUS_VARIANT] ?? "default"}>
                      {selectedItem.review_status}
                    </Badge>
                  )}
                </div>
              </div>
              <div style={{ padding: "16px 20px" }}>
                <p style={{ fontSize: 14, lineHeight: "24px", color: "var(--color-code-text)" }}>
                  {selectedItem?.value ?? "\u2014"}
                </p>
              </div>
            </div>

            <div
              className={showTranslatedDocument ? "edb-doc-readers-grid edb-doc-readers-two-col" : "edb-doc-readers-grid"}
            >
              <EvidenceDocumentReader
                title="Original document"
                paragraphs={originalDocument.paragraphs}
                track="original"
                annotations={originalAnnotations}
                reviewContexts={reviewContexts}
                alignmentHighlightsByParagraph={originalAlignmentHighlights}
                onAlignmentHover={setHoveredAlignmentPairId}
                onAlignmentLeave={() => setHoveredAlignmentPairId(null)}
                onAlignmentToggle={handleAlignmentToggle}
                onCreateAnnotation={handleCreateAnnotation}
                onUpdateAnnotation={handleUpdateAnnotation}
                onDeleteAnnotation={handleDeleteAnnotation}
                onAssignField={handleAssignField}
                fieldTypes={fieldTypes}
              />
              {showTranslatedDocument && (
                <EvidenceDocumentReader
                  title="English translation"
                  paragraphs={translatedDocument.paragraphs}
                  track="translated"
                  annotations={translatedAnnotations}
                  reviewContexts={reviewContexts}
                  alignmentHighlightsByParagraph={translatedAlignmentHighlights}
                  onAlignmentHover={setHoveredAlignmentPairId}
                  onAlignmentLeave={() => setHoveredAlignmentPairId(null)}
                  onAlignmentToggle={handleAlignmentToggle}
                  onCreateAnnotation={handleCreateAnnotation}
                  onUpdateAnnotation={handleUpdateAnnotation}
                  onDeleteAnnotation={handleDeleteAnnotation}
                  onAssignField={handleAssignField}
                  fieldTypes={fieldTypes}
                />
              )}
            </div>
          </section>
        </div>
      </div>
  );
}
