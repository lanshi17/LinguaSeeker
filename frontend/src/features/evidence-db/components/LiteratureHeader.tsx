import { Button } from "antd";
import { BookOpen, Download, ExternalLink } from "lucide-react";
import type { EvidenceGroupDetailResponse } from "@/features/evidence-search/types/evidenceSearch";

/* ── Literature Header ──────────────────────────────────── */

export function LiteratureHeader({
  groupDetail,
  onExportReport,
}: {
  groupDetail: EvidenceGroupDetailResponse;
  onExportReport?: () => void;
}) {
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
            {groupDetail.title ?? "Untitled Document"}
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
                PMID:{groupDetail.pmid}
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
                DOI:{groupDetail.doi.slice(0, 30)}
                <ExternalLink style={{ width: 12, height: 12 }} />
              </a>
            )}
            <span>{groupDetail.item_count} evidence fields</span>
            {groupDetail.avg_confidence != null && (
              <span>
                {Math.round(groupDetail.avg_confidence * 100)}% confidence
              </span>
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
            Export report
          </Button>
        )}
      </div>
    </section>
  );
}
