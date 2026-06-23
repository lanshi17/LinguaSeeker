import { ShieldCheck } from "lucide-react";
import { Typography } from "antd";
import { AuditView } from "@/features/audit";

export function AuditPage() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Custom header with gradient icon box — matches EvidencePage pattern */}
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 10,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "linear-gradient(135deg, var(--color-primary-500), var(--color-primary-700))",
            boxShadow: "0 2px 8px rgba(8, 145, 178, 0.25)",
          }}
        >
          <ShieldCheck style={{ width: 22, height: 22, color: "#fff" }} />
        </div>
        <div>
          <Typography.Title level={3} style={{ margin: 0 }}>
            Audit Trail
          </Typography.Title>
          <Typography.Text type="secondary" style={{ fontSize: 14 }}>
            Review all evidence corrections, status changes, and field-level edits.
          </Typography.Text>
        </div>
      </div>

      <AuditView />
    </div>
  );
}
