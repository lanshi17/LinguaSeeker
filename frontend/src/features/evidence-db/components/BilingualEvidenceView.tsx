import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  AlertCircle,
  ChevronRight,
} from "lucide-react";
import { useEvidenceGroupDetail } from "@/features/evidence-search/hooks/useEvidenceGroupDetail";
import {
  EVIDENCE_CATEGORIES,
  buildEvidenceDocument,
  hasTranslatedDocumentText,
  countEvidenceCategories,
} from "@/features/evidence-search/utils/evidenceDocument";
import { BilingualEvidenceSkeleton } from "./BilingualEvidenceSkeleton";
import { DocumentReader } from "./DocumentReader";
import type { BlockHighlight } from "./StructuredBlockRenderer";
import { ActiveEvidenceCard } from "./ActiveEvidenceCard";
import { LiteratureHeader } from "./LiteratureHeader";
import { BilingualSidebar } from "./BilingualSidebar";
import { bevEmbeddedCSS } from "./bevStyles";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createAnnotation,
  deleteAnnotation,
  listAnnotations,
  updateAnnotation,
} from "@/api/annotations";
import type {
  AnnotationCreateRequest,
  AnnotationTrack,
  AnnotationUpdateRequest,
  UserAnnotation,
} from "@/features/evidence-search/types/annotations";

/* ── Main View ──────────────────────────────────────────── */

export function BilingualEvidenceView({
  variantSlug,
  sourceDocumentId,
}: {
  variantSlug: string;
  sourceDocumentId: string;
}) {
  const [enabledCategories, setEnabledCategories] = useState<Set<string>>(
    () => new Set(EVIDENCE_CATEGORIES),
  );
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<
    string | undefined
  >(undefined);

  const {
    detail: groupDetail,
    isLoading,
    error,
  } = useEvidenceGroupDetail(undefined, sourceDocumentId);
  const queryClient = useQueryClient();
  const annotationsQuery = useQuery({
    queryKey: ["annotations", sourceDocumentId],
    queryFn: () => listAnnotations(sourceDocumentId),
    enabled: Boolean(sourceDocumentId),
  });
  const allAnnotations: UserAnnotation[] = annotationsQuery.data ?? [];

  const createMutation = useMutation({
    mutationFn: (payload: AnnotationCreateRequest) => createAnnotation(sourceDocumentId, payload),
    onSuccess: (created) => {
      queryClient.setQueryData<UserAnnotation[]>(["annotations", sourceDocumentId], (prev) => [
        ...(prev ?? []),
        created,
      ]);
    },
  });
  const updateMutation = useMutation({
    mutationFn: (vars: { id: string; payload: AnnotationUpdateRequest }) =>
      updateAnnotation(sourceDocumentId, vars.id, vars.payload),
    onSuccess: (updated) => {
      queryClient.setQueryData<UserAnnotation[]>(["annotations", sourceDocumentId], (prev) =>
        (prev ?? []).map((a) => (a.id === updated.id ? updated : a)),
      );
    },
  });
  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAnnotation(sourceDocumentId, id),
    onSuccess: (_void, deletedId) => {
      queryClient.setQueryData<UserAnnotation[]>(["annotations", sourceDocumentId], (prev) =>
        (prev ?? []).filter((a) => a.id !== deletedId),
      );
    },
  });

  const handleCreateAnnotation = (payload: {
    paragraph_id: string;
    track: AnnotationTrack;
    start_offset: number;
    end_offset: number;
    color: string;
  }) => void createMutation.mutate(payload);
  const handleUpdateAnnotation = (
    id: string,
    payload: { color?: string | null; note?: string | null },
  ) => void updateMutation.mutate({ id, payload });
  const handleDeleteAnnotation = (id: string) => void deleteMutation.mutate(id);

  const originalAnnotations = allAnnotations.filter((a) => a.track === "original");
  const translatedAnnotations = allAnnotations.filter((a) => a.track === "translated");


  const originalDoc = useMemo(
    () =>
      groupDetail
        ? buildEvidenceDocument(
            groupDetail,
            "original",
            undefined,
            selectedEvidenceId,
            enabledCategories,
          )
        : null,
    [groupDetail, selectedEvidenceId, enabledCategories],
  );

  const translatedDoc = useMemo(
    () =>
      groupDetail
        ? buildEvidenceDocument(
            groupDetail,
            "translated",
            undefined,
            selectedEvidenceId,
            enabledCategories,
          )
        : null,
    [groupDetail, selectedEvidenceId, enabledCategories],
  );

  const hasTranslation = groupDetail
    ? hasTranslatedDocumentText(groupDetail)
    : false;

  // Build block-level highlights from traces for structured rendering
  const buildBlockHighlights = useMemo((): { original: BlockHighlight[]; translated: BlockHighlight[] } => {
    if (!groupDetail) return { original: [], translated: [] };
    const items = new Map(groupDetail.items.map((item) => [item.canonical_evidence_id, item] as const));
    const origHighlights: BlockHighlight[] = [];
    const transHighlights: BlockHighlight[] = [];

    for (const trace of groupDetail.traces) {
      const item = items.get(trace.canonical_evidence_id);
      if (!item) continue;

      // Check category filter
      const cat = item.category ?? (item.field_id.includes(".") ? item.field_id.split(".")[0] : null);
      if (enabledCategories && cat && !enabledCategories.has(cat)) continue;

      if (trace.original?.text) {
        origHighlights.push({
          evidenceId: trace.canonical_evidence_id,
          fieldId: trace.field_id,
          label: item.field_name ?? trace.field_id,
          tone: cat ?? "neutral",
          category: cat,
          globalStart: trace.original.highlight_start,
          globalEnd: trace.original.highlight_end,
          selected: trace.canonical_evidence_id === selectedEvidenceId,
        });
      }
      if (trace.translated?.text) {
        transHighlights.push({
          evidenceId: trace.canonical_evidence_id,
          fieldId: trace.field_id,
          label: item.field_name ?? trace.field_id,
          tone: cat ?? "neutral",
          category: cat,
          globalStart: trace.translated.highlight_start,
          globalEnd: trace.translated.highlight_end,
          selected: trace.canonical_evidence_id === selectedEvidenceId,
        });
      }
    }

    return { original: origHighlights, translated: transHighlights };
  }, [groupDetail, selectedEvidenceId, enabledCategories]);

  const categoryCounts = useMemo(
    () => (groupDetail ? countEvidenceCategories(groupDetail.items) : {}),
    [groupDetail],
  );

  const toggleCategory = (cat: string) => {
    setEnabledCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) {
        next.delete(cat);
      } else {
        next.add(cat);
      }
      return next;
    });
  };

  const toggleAllCategories = (on: boolean) => {
    setEnabledCategories(on ? new Set(EVIDENCE_CATEGORIES) : new Set());
  };

  if (isLoading) {
    return <BilingualEvidenceSkeleton />;
  }

  if (error || !groupDetail) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <Link
          to={`/evidence-db/${encodeURIComponent(variantSlug)}`}
          className="bev-link"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            fontSize: 14,
            color: "#9ca3af",
            textDecoration: "none",
          }}
        >
          <ArrowLeft style={{ width: 16, height: 16 }} />
          Back to variant detail
        </Link>
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          borderRadius: 12,
          border: "1px solid #fecaca",
          backgroundColor: "#fef2f2",
          padding: 16,
          fontSize: 14,
          color: "#b91c1c",
        }}>
          <AlertCircle style={{ width: 20, height: 20, flexShrink: 0 }} />
          <span>Failed to load evidence data for this literature.</span>
        </div>
      </div>
    );
  }

  return (
    <div className="content-fade-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <style>{bevEmbeddedCSS}</style>

      {/* Breadcrumb */}
      <nav style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 14, color: "#9ca3af" }}>
        <Link
          to="/evidence-db"
          className="bev-link"
          style={{ color: "inherit", textDecoration: "none" }}
        >
          Evidence DB
        </Link>
        <ChevronRight style={{ width: 14, height: 14 }} />
        <Link
          to={`/evidence-db/${encodeURIComponent(variantSlug)}`}
          className="bev-link"
          style={{ color: "inherit", textDecoration: "none", fontFamily: "var(--font-mono)" }}
        >
          {variantSlug.split(":").slice(0, 2).join(":")}
        </Link>
        <ChevronRight style={{ width: 14, height: 14 }} />
        <span style={{
          color: "#9ca3af",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          maxWidth: 300,
        }}>
          {groupDetail.title ?? "Literature"}
        </span>
      </nav>

      {/* Literature Header */}
      <LiteratureHeader groupDetail={groupDetail} />

      {/* Main: Bilingual comparison layout */}
      <div className="bev-main-grid">
        {/* Sidebar: controls + navigator */}
        <BilingualSidebar
          categoryCounts={categoryCounts}
          enabledCategories={enabledCategories}
          toggleCategory={toggleCategory}
          toggleAllCategories={toggleAllCategories}
          items={groupDetail.items}
          selectedEvidenceId={selectedEvidenceId}
          onSelectEvidence={setSelectedEvidenceId}
        />

        {/* Main: bilingual document readers */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Active evidence card */}
          {selectedEvidenceId && (
            <ActiveEvidenceCard
              item={
                groupDetail.items.find(
                  (i) => i.canonical_evidence_id === selectedEvidenceId,
                ) ?? groupDetail.items[0]
              }
            />
          )}

          {/* Bilingual panels */}
          <div className={`bev-bilingual-grid${hasTranslation ? " bev-bilingual-grid--dual" : ""}`}>
            <DocumentReader
              title="Original Text"
              track="original"
              document={originalDoc ?? { track: "original", paragraphs: [] }}
              accentColor="#3B82F6"
              blocks={groupDetail?.original_blocks}
              blockHighlights={buildBlockHighlights.original}
              sourceDocumentId={sourceDocumentId}
              annotations={originalAnnotations}
              onCreateAnnotation={handleCreateAnnotation}
              onUpdateAnnotation={handleUpdateAnnotation}
              onDeleteAnnotation={handleDeleteAnnotation}
            />
            {hasTranslation && (
              <DocumentReader
                title="Translated Text (Chinese)"
                track="translated"
                document={
                  translatedDoc ?? { track: "translated", paragraphs: [] }
                }
                accentColor="#8B5CF6"
                blocks={groupDetail?.translated_blocks}
                blockHighlights={buildBlockHighlights.translated}
                sourceDocumentId={sourceDocumentId}
                annotations={translatedAnnotations}
                onCreateAnnotation={handleCreateAnnotation}
                onUpdateAnnotation={handleUpdateAnnotation}
                onDeleteAnnotation={handleDeleteAnnotation}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
