import { Eye, EyeOff } from "lucide-react";
import { EVIDENCE_CATEGORIES } from "@/features/evidence-search/utils/evidenceDocument";
import type {
  EvidenceGroupItem,
  ReviewStatusValue,
} from "@/features/evidence-search/types/evidenceSearch";
import { CategoryToggle, EvidenceNavigator } from "./SidebarControls";

const REVIEW_STATUS_OPTIONS: Array<{ value: ReviewStatusValue; label: string }> = [
  { value: "provisional", label: "Provisional" },
  { value: "approved", label: "Approved" },
  { value: "corrected", label: "Corrected" },
  { value: "rejected", label: "Rejected" },
];

const STATUS_TONES: Record<ReviewStatusValue, { bg: string; color: string; border: string }> = {
  provisional: { bg: "#f9fafb", color: "#4b5563", border: "#e5e7eb" },
  approved: { bg: "#f0fdf4", color: "#15803d", border: "#bbf7d0" },
  corrected: { bg: "#fffbeb", color: "#b45309", border: "#fde68a" },
  rejected: { bg: "#fef2f2", color: "#b91c1c", border: "#fecaca" },
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
  return (
    <aside style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Category toggles */}
      <div className="edb-card" style={{ borderRadius: 12, padding: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <h3 style={{
            fontSize: 12,
            fontWeight: 600,
            color: "#6b7280",
            textTransform: "uppercase",
            letterSpacing: 0,
            margin: 0,
          }}>
            Evidence Layers
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
                color: "#9ca3af",
                border: "none",
                backgroundColor: "transparent",
                display: "flex",
                alignItems: "center",
              }}
              title="Show all"
              aria-label="Show all categories"
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
                color: "#9ca3af",
                border: "none",
                backgroundColor: "transparent",
                display: "flex",
                alignItems: "center",
              }}
              title="Hide all"
              aria-label="Hide all categories"
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
            color: "#6b7280",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            margin: 0,
          }}>
            Review Status
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
                color: "#9ca3af",
                border: "none",
                backgroundColor: "transparent",
                display: "flex",
                alignItems: "center",
              }}
              title="Show all review statuses"
              aria-label="Show all review statuses"
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
                color: "#9ca3af",
                border: "none",
                backgroundColor: "transparent",
                display: "flex",
                alignItems: "center",
              }}
              title="Hide all review statuses"
              aria-label="Hide all review statuses"
            >
              <EyeOff style={{ width: 14, height: 14 }} />
            </button>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {REVIEW_STATUS_OPTIONS.map(({ value, label }) => {
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
                  backgroundColor: checked ? tone.bg : "#f9fafb",
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
                <span style={{ color: "#374151" }}>{label}</span>
                <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", color: "#6b7280" }}>
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
          color: "#6b7280",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          marginBottom: 12,
          margin: 0,
          paddingBottom: 0,
        }}>
          Evidence Fields
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
