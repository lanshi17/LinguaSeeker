import { useState, useMemo } from "react";
import { ShieldCheck, CircleHelp } from "lucide-react";
import { Typography } from "antd";
import { AuditView } from "@/features/audit";
import { useI18n } from "@/lib/i18n";
import { PageGuide, type GuideSection } from "@/components/ui/PageGuide";

export function AuditPage() {
  const { t } = useI18n();
  const [guideOpen, setGuideOpen] = useState(false);

  const guideSections: GuideSection[] = useMemo(() => [
    { title: t("pageGuide.audit.s1.title"), items: [
      t("pageGuide.audit.s1.i1"), t("pageGuide.audit.s1.i2"),
      t("pageGuide.audit.s1.i3"),
    ]},
    { title: t("pageGuide.audit.s2.title"), items: [
      t("pageGuide.audit.s2.i1"), t("pageGuide.audit.s2.i2"),
      t("pageGuide.audit.s2.i3"), t("pageGuide.audit.s2.i4"),
    ]},
  ], [t]);
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
            {t("audit.title")}
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
            {t("audit.description")}
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

      <AuditView />

      <PageGuide
        open={guideOpen}
        onClose={() => setGuideOpen(false)}
        title={t("pageGuide.audit.title")}
        sections={guideSections}
      />
    </div>
  );
}
