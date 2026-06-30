import { Eye, EyeOff } from "lucide-react";
import { EVIDENCE_CATEGORIES } from "@/features/evidence-search/utils/evidenceDocument";
import type {
  EvidenceGroupItem,
  ReviewStatusValue,
} from "@/features/evidence-search/types/evidenceSearch";
import { CategoryToggle, EvidenceNavigator } from "./SidebarControls";
import { useI18n } from "@/lib/i18n";

const STATUS_TONES: Record<ReviewStatusValue, { bg: string; color: string; border: string }> = {
  provisional: { bg: "var(--color-bg)", color: "var(--color-text-strong)", border: "var(--color-border)" },
  approved: { bg: "var(--color-highlight-green)", color: "var(--color-success-700)", border: "var(--color-success-200)" },
  corrected: { bg: "var(--color-highlight-amber)", color: "var(--color-warning-text)", border: "var(--color-highlight-amber-border)" },
  rejected: { bg: "var(--color-error-bg)", color: "var(--color-error-text)", border: "var(--color-error-border)" },
};

/* ── Bilingual Evidence Sidebar ─────────────────────────── */

export function BilingualSidebar({
  categoryCounts,
  enabledCategories,
  toggleCategory,
  toggleAllCategories,
  statusCounts,
  enabledStatuses,
  toggleStatus,
  toggleAllStatuses,
  items,
  selectedEvidenceId,
  onSelectEvidence,
}: {
  categoryCounts: Record<string, number>;
  enabledCategories: Set<string>;
  toggleCategory: (cat: string) => void;
  toggleAllCategories: (on: boolean) => void;
  statusCounts: Record<string, number>;
  enabledStatuses: Set<string>;
  toggleStatus: (status: string) => void;
  toggleAllStatuses: (on: boolean) => void;
  items: EvidenceGroupItem[];
  selectedEvidenceId?: string;
  onSelectEvidence: (id: string) => void;
}) {
  const { t } = useI18n();

  const reviewStatusOptions: Array<{ value: ReviewStatusValue; label: string }> = [
    { value: "provisional", label: t("evidenceDb.sidebar.statusProvisional") },
    { value: "approved", label: t("evidenceDb.sidebar.statusApproved") },
    { value: "corrected", label: t("evidenceDb.sidebar.statusCorrected") },
    { value: "rejected", label: t("evidenceDb.sidebar.statusRejected") },
  ];

  return (
    <aside style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Category toggles */}
      <div className="edb-card" style={{ borderRadius: 12, padding: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <h3 style={{
            fontSize: 12,
            fontWeight: 600,
            color: "var(--color-text-secondary)",
            textTransform: "uppercase",
            letterSpacing: 0,
            margin: 0,
          }}>
            {t("evidenceDb.sidebar.layers")}
          </h3>
          <div style={{ display: "flex", gap: 4 }}>
            <button
              type="button"
              onClick={() => toggleAllCategories(true)}
              className="bev-eye-btn"
              style={{
                cursor: "pointer",
                borderRadius: 4,
                padding: "2px 6px",
                fontSize: 10,
                color: "var(--color-text-muted)",
                border: "none",
                backgroundColor: "transparent",
                display: "flex",
                alignItems: "center",
              }}
              title={t("evidenceDb.sidebar.showAll")}
              aria-label={t("evidenceDb.sidebar.showAll")}
            >
              <Eye style={{ width: 14, height: 14 }} />
            </button>
            <button
              type="button"
              onClick={() => toggleAllCategories(false)}
              className="bev-eye-btn"
              style={{
                cursor: "pointer",
                borderRadius: 4,
                padding: "2px 6px",
                fontSize: 10,
                color: "var(--color-text-muted)",
                border: "none",
                backgroundColor: "transparent",
                display: "flex",
                alignItems: "center",
              }}
              title={t("evidenceDb.sidebar.hideAll")}
              aria-label={t("evidenceDb.sidebar.hideAll")}
            >
              <EyeOff style={{ width: 14, height: 14 }} />
            </button>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {EVIDENCE_CATEGORIES.map((cat) => (
            <CategoryToggle
              key={cat}
              category={cat}
              count={categoryCounts[cat] ?? 0}
              checked={enabledCategories.has(cat)}
              onChange={() => toggleCategory(cat)}
            />
          ))}
        </div>
      </div>

      {/* Review status toggles */}
      <div className="edb-card" style={{ borderRadius: 12, padding: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <h3 style={{
            fontSize: 12,
            fontWeight: 600,
            color: "var(--color-text-secondary)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            margin: 0,
          }}>
            {t("evidenceDb.sidebar.reviewStatus")}
          </h3>
          <div style={{ display: "flex", gap: 4 }}>
            <button
              type="button"
              onClick={() => toggleAllStatuses(true)}
              className="bev-eye-btn"
              style={{
                cursor: "pointer",
                borderRadius: 4,
                padding: "2px 6px",
                fontSize: 10,
                color: "var(--color-text-muted)",
                border: "none",
                backgroundColor: "transparent",
                display: "flex",
                alignItems: "center",
              }}
              title={t("evidenceDb.sidebar.showAll")}
              aria-label={t("evidenceDb.sidebar.showAll")}
            >
              <Eye style={{ width: 14, height: 14 }} />
            </button>
            <button
              type="button"
              onClick={() => toggleAllStatuses(false)}
              className="bev-eye-btn"
              style={{
                cursor: "pointer",
                borderRadius: 4,
                padding: "2px 6px",
                fontSize: 10,
                color: "var(--color-text-muted)",
                border: "none",
                backgroundColor: "transparent",
                display: "flex",
                alignItems: "center",
              }}
              title={t("evidenceDb.sidebar.hideAll")}
              aria-label={t("evidenceDb.sidebar.hideAll")}
            >
              <EyeOff style={{ width: 14, height: 14 }} />
            </button>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {reviewStatusOptions.map(({ value, label }) => {
            const checked = enabledStatuses.has(value);
            const tone = STATUS_TONES[value];
            return (
              <label
                key={value}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  borderRadius: 8,
                  border: checked ? `1px solid ${tone.border}` : "1px solid transparent",
                  backgroundColor: checked ? tone.bg : "var(--color-bg)",
                  opacity: checked ? 1 : 0.5,
                  padding: "6px 10px",
                  fontSize: 12,
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggleStatus(value)}
                  style={{
                    position: "absolute",
                    width: 1,
                    height: 1,
                    padding: 0,
                    margin: -1,
                    overflow: "hidden",
                    clip: "rect(0,0,0,0)",
                    whiteSpace: "nowrap",
                    borderWidth: 0,
                  }}
                />
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    backgroundColor: tone.color,
                  }}
                />
                <span style={{ color: "var(--color-text-strong)" }}>{label}</span>
                <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", color: "var(--color-text-secondary)" }}>
                  {statusCounts[value] ?? 0}
                </span>
              </label>
            );
          })}
        </div>
      </div>

      {/* Evidence navigator */}
      <div className="edb-card" style={{ borderRadius: 12, padding: 16 }}>
        <h3 style={{
          fontSize: 12,
          fontWeight: 600,
          color: "var(--color-text-secondary)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          marginBottom: 12,
          margin: 0,
          paddingBottom: 0,
        }}>
          {t("evidenceDb.sidebar.evidenceFields")}
        </h3>
        <div className="edb-scroll" style={{ maxHeight: 400, overflowY: "auto" }}>
          <EvidenceNavigator
            items={items}
            selectedId={selectedEvidenceId}
            onSelect={onSelectEvidence}
          />
        </div>
      </div>
    </aside>
  );
}
