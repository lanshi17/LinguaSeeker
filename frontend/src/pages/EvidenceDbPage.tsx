import { useState, useMemo } from "react";
import { useParams } from "react-router-dom";
import { Typography } from "antd";
import { Database, CircleHelp } from "lucide-react";
import { VariantIndexView, VariantDetailView, BilingualEvidenceView } from "@/features/evidence-db";
import { useI18n } from "@/lib/i18n";
import { PageGuide, type GuideSection } from "@/components/ui/PageGuide";

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

  // L1: variant index
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Page Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 36,
            height: 36,
            flexShrink: 0,
            borderRadius: 6,
            border: "1px solid var(--color-border)",
            color: "var(--color-primary-600)",
          }}
        >
          <Database size={18} />
        </div>
        <div style={{ flex: 1 }}>
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

      <VariantIndexView />

      <PageGuide
        open={guideOpen}
        onClose={() => setGuideOpen(false)}
        title={t("pageGuide.evidenceDb.title")}
        sections={guideSections}
      />
    </div>
  );
}
