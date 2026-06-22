import { Eye, EyeOff } from "lucide-react";
import { EVIDENCE_CATEGORIES } from "@/features/evidence-search/utils/evidenceDocument";
import type { EvidenceGroupItem } from "@/features/evidence-search/types/evidenceSearch";
import { CategoryToggle, EvidenceNavigator } from "./SidebarControls";

/* ── Bilingual Evidence Sidebar ─────────────────────────── */

export function BilingualSidebar({
  categoryCounts,
  enabledCategories,
  toggleCategory,
  toggleAllCategories,
  items,
  selectedEvidenceId,
  onSelectEvidence,
}: {
  categoryCounts: Record<string, number>;
  enabledCategories: Set<string>;
  toggleCategory: (cat: string) => void;
  toggleAllCategories: (on: boolean) => void;
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
            letterSpacing: "0.05em",
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
