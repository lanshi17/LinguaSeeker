import { Typography } from "antd";
import { EvidenceSearchView } from "@/features/evidence-search";
import { BookOpen } from "lucide-react";

export function EvidencePage() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Page header */}
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
            boxShadow: "0 4px 6px -1px rgba(6, 182, 212, 0.25)",
          }}
        >
          <BookOpen size={24} color="#fff" />
        </div>
        <div>
          <Typography.Title level={3} style={{ margin: 0 }}>
            Literature Evidence
          </Typography.Title>
          <Typography.Text type="secondary" style={{ fontSize: 14 }}>
            Search and explore literature-level evidence by gene, variant, disease, or PMID.
          </Typography.Text>
        </div>
      </div>

      <EvidenceSearchView />
    </div>
  );
}
