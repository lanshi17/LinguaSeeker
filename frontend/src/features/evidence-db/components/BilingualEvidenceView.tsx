import { useState, useMemo, useRef, useCallback, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  AlertCircle,
  ChevronRight,
  CircleHelp,
} from "lucide-react";
import { Switch, Tooltip } from "antd";
import { useEvidenceGroupDetail } from "@/features/evidence-search/hooks/useEvidenceGroupDetail";
import {
  EVIDENCE_CATEGORIES,
  buildEvidenceDocument,
  buildBlockHighlightsFromValues,
  hasTranslatedDocumentText,
  countEvidenceCategories,
} from "@/features/evidence-search/utils/evidenceDocument";
import {
  buildAlignmentHighlightMap,
  buildAlignmentHighlightsForBlocks,
  type AlignmentInteractionState,
} from "@/features/evidence-search/utils/translationAlignment";
import { BilingualEvidenceSkeleton } from "./BilingualEvidenceSkeleton";
import { DocumentReader } from "./DocumentReader";
import type { FieldTypeOption } from "@/features/evidence-search/components/annotationLayer";
import type { ReviewContextMap } from "./HighlightedText";
import { FieldReviewMenu } from "@/features/evidence-search/components/FieldReviewPopover";
import type { FieldReviewInfo } from "@/features/evidence-search/components/FieldReviewPopover";
import type { BlockHighlight } from "./StructuredBlockRenderer";
import { ActiveEvidenceCard } from "./ActiveEvidenceCard";
import { LiteratureHeader } from "./LiteratureHeader";
import { BilingualSidebar } from "./BilingualSidebar";
import { bevEmbeddedCSS } from "./bevStyles";
import { PageGuide, type GuideSection } from "@/components/ui/PageGuide";
import { ExportReportDrawer } from "@/features/evidence-search/components/ExportReportDrawer";
import { computeLiteratureQuality } from "../utils/fieldModel";
import {
  createScrollSyncHandler,
  loadScrollSyncSetting,
  saveScrollSyncSetting,
} from "../utils/scrollSync";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createAnnotation,
  deleteAnnotation,
  listAnnotations,
  updateAnnotation,
} from "@/features/evidence-search/services/annotations";
import type {
  AnnotationCreateRequest,
  AnnotationTrack,
  AnnotationUpdateRequest,
  UserAnnotation,
} from "@/features/evidence-search/types/annotations";
import type {
  EvidenceChainHighlight,
  EvidenceGroupItem,
  EvidenceTrackTrace,
  ReviewStatusValue,
} from "@/features/evidence-search/types/evidenceSearch";
import { patchEvidence } from "@/features/evidence-search/services/evidenceCorrection";
import { App } from "antd";
import { useI18n } from "@/lib/i18n";
import { EVIDENCE_FIELD_SPECS } from "@/lib/constants/evidenceFields";

const REVIEW_STATUSES: ReviewStatusValue[] = [
  "provisional",
  "approved",
  "corrected",
  "rejected",
];

function categoryFromItem(item: EvidenceGroupItem): string | null {
  return item.category ?? (item.field_id.includes(".") ? item.field_id.split(".")[0] : null);
}

function hasSourceSpan(highlight?: EvidenceChainHighlight | null): boolean {
  return Boolean(
    highlight &&
      Object.keys(highlight.source_span ?? {}).length > 0 &&
      highlight.highlight_end > highlight.highlight_start,
  );
}

function traceHasSourceSpan(trace?: EvidenceTrackTrace): boolean {
  return Boolean(trace && (hasSourceSpan(trace.original) || hasSourceSpan(trace.translated)));
}

/* ── Main View ──────────────────────────────────────────── */

export function BilingualEvidenceView({
  variantSlug,
  sourceDocumentId,
}: {
  variantSlug: string;
  sourceDocumentId: string;
}) {
  const { t } = useI18n();
  const [enabledCategories, setEnabledCategories] = useState<Set<string>>(
    () => new Set(EVIDENCE_CATEGORIES),
  );
  const [enabledStatuses, setEnabledStatuses] = useState<Set<string>>(
    () => new Set(REVIEW_STATUSES),
  );
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<
    string | undefined
  >(undefined);
  const [reviewSubmittingStatus, setReviewSubmittingStatus] =
    useState<ReviewStatusValue | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [guideOpen, setGuideOpen] = useState(false);
  const [hoveredAlignmentPairId, setHoveredAlignmentPairId] = useState<string | null>(null);
  const [pinnedAlignmentPairId, setPinnedAlignmentPairId] = useState<string | null>(null);

  // ── Scroll sync state ──────────────────────────────────────────────
  const [isScrollSyncEnabled, setIsScrollSyncEnabled] = useState(loadScrollSyncSetting);
  const isProgrammaticScroll = useRef(false);
  const originalScrollRef = useRef<HTMLDivElement | null>(null);
  const translatedScrollRef = useRef<HTMLDivElement | null>(null);

  const toggleScrollSync = useCallback((enabled: boolean) => {
    setIsScrollSyncEnabled(enabled);
    saveScrollSyncSetting(enabled);
  }, []);
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

  // original → translated, and translated → original
  const handleOriginalScroll = createScrollSyncHandler(
    translatedScrollRef,
    isProgrammaticScroll,
    isScrollSyncEnabled,
  );
  const handleTranslatedScroll = createScrollSyncHandler(
    originalScrollRef,
    isProgrammaticScroll,
    isScrollSyncEnabled,
  );

  const {
    detail: groupDetail,
    isLoading,
    error,
  } = useEvidenceGroupDetail(undefined, sourceDocumentId);
  const queryClient = useQueryClient();
  const { message } = App.useApp();
  const refreshEvidenceReviewData = useCallback(async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["evidence", "group-detail"] }),
      queryClient.invalidateQueries({ queryKey: ["evidence", "search"] }),
      queryClient.invalidateQueries({ queryKey: ["evidence-db"] }),
    ]);
  }, [queryClient]);

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

  useEffect(() => {
    if (!groupDetail?.items.length) {
      return;
    }
    if (
      selectedEvidenceId &&
      groupDetail.items.some((item) => item.canonical_evidence_id === selectedEvidenceId)
    ) {
      return;
    }
    const firstReviewTarget =
      groupDetail.items.find((item) => item.review_status === "provisional") ??
      groupDetail.items[0];
    setSelectedEvidenceId(firstReviewTarget.canonical_evidence_id);
  }, [groupDetail, selectedEvidenceId]);

  const handleReviewStatusChange = useCallback(async (
    evidenceId: string,
    status: ReviewStatusValue,
  ) => {
    setReviewSubmittingStatus(status);
    try {
      await patchEvidence(evidenceId, { fields: {}, new_status: status });
      await refreshEvidenceReviewData();
      message.success(t("evidence.review.success", { status: t(`evidenceDb.review.${status}`) }));
    } catch {
      message.error(t("evidence.review.error"));
    } finally {
      setReviewSubmittingStatus(null);
    }
  }, [message, refreshEvidenceReviewData, t]);

  const handleAssignField = useCallback(async (selectedText: string, fieldType: string) => {
    if (!groupDetail) return;
    // Find an existing item for this field type, or use the first item
    const targetItem = groupDetail.items.find(
      (item) => item.field_id === fieldType || item.category === fieldType,
    ) ?? groupDetail.items[0];
    if (!targetItem) return;
    try {
      await patchEvidence(targetItem.canonical_evidence_id, {
        fields: { [fieldType]: selectedText },
        change_reason: `Text selection assignment to ${fieldType}`,
      });
      await refreshEvidenceReviewData();
      message.success(t("evidence.fieldAssign.success", { field: fieldType }));
    } catch {
      message.error(t("evidence.fieldAssign.error"));
    }
  }, [groupDetail, message, refreshEvidenceReviewData, t]);

  const fieldTypes = useMemo<FieldTypeOption[]>(
    () => EVIDENCE_FIELD_SPECS.map((spec) => ({
      fieldId: spec.fieldId,
      label: spec.fieldName,
      category: spec.categoryId,
    })),
    [],
  );

  const guideSections: GuideSection[] = useMemo(() => [
    { title: t("pageGuide.bilingual.s1.title"), items: [
      t("pageGuide.bilingual.s1.i1"), t("pageGuide.bilingual.s1.i2"),
      t("pageGuide.bilingual.s1.i3"),
    ]},
    { title: t("pageGuide.bilingual.s2.title"), items: [
      t("pageGuide.bilingual.s2.i1"), t("pageGuide.bilingual.s2.i2"),
      t("pageGuide.bilingual.s2.i3"),
    ]},
    { title: t("pageGuide.bilingual.s3.title"), items: [
      t("pageGuide.bilingual.s3.i1"), t("pageGuide.bilingual.s3.i2"),
      t("pageGuide.bilingual.s3.i3"),
    ]},
    { title: t("pageGuide.bilingual.s4.title"), items: [
      t("pageGuide.bilingual.s4.i1"), t("pageGuide.bilingual.s4.i2"),
      t("pageGuide.bilingual.s4.i3"),
    ]},
    { title: t("pageGuide.bilingual.s5.title"), items: [
      t("pageGuide.bilingual.s5.i1"), t("pageGuide.bilingual.s5.i2"),
      t("pageGuide.bilingual.s5.i3"), t("pageGuide.bilingual.s5.i4"),
    ]},
  ], [t]);

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

  const originalAlignmentHighlights = useMemo(
    () =>
      groupDetail && originalDoc
        ? buildAlignmentHighlightMap(groupDetail, originalDoc, "original", alignmentState)
        : {},
    [alignmentState, groupDetail, originalDoc],
  );

  const translatedAlignmentHighlights = useMemo(
    () =>
      groupDetail && translatedDoc
        ? buildAlignmentHighlightMap(groupDetail, translatedDoc, "translated", alignmentState)
        : {},
    [alignmentState, groupDetail, translatedDoc],
  );

  const hasTranslation = groupDetail
    ? hasTranslatedDocumentText(groupDetail)
    : false;
  // Build block-level highlights by searching evidence values in the
  // concatenated block text. Falls back from trace-based spans (often
  // empty) to value-based full-text search — same algorithm as
  // buildEvidenceDocument but mapped to the block offset coordinate space.
  const buildBlockHighlights = useMemo((): { original: BlockHighlight[]; translated: BlockHighlight[] } => {
    if (!groupDetail) return { original: [], translated: [] };
    const origBlocks = groupDetail.original_blocks;
    const transBlocks = groupDetail.translated_blocks;
    return {
      original: origBlocks && origBlocks.length > 0
        ? buildBlockHighlightsFromValues(origBlocks, groupDetail, "original", selectedEvidenceId, enabledCategories)
        : [],
      translated: transBlocks && transBlocks.length > 0
        ? buildBlockHighlightsFromValues(transBlocks, groupDetail, "translated", selectedEvidenceId, enabledCategories)
        : [],
    };
  }, [groupDetail, selectedEvidenceId, enabledCategories]);

  const buildBlockAlignmentHighlights = useMemo(() => {
    if (!groupDetail) return { original: [], translated: [] };
    return {
      original: buildAlignmentHighlightsForBlocks(
        groupDetail.original_blocks,
        groupDetail,
        "original",
        alignmentState,
      ),
      translated: buildAlignmentHighlightsForBlocks(
        groupDetail.translated_blocks,
        groupDetail,
        "translated",
        alignmentState,
      ),
    };
  }, [alignmentState, groupDetail]);

  const categoryCounts = useMemo(
    () => (groupDetail ? countEvidenceCategories(groupDetail.items.filter((i) => i.value?.trim())) : {}),
    [groupDetail],
  );

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const item of groupDetail?.items ?? []) {
      counts[item.review_status] = (counts[item.review_status] ?? 0) + 1;
    }
    return counts;
  }, [groupDetail]);

  const navigatorItems = useMemo(() => {
    if (!groupDetail) return [];
    return groupDetail.items.filter((item) => {
      const cat = categoryFromItem(item);
      const categoryEnabled = cat ? enabledCategories.has(cat) : true;
      return categoryEnabled && enabledStatuses.has(item.review_status);
    });
  }, [enabledCategories, enabledStatuses, groupDetail]);

  const literatureQuality = useMemo(
    () => (groupDetail ? computeLiteratureQuality(groupDetail) : null),
    [groupDetail],
  );

  const selectedItem = useMemo(
    () =>
      groupDetail?.items.find(
        (item) => item.canonical_evidence_id === selectedEvidenceId,
      ) ?? groupDetail?.items[0],
    [groupDetail, selectedEvidenceId],
  );

  const selectedTrace = useMemo(
    () =>
      groupDetail?.traces.find(
        (trace) => trace.canonical_evidence_id === selectedEvidenceId,
      ),
    [groupDetail, selectedEvidenceId],
  );

  // Build review context map for hover-to-review on highlight marks
  const reviewContexts = useMemo<ReviewContextMap>(() => {
    if (!groupDetail) return new Map();
    const map = new Map<string, FieldReviewInfo>();
    for (const item of groupDetail.items) {
      map.set(item.canonical_evidence_id, {
        evidenceId: item.canonical_evidence_id,
        fieldId: item.field_id,
        label: item.field_name ?? item.field_id,
        category: item.category,
        currentStatus: item.review_status,
        value: item.value,
        groupId: groupDetail.group_id,
      });
    }
    return map;
  }, [groupDetail]);


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

  const toggleStatus = (status: string) => {
    setEnabledStatuses((prev) => {
      const next = new Set(prev);
      if (next.has(status)) {
        next.delete(status);
      } else {
        next.add(status);
      }
      return next;
    });
  };

  const toggleAllStatuses = (on: boolean) => {
    setEnabledStatuses(on ? new Set(REVIEW_STATUSES) : new Set());
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
            color: "var(--color-text-muted)",
            textDecoration: "none",
          }}
        >
          <ArrowLeft style={{ width: 16, height: 16 }} />
          {t("evidenceDb.bilingual.back")}
        </Link>
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          borderRadius: 12,
          border: "1px solid var(--color-error-border)",
          backgroundColor: "var(--color-error-bg)",
          padding: 16,
          fontSize: 14,
          color: "var(--color-error-text)",
        }}>
          <AlertCircle style={{ width: 20, height: 20, flexShrink: 0 }} />
          <span>{t("evidenceDb.bilingual.loadError")}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="content-fade-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <style>{bevEmbeddedCSS}</style>
      <FieldReviewMenu onReviewed={refreshEvidenceReviewData} />

      {/* Breadcrumb */}
      <nav style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 14, color: "var(--color-text-muted)" }}>
        <Link
          to="/evidence-db"
          className="bev-link"
          style={{ color: "inherit", textDecoration: "none" }}
        >
          {t("evidenceDb.bilingual.breadcrumb")}
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
          flex: 1,
          color: "var(--color-text-muted)",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          maxWidth: 300,
        }}>
          {groupDetail.title ?? t("evidenceDb.bilingual.litFallback")}
        </span>
        <button
          onClick={() => setGuideOpen(true)}
          aria-label={t("pageGuide.openGuide")}
          style={{
            display: "flex", alignItems: "center", gap: 4, flexShrink: 0,
            background: "none", border: "1px solid var(--color-border)",
            borderRadius: 6, padding: "3px 8px", cursor: "pointer",
            color: "var(--color-text-secondary)", fontSize: 12,
            transition: "color 0.15s, border-color 0.15s",
          }}
        >
          <CircleHelp size={14} />
          {t("pageGuide.help")}
        </button>
      </nav>

      {/* Literature Header */}
      <LiteratureHeader
        groupDetail={groupDetail}
        quality={literatureQuality ?? undefined}
        onExportReport={() => setExportOpen(true)}
      />

      {/* Main: Bilingual comparison layout */}
      <div className="bev-main-grid">
        {/* Sidebar: controls + navigator */}
        <BilingualSidebar
          categoryCounts={categoryCounts}
          enabledCategories={enabledCategories}
          toggleCategory={toggleCategory}
          toggleAllCategories={toggleAllCategories}
          statusCounts={statusCounts}
          enabledStatuses={enabledStatuses}
          toggleStatus={toggleStatus}
          toggleAllStatuses={toggleAllStatuses}
          items={navigatorItems}
          selectedEvidenceId={selectedEvidenceId}
          onSelectEvidence={setSelectedEvidenceId}
        />

        {/* Main: bilingual document readers */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Active evidence card */}
          {selectedItem && (
            <ActiveEvidenceCard
              item={selectedItem}
              sourceSpanAvailable={traceHasSourceSpan(selectedTrace)}
              onReviewStatusChange={(status) => {
                void handleReviewStatusChange(selectedItem.canonical_evidence_id, status);
              }}
              reviewSubmittingStatus={reviewSubmittingStatus}
            />
          )}
          {/* Sync control + bilingual panels */}
          {hasTranslation && (
            <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 8 }}>
              <Tooltip title={t("evidenceDb.bilingual.syncScroll")}>
                <span style={{ fontSize: 13, color: "var(--color-text-secondary)", display: "inline-flex", alignItems: "center", gap: 6 }}>
                  {t("evidenceDb.bilingual.syncScroll")}
                  <Switch
                    size="small"
                    checked={isScrollSyncEnabled}
                    onChange={toggleScrollSync}
                  />
                </span>
              </Tooltip>
            </div>
          )}

          <div className={`bev-bilingual-grid${hasTranslation ? " bev-bilingual-grid--dual" : ""}`}>
            <DocumentReader
              title={t("evidenceDb.bilingual.originalText")}
              track="original"
              document={originalDoc ?? { track: "original", paragraphs: [] }}
              accentColor="#3B82F6"
              blocks={groupDetail?.original_blocks}
              blockHighlights={buildBlockHighlights.original}
              blockAlignmentHighlights={buildBlockAlignmentHighlights.original}
              alignmentHighlightsByParagraph={originalAlignmentHighlights}
              sourceDocumentId={sourceDocumentId}
              annotations={originalAnnotations}
              reviewContexts={reviewContexts}
              scrollContainerRef={originalScrollRef}
              onContainerScroll={handleOriginalScroll}
              onCreateAnnotation={handleCreateAnnotation}
              onUpdateAnnotation={handleUpdateAnnotation}
              onDeleteAnnotation={handleDeleteAnnotation}
              onAlignmentHover={setHoveredAlignmentPairId}
              onAlignmentLeave={() => setHoveredAlignmentPairId(null)}
              onAlignmentToggle={handleAlignmentToggle}
              onAssignField={handleAssignField}
              fieldTypes={fieldTypes}
            />
            {hasTranslation && (
              <DocumentReader
                title={t("evidenceDb.bilingual.translatedText")}
                track="translated"
                document={
                  translatedDoc ?? { track: "translated", paragraphs: [] }
                }
                accentColor="#8B5CF6"
                blocks={groupDetail?.translated_blocks}
                blockHighlights={buildBlockHighlights.translated}
                blockAlignmentHighlights={buildBlockAlignmentHighlights.translated}
                alignmentHighlightsByParagraph={translatedAlignmentHighlights}
                sourceDocumentId={sourceDocumentId}
                annotations={translatedAnnotations}
                reviewContexts={reviewContexts}
                scrollContainerRef={translatedScrollRef}
                onContainerScroll={handleTranslatedScroll}
                onCreateAnnotation={handleCreateAnnotation}
                onUpdateAnnotation={handleUpdateAnnotation}
                onDeleteAnnotation={handleDeleteAnnotation}
                onAlignmentHover={setHoveredAlignmentPairId}
                onAlignmentLeave={() => setHoveredAlignmentPairId(null)}
                onAlignmentToggle={handleAlignmentToggle}
                onAssignField={handleAssignField}
                fieldTypes={fieldTypes}
              />
            )}
          </div>
        </div>
      </div>

      <ExportReportDrawer
        detail={groupDetail}
        open={exportOpen}
        onClose={() => setExportOpen(false)}
      />

      <PageGuide
        open={guideOpen}
        onClose={() => setGuideOpen(false)}
        title={t("pageGuide.bilingual.title")}
        sections={guideSections}
      />
    </div>
  );
}
