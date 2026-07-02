import { useSearchParams, Navigate } from "react-router-dom";
import { Typography } from "antd";
import { EvidenceDetailView } from "@/features/evidence-search";
import { BookOpen, Columns2 } from "lucide-react";
import { useI18n } from "@/lib/i18n";

export function EvidenceDetailPage() {
  const { t } = useI18n();
  const [searchParams] = useSearchParams();
  const evidenceId = searchParams.get("evidenceId") ?? undefined;
  const groupId = searchParams.get("groupId");
  const view = searchParams.get("view");

  if (!groupId) {
    return <Navigate to="/evidence" replace />;
  }

  const isCompareView = view === "compare";

  const iconStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    width: 36,
    height: 36,
    flexShrink: 0,
    borderRadius: 6,
    border: "1px solid var(--color-border)",
    color: "var(--color-primary-600)",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Page header with icon */}
      <div className="no-print" style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={iconStyle}>
          {isCompareView ? (
            <Columns2 size={18} />
          ) : (
            <BookOpen size={18} />
          )}
        </div>
        <div>
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
            {isCompareView ? t("evidenceDetail.compareTitle") : t("evidenceDetail.title")}
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
            {isCompareView ? t("evidenceDetail.compareDescription") : t("evidenceDetail.description")}
          </Typography.Text>
        </div>
      </div>

      <EvidenceDetailView
        groupId={groupId}
        initialEvidenceId={evidenceId}
        initialView={isCompareView ? "compare" : "overview"}
      />
    </div>
  );
}
