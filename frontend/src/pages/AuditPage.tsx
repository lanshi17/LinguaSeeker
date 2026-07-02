import { ShieldCheck } from "lucide-react";
import { Typography } from "antd";
import { AuditView } from "@/features/audit";
import { useI18n } from "@/lib/i18n";

export function AuditPage() {
  const { t } = useI18n();
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: 6,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            border: "1px solid var(--color-border)",
            color: "var(--color-primary-600)",
          }}
        >
          <ShieldCheck style={{ width: 18, height: 18 }} />
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
            {t("audit.title")}
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
            {t("audit.description")}
          </Typography.Text>
        </div>
      </div>

      <AuditView />
    </div>
  );
}
