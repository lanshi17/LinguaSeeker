import { useState, useMemo, useCallback } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Typography } from "antd";
import { Database, CircleHelp, Dna, BookOpen, FileText, TrendingUp } from "lucide-react";
import { VariantIndexView, VariantDetailView, BilingualEvidenceView } from "@/features/evidence-db";
import { ClassificationDistributionBar } from "@/features/evidence-db/components/ClassificationDistributionBar";
import { fetchAllEvidence } from "@/features/evidence-db/services/variantDb";
import { aggregateVariants } from "@/features/evidence-db/utils/variantAggregation";
import { formatConfidencePercent } from "@/features/evidence-db/utils/fieldLabels";
import type { ClassificationLevel } from "@/features/evidence-db/types/variantDb";
import { useI18n } from "@/lib/i18n";
import { PageGuide, type GuideSection } from "@/components/ui/PageGuide";
import "@/features/evidence-db/evidence-db.css";

/**
 * Evidence Database page — routes between three levels via URL params:
 *
 * L1 /evidence-db                                — variant index (all variants)
 * L2 /evidence-db/:variantSlug                   — single variant detail + references
 * L3 /evidence-db/:variantSlug/:sourceDocumentId — bilingual evidence comparison
 */
export function EvidenceDbPage() {
  const { variantSlug, sourceDocumentId } = useParams();
  const { t } = useI18n();
  const [guideOpen, setGuideOpen] = useState(false);
  const [activeClassification, setActiveClassification] = useState<ClassificationLevel | null>(null);

  // Share the same React Query cache as VariantIndexView
  const query = useQuery({
    queryKey: ["evidence-db", "all-evidence"],
    queryFn: () => fetchAllEvidence({ page: 1, page_size: 1000 }),
    staleTime: 60_000,
  });

  const allEntries = useMemo(
    () => (query.data?.items ? aggregateVariants(query.data.items) : []),
    [query.data],
  );

  const stats = useMemo(() => {
    if (allEntries.length === 0) return null;
    const groupDocPairs = new Set<string>();
    const distinctDocs = new Set<string>();
    const groupConfidences = new Map<string, number>();
    for (const e of allEntries) {
      for (const gid of e.groupIds) {
        if (!groupConfidences.has(gid)) groupConfidences.set(gid, e.avgConfidence);
        for (const docId of e.sourceDocumentIds) {
          groupDocPairs.add(`${gid}\0${docId}`);
        }
      }
      for (const docId of e.sourceDocumentIds) distinctDocs.add(docId);
    }
    const distribution: Record<ClassificationLevel, number> = {
      pathogenic: 0, likely_pathogenic: 0, uncertain: 0, likely_benign: 0, benign: 0,
    };
    for (const e of allEntries) distribution[e.classificationLevel]++;
    return {
      totalVariants: allEntries.length,
      totalEvidenceGroups: groupDocPairs.size,
      totalLiterature: distinctDocs.size,
      avgConfidence: groupConfidences.size > 0
        ? [...groupConfidences.values()].reduce((s, c) => s + c, 0) / groupConfidences.size
        : 0,
      distribution,
    };
  }, [allEntries]);

  const handleClassificationClick = useCallback((level: ClassificationLevel) => {
    setActiveClassification((prev) => (prev === level ? null : level));
  }, []);

  const guideSections: GuideSection[] = useMemo(() => [
    { title: t("pageGuide.evidenceDb.s1.title"), items: [
      t("pageGuide.evidenceDb.s1.i1"), t("pageGuide.evidenceDb.s1.i2"),
      t("pageGuide.evidenceDb.s1.i3"), t("pageGuide.evidenceDb.s1.i4"),
    ]},
    { title: t("pageGuide.evidenceDb.s2.title"), items: [
      t("pageGuide.evidenceDb.s2.i1"), t("pageGuide.evidenceDb.s2.i2"),
      t("pageGuide.evidenceDb.s2.i3"),
    ]},
    { title: t("pageGuide.evidenceDb.s3.title"), items: [
      t("pageGuide.evidenceDb.s3.i1"), t("pageGuide.evidenceDb.s3.i2"),
      t("pageGuide.evidenceDb.s3.i3"),
    ]},
  ], [t]);

  // L3: bilingual evidence comparison
  if (variantSlug && sourceDocumentId) {
    return <BilingualEvidenceView variantSlug={variantSlug} sourceDocumentId={sourceDocumentId} />;
  }

  // L2: variant detail
  if (variantSlug) {
    return <VariantDetailView variantSlug={variantSlug} />;
  }

  // L1: variant index — the default landing
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Hero section — distinctive header with classification bar */}
      <section
        style={{
          borderRadius: 14,
          border: "1px solid var(--color-border)",
          backgroundColor: "var(--color-surface)",
          overflow: "hidden",
        }}
      >
        {/* Top bar with title and help */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            padding: "20px 24px 0",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 36,
                height: 36,
                flexShrink: 0,
                borderRadius: 8,
                border: "1.5px solid var(--color-primary-400)",
                color: "var(--color-primary-600)",
                backgroundColor: "var(--color-primary-50)",
              }}
            >
              <Database size={18} />
            </div>
            <div style={{ minWidth: 0 }}>
              <Typography.Text
                style={{
                  fontSize: 10,
                  fontWeight: 600,
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                  color: "var(--color-text-secondary)",
                  display: "block",
                  marginBottom: 2,
                }}
              >
                {t("evidenceDb.title")}
              </Typography.Text>
              <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                {t("evidenceDb.description")}
              </Typography.Text>
            </div>
          </div>
          <button
            onClick={() => setGuideOpen(true)}
            aria-label={t("pageGuide.openGuide")}
            style={{
              display: "flex", alignItems: "center", gap: 4, flexShrink: 0,
              background: "none", border: "1px solid var(--color-border)",
              borderRadius: 6, padding: "4px 10px", cursor: "pointer",
              color: "var(--color-text-secondary)", fontSize: 12,
              transition: "color 0.15s, border-color 0.15s",
            }}
          >
            <CircleHelp size={14} />
            {t("pageGuide.help")}
          </button>
        </div>

        {/* Quick stats row */}
        {stats && (
          <div className="edb-hero-stats">
            {[
              { icon: Dna, label: t("evidenceDb.hero.variants"), value: String(stats.totalVariants) },
              { icon: FileText, label: t("evidenceDb.hero.evidenceGroups"), value: String(stats.totalEvidenceGroups) },
              { icon: BookOpen, label: t("evidenceDb.hero.literature"), value: String(stats.totalLiterature) },
              { icon: TrendingUp, label: t("evidenceDb.hero.confidence"), value: formatConfidencePercent(stats.avgConfidence) },
            ].map((s) => {
              const Icon = s.icon;
              return (
                <div
                  key={s.label}
                  className="edb-hero-stat-item"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "12px 16px",
                  }}
                >
                  <Icon size={16} style={{ color: "var(--color-primary-600)", flexShrink: 0 }} />
                  <div style={{ minWidth: 0 }}>
                    <div
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 18,
                        fontWeight: 600,
                        color: "var(--color-text)",
                        lineHeight: 1.2,
                      }}
                    >
                      {s.value}
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        fontWeight: 500,
                        color: "var(--color-text-muted)",
                        letterSpacing: "0.03em",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {s.label}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Classification distribution bar — the signature visual */}
        {stats && (
          <div style={{ padding: "16px 24px 20px" }}>
            <ClassificationDistributionBar
              distribution={stats.distribution}
              activeLevel={activeClassification}
              onSegmentClick={handleClassificationClick}
            />
          </div>
        )}
      </section>

      <VariantIndexView
        activeClassification={activeClassification}
        onClearClassification={() => setActiveClassification(null)}
      />

      <PageGuide
        open={guideOpen}
        onClose={() => setGuideOpen(false)}
        title={t("pageGuide.evidenceDb.title")}
        sections={guideSections}
      />
    </div>
  );
}
