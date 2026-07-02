import { Typography } from "antd";
import { EvidenceSearchView } from "@/features/evidence-search";
import { BookOpen } from "lucide-react";
import { useI18n } from "@/lib/i18n";

export function EvidencePage() {
  const { t } = useI18n();
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Page header */}
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
          <BookOpen size={18} />
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
            {t("evidence.title")}
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
            {t("evidence.description")}
          </Typography.Text>
        </div>
      </div>

      <EvidenceSearchView />
    </div>
  );
}
