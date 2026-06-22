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
import { useVariantDetail } from "../hooks/useVariantDetail";
import { BilingualEvidenceSkeleton } from "./BilingualEvidenceSkeleton";
import { DocumentReader } from "./DocumentReader";
import { ActiveEvidenceCard } from "./ActiveEvidenceCard";
import { LiteratureHeader } from "./LiteratureHeader";
import { BilingualSidebar } from "./BilingualSidebar";
import { bevEmbeddedCSS } from "./bevStyles";

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

  const { detail: variantDetail, isLoading: isVariantLoading } =
    useVariantDetail(variantSlug);

  const groupId = useMemo(() => {
    if (!variantDetail) return null;
    const group = variantDetail.evidenceGroups.find(
      (g) => g.source_document_id === sourceDocumentId,
    );
    return group?.group_id ?? variantDetail.entry.groupIds[0] ?? null;
  }, [variantDetail, sourceDocumentId]);

  const {
    detail: groupDetail,
    isLoading: isGroupLoading,
    error,
  } = useEvidenceGroupDetail(groupId ?? "");

  const isLoading = isVariantLoading || isGroupLoading;

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
            />
            {hasTranslation && (
              <DocumentReader
                title="Translated Text (Chinese)"
                track="translated"
                document={
                  translatedDoc ?? { track: "translated", paragraphs: [] }
                }
                accentColor="#8B5CF6"
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
