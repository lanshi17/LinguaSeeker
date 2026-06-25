import { useSearchParams, Navigate } from "react-router-dom";
import { Typography } from "antd";
import { EvidenceDetailView } from "@/features/evidence-search";
import { BookOpen, Columns2 } from "lucide-react";

export function EvidenceDetailPage() {
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
    width: 48,
    height: 48,
    flexShrink: 0,
    borderRadius: 12,
    background: isCompareView
      ? "linear-gradient(to bottom right, #a855f7, #7e22ce)"
      : "linear-gradient(to bottom right, var(--color-primary-500), var(--color-primary-700))",
    boxShadow: isCompareView
      ? "0 4px 6px -1px rgba(168, 85, 247, 0.25)"
      : "0 4px 6px -1px rgba(6, 182, 212, 0.25)",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Page header with icon */}
      <div className="no-print" style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <div style={iconStyle}>
          {isCompareView ? (
            <Columns2 size={24} color="#fff" />
          ) : (
            <BookOpen size={24} color="#fff" />
          )}
        </div>
        <div>
          <Typography.Title level={3} style={{ margin: 0 }}>
            {isCompareView ? "Bilingual Evidence" : "Literature Detail"}
          </Typography.Title>
          <Typography.Text type="secondary" style={{ fontSize: 14 }}>
            {isCompareView
              ? "Read original and English full-text evidence side by side with category highlight controls."
              : "Review literature metadata, evidence distribution, and extracted fields."}
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
