import { CATEGORY_COLORS } from "@/features/evidence-search/utils/evidenceDocument";
import type { EvidenceGroupItem } from "@/features/evidence-search/types/evidenceSearch";
import { categoryLabel } from "@/features/evidence-search/utils/categoryStyles";

/* ── Category Toggle ────────────────────────────────────── */

export function CategoryToggle({
  category,
  count,
  checked,
  onChange,
}: {
  category: string;
  count: number;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  const hex = CATEGORY_COLORS[category]?.hex ?? "#64748B";

  return (
    <label
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        borderRadius: 8,
        border: checked ? "1px solid var(--color-border)" : "1px solid transparent",
        backgroundColor: checked ? "var(--color-surface)" : "var(--color-bg)",
        opacity: checked ? 1 : 0.5,
        padding: "6px 10px",
        fontSize: 12,
        fontWeight: 500,
        cursor: "pointer",
        transition: "all 0.15s",
      }}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
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
      <div
        style={{
          display: "flex",
          width: 16,
          height: 16,
          flexShrink: 0,
          alignItems: "center",
          justifyContent: "center",
          borderRadius: 4,
          border: checked ? "1px solid transparent" : "1px solid var(--color-text-muted)",
          backgroundColor: checked ? hex : "var(--color-surface)",
          color: checked ? "var(--color-text-strong)" : undefined,
          transition: "background-color 0.15s",
        }}
      >
        {checked && (
          <svg style={{ width: 12, height: 12 }} viewBox="0 0 12 12" fill="none">
            <path
              d="M2 6l3 3 5-5"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </div>
      <span style={{ color: "var(--color-text-strong)" }}>
        <span style={{ fontFamily: "var(--font-mono)" }}>{category}</span>: {categoryLabel(category)}
      </span>
      <span style={{ marginLeft: "auto", fontFamily: "var(--font-mono)", color: "var(--color-text-secondary)" }}>{count}</span>
    </label>
  );
}

/* ── Evidence Navigator ─────────────────────────────────── */

export function EvidenceNavigator({
  items,
  selectedId,
  onSelect,
}: {
  items: EvidenceGroupItem[];
  selectedId?: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      {items.map((item) => {
        const cat =
          item.category ??
          (item.field_id.includes(".") ? item.field_id.split(".")[0] : null);
        const hex = cat ? CATEGORY_COLORS[cat]?.hex ?? "#64748B" : "#64748B";
        const isSelected = item.canonical_evidence_id === selectedId;
        const confidence = item.confidence ?? 0;
        const confColor = confidence >= 0.7 ? "#059669" : confidence >= 0.4 ? "#D97706" : "#EF4444";

        return (
          <button
            key={item.canonical_evidence_id}
            type="button"
            onClick={() => onSelect(item.canonical_evidence_id)}
            className={isSelected ? "bev-nav-item bev-nav-item--selected" : "bev-nav-item"}
            style={{
              display: "flex",
              width: "100%",
              alignItems: "center",
              gap: 8,
              borderRadius: 8,
              padding: "8px 10px",
              textAlign: "left",
              fontSize: 12,
              transition: "all 0.15s",
              cursor: "pointer",
              border: isSelected ? undefined : "1px solid transparent",
              backgroundColor: isSelected ? undefined : undefined,
            }}
          >
            <div
              style={{
                width: 8,
                height: 8,
                flexShrink: 0,
                borderRadius: "50%",
                backgroundColor: hex,
              }}
            />
            <span style={{
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              flex: 1,
              color: "var(--color-text-strong)",
              fontWeight: 500,
            }}>
              {item.field_name ?? item.field_id}
            </span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: confColor }}>
              {Math.round(confidence * 100)}%
            </span>
          </button>
        );
      })}
    </div>
  );
}
