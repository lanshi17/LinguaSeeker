import { useParams } from "react-router-dom";
import { Typography } from "antd";
import { Database } from "lucide-react";
import { VariantIndexView, VariantDetailView, BilingualEvidenceView } from "@/features/evidence-db";
import { useI18n } from "@/lib/i18n";

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
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 48,
            height: 48,
            flexShrink: 0,
            borderRadius: 12,
            background: "linear-gradient(to bottom right, var(--color-primary-500), var(--color-primary-700))",
            boxShadow: "0 4px 6px -1px rgba(6, 182, 212, 0.2)",
          }}
        >
          <Database size={24} color="var(--color-surface)" />
        </div>
        <div>
          <Typography.Title
            level={3}
            style={{
              margin: 0,
              fontFamily: "var(--font-display)",
              fontWeight: 600,
              letterSpacing: "-0.025em",
            }}
          >
            {t("evidenceDb.title")}
          </Typography.Title>
          <Typography.Text type="secondary" style={{ fontSize: 14 }}>
            {t("evidenceDb.description")}
          </Typography.Text>
        </div>
      </div>

      <VariantIndexView />
    </div>
  );
}
