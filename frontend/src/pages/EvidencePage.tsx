import { useState, useMemo } from "react";
import { Typography } from "antd";
import { EvidenceSearchView } from "@/features/evidence-search";
import { BookOpen, CircleHelp } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { PageGuide, type GuideSection } from "@/components/ui/PageGuide";

export function EvidencePage() {
  const { t } = useI18n();
  const [guideOpen, setGuideOpen] = useState(false);

  const guideSections: GuideSection[] = useMemo(() => [
    { title: t("pageGuide.evidence.s1.title"), items: [
      t("pageGuide.evidence.s1.i1"), t("pageGuide.evidence.s1.i2"),
      t("pageGuide.evidence.s1.i3"), t("pageGuide.evidence.s1.i4"),
    ]},
    { title: t("pageGuide.evidence.s2.title"), items: [
      t("pageGuide.evidence.s2.i1"), t("pageGuide.evidence.s2.i2"),
      t("pageGuide.evidence.s2.i3"), t("pageGuide.evidence.s2.i4"),
      t("pageGuide.evidence.s2.i5"), t("pageGuide.evidence.s2.i6"),
      t("pageGuide.evidence.s2.i7"), t("pageGuide.evidence.s2.i8"),
    ]},
  ], [t]);
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
            {t("evidence.title")}
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
            {t("evidence.description")}
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

      <EvidenceSearchView />

      <PageGuide
        open={guideOpen}
        onClose={() => setGuideOpen(false)}
        title={t("pageGuide.evidence.title")}
        sections={guideSections}
      />
    </div>
  );
}
