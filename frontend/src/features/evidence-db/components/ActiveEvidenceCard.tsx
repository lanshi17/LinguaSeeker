import { CATEGORY_COLORS } from "@/features/evidence-search/utils/evidenceDocument";
import type { EvidenceGroupItem } from "@/features/evidence-search/types/evidenceSearch";
import { categoryLabel } from "@/features/evidence-search/utils/categoryStyles";
import { useI18n } from "@/lib/i18n";

/* ── Active Evidence Card ───────────────────────────────── */

export function ActiveEvidenceCard({
  item,
  sourceSpanAvailable = false,
}: {
  item: EvidenceGroupItem;
  sourceSpanAvailable?: boolean;
}) {
  const { t } = useI18n();
  const cat =
    item.category ??
    (item.field_id.includes(".") ? item.field_id.split(".")[0] : null);
  const hex = cat ? CATEGORY_COLORS[cat]?.hex ?? "#64748B" : "#64748B";
  const confidence = item.confidence ?? 0;
  const confColor = confidence >= 0.7 ? "#059669" : confidence >= 0.4 ? "#D97706" : "#EF4444";

  return (
    <div
      style={{
        borderRadius: 12,
        border: "1px solid var(--color-border)",
        borderLeftColor: hex,
        borderLeftWidth: 3,
        backgroundColor: "var(--color-surface)",
        overflow: "hidden",
      }}
    >
      <div style={{ padding: 16 }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, marginBottom: 8 }}>
          <div>
            <p style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text)", margin: 0 }}>
              {item.field_name ?? item.field_id}
            </p>
            <p style={{ fontSize: 11, color: "var(--color-text-secondary)", fontFamily: "var(--font-mono)", marginTop: 2, margin: 0 }}>
              {item.field_id}
            </p>
          </div>
          {cat && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                borderRadius: 4,
                border: `1px solid ${hex}40`,
                padding: "2px 6px",
                fontSize: 10,
                fontWeight: 500,
                backgroundColor: `${hex}1a`,
                color: hex,
              }}
            >
              <span style={{ fontFamily: "var(--font-mono)" }}>{cat}</span>: {categoryLabel(cat)}
            </span>
          )}
        </div>

        {item.value && (
          <div style={{ borderRadius: 8, backgroundColor: "var(--color-bg)", padding: 12, marginBottom: 8 }}>
            <p style={{ fontSize: 14, color: "var(--color-text-strong)", lineHeight: 1.625, margin: 0 }}>
              {typeof item.value === "string"
                ? item.value
                : JSON.stringify(item.value, null, 2)}
            </p>
          </div>
        )}

        <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 11, color: "var(--color-text-secondary)" }}>
          <span style={{ fontWeight: 500, color: confColor }}>
            {Math.round(confidence * 100)}% {t("evidenceDb.card.confidence")}
          </span>
          <span>&middot;</span>
          <span style={{ textTransform: "capitalize" }}>
            {item.review_status ?? t("evidenceDb.card.provisional")}
          </span>
          <span>&middot;</span>
          <span style={{ textTransform: "capitalize" }}>{item.track ?? t("evidenceDb.card.original")}</span>
          {item.page && (
            <>
              <span>&middot;</span>
              <span>{t("evidenceDb.card.page", { num: String(item.page) })}</span>
            </>
          )}
          <span>&middot;</span>
          <span>{sourceSpanAvailable ? t("evidenceDb.card.sourceSpan") : t("evidenceDb.card.noSourceSpan")}</span>
        </div>
      </div>
    </div>
  );
}
