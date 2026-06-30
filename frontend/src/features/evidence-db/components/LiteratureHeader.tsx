import { Button } from "antd";
import { BookOpen, Download, ExternalLink } from "lucide-react";
import type { EvidenceGroupDetailResponse } from "@/features/evidence-search/types/evidenceSearch";
import type { ReviewProgress } from "../utils/fieldModel";
import {
  getEvidenceDbLabels,
  formatConfidencePercent,
  formatReviewedCount,
} from "../utils/fieldLabels";
import { useI18n } from "@/lib/i18n";

/* ── Literature Header ──────────────────────────────────── */

export interface LiteratureHeaderQuality {
  hasFullText: boolean;
  hasTranslation: boolean;
  reviewProgress: ReviewProgress;
}

function qualityBadgeStyle(tone: "source" | "translation") {
  const styles = {
    source: {
      border: "1px solid #bfdbfe",
      backgroundColor: "#eff6ff",
      color: "#1d4ed8",
    },
    translation: {
      border: "1px solid #ddd6fe",
      backgroundColor: "#f5f3ff",
      color: "#6d28d9",
    },
  };
  return {
    display: "inline-flex",
    alignItems: "center",
    borderRadius: 999,
    padding: "2px 8px",
    fontSize: 12,
    fontWeight: 500,
    ...styles[tone],
  };
}

export function LiteratureHeader({
  groupDetail,
  quality,
  onExportReport,
}: {
  groupDetail: EvidenceGroupDetailResponse;
  quality?: LiteratureHeaderQuality;
  onExportReport?: () => void;
}) {
  const { t } = useI18n();
  const labels = getEvidenceDbLabels(t);

  return (
    <section style={{
      borderRadius: 12,
      border: "1px solid #e5e7eb",
      backgroundColor: "#fff",
      padding: 20,
    }}>
      <div className="bev-literature-header-content" style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
        <div style={{
          display: "flex",
          width: 40,
          height: 40,
          flexShrink: 0,
          alignItems: "center",
          justifyContent: "center",
          borderRadius: 8,
          backgroundColor: "#fffbeb",
          color: "#d97706",
        }}>
          <BookOpen style={{ width: 20, height: 20 }} />
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <h1 style={{
            fontFamily: "var(--font-display)",
            fontSize: 18,
            fontWeight: 500,
            color: "#111827",
            lineHeight: 1.375,
            margin: 0,
          }}>
            {groupDetail.title ?? t("evidenceDb.header.untitled")}
          </h1>
          <div style={{
            marginTop: 6,
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            columnGap: 12,
            rowGap: 4,
            fontSize: 12,
            color: "#6b7280",
          }}>
            {groupDetail.pmid && (
              <a
                href={`https://pubmed.ncbi.nlm.nih.gov/${groupDetail.pmid}`}
                target="_blank"
                rel="noopener noreferrer"
                className="bev-pmid-link"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  fontFamily: "var(--font-mono)",
                  color: "var(--color-primary-600)",
                  textDecoration: "none",
                }}
              >
                {t("evidenceDb.header.pmid")}{groupDetail.pmid}
                <ExternalLink style={{ width: 12, height: 12 }} />
              </a>
            )}
            {groupDetail.doi && (
              <a
                href={`https://doi.org/${groupDetail.doi}`}
                target="_blank"
                rel="noopener noreferrer"
                className="bev-pmid-link"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  fontFamily: "var(--font-mono)",
                  color: "var(--color-primary-600)",
                  textDecoration: "none",
                }}
              >
                {t("evidenceDb.header.doi")}{groupDetail.doi.slice(0, 30)}
                <ExternalLink style={{ width: 12, height: 12 }} />
              </a>
            )}
            <span>{groupDetail.item_count} {t("evidenceDb.header.evidenceFields")}</span>
            {groupDetail.avg_confidence != null && (
              <span>
                {formatConfidencePercent(groupDetail.avg_confidence)} {t("evidenceDb.header.confidence")}
              </span>
            )}
            {quality?.hasFullText && (
              <span style={qualityBadgeStyle("source")}>{t("evidenceDb.header.fullText")}</span>
            )}
            {quality?.hasTranslation && (
              <span style={qualityBadgeStyle("translation")}>{t("evidenceDb.header.translated")}</span>
            )}
            {quality && (
              <span>{formatReviewedCount(quality.reviewProgress, t)}</span>
            )}
          </div>
        </div>
        {onExportReport && (
          <Button
            type="primary"
            icon={<Download style={{ width: 16, height: 16 }} />}
            onClick={onExportReport}
            style={{ flexShrink: 0 }}
          >
            {labels.exportReport}
          </Button>
        )}
      </div>
    </section>
  );
}
