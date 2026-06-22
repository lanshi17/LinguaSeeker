import { Search, X, Dna, FlaskConical, Stethoscope, Hash } from "lucide-react";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import type { EvidenceSearchQuery } from "../types/evidenceSearch";

interface EvidenceSearchFormProps {
  filters: EvidenceSearchQuery;
  onUpdateFilter: (key: keyof EvidenceSearchQuery, value: string) => void;
  onSearch: () => void;
  onClear: () => void;
  isSearching?: boolean;
}

export function EvidenceSearchForm({
  filters,
  onUpdateFilter,
  onSearch,
  onClear,
  isSearching,
}: EvidenceSearchFormProps) {
  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSearch();
  }

  return (
    <>
      <style>{`
        .edb-search-grid {
          display: grid;
          gap: 16px;
        }
        @media (min-width: 768px) {
          .edb-search-grid {
            grid-template-columns: repeat(4, minmax(0, 1fr));
          }
        }
        .edb-search-field:focus-within .edb-search-icon {
          color: var(--color-primary-500, #06b6d4);
        }
      `}</style>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {/* Header with accent */}
        <div
          style={{
            position: "relative",
            overflow: "hidden",
            borderRadius: 8,
            background: "linear-gradient(to right, var(--color-primary-50, #ecfeff), var(--color-primary-50, #ecfeff) 50%, transparent)",
            padding: "16px 20px",
          }}
        >
          <div
            style={{
              position: "absolute",
              left: 0,
              top: 0,
              height: "100%",
              width: 4,
              background: "linear-gradient(to bottom, var(--color-primary-400, #22d3ee), var(--color-primary-600, #0891b2))",
            }}
          />
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
              <div
                style={{
                  display: "flex",
                  height: 40,
                  width: 40,
                  flexShrink: 0,
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: 8,
                  backgroundColor: "var(--color-primary-100, #cffafe)",
                  color: "var(--color-primary-700, #0e7490)",
                }}
              >
                <Search style={{ width: 20, height: 20 }} />
              </div>
              <div>
                <h2 style={{ fontSize: 16, fontWeight: 600, color: "#030712", margin: 0 }}>
                  Literature Evidence Search
                </h2>
                <p style={{ marginTop: 2, fontSize: 14, color: "#4b5563" }}>
                  Search by gene, variant, disease, or publication identifier
                </p>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Button type="submit" loading={isSearching} style={{ boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)" }}>
                <Search style={{ width: 16, height: 16, marginRight: 8 }} />
                Search
              </Button>
              <Button type="button" variant="ghost" onClick={onClear}>
                <X style={{ width: 16, height: 16, marginRight: 8 }} />
                Clear
              </Button>
            </div>
          </div>
        </div>

        {/* Input fields with icons */}
        <div className="edb-search-grid">
          <div className="edb-search-field" style={{ position: "relative" }}>
            <div
              className="edb-search-icon"
              style={{
                pointerEvents: "none",
                position: "absolute",
                left: 12,
                top: 38,
                zIndex: 10,
                color: "#9ca3af",
                transition: "color 0.15s",
              }}
            >
              <Dna style={{ width: 16, height: 16 }} />
            </div>
            <Input
              label="Gene"
              placeholder="e.g., BRCA1"
              value={filters.gene ?? ""}
              onChange={(e) => onUpdateFilter("gene", e.target.value)}
              style={{ paddingLeft: 36 }}
            />
          </div>
          <div className="edb-search-field" style={{ position: "relative" }}>
            <div
              className="edb-search-icon"
              style={{
                pointerEvents: "none",
                position: "absolute",
                left: 12,
                top: 38,
                zIndex: 10,
                color: "#9ca3af",
                transition: "color 0.15s",
              }}
            >
              <FlaskConical style={{ width: 16, height: 16 }} />
            </div>
            <Input
              label="Variant"
              placeholder="e.g., c.5266dupC"
              value={filters.variant ?? ""}
              onChange={(e) => onUpdateFilter("variant", e.target.value)}
              style={{ paddingLeft: 36 }}
            />
          </div>
          <div className="edb-search-field" style={{ position: "relative" }}>
            <div
              className="edb-search-icon"
              style={{
                pointerEvents: "none",
                position: "absolute",
                left: 12,
                top: 38,
                zIndex: 10,
                color: "#9ca3af",
                transition: "color 0.15s",
              }}
            >
              <Stethoscope style={{ width: 16, height: 16 }} />
            </div>
            <Input
              label="Disease"
              placeholder="e.g., Breast cancer"
              value={filters.disease ?? ""}
              onChange={(e) => onUpdateFilter("disease", e.target.value)}
              style={{ paddingLeft: 36 }}
            />
          </div>
          <div className="edb-search-field" style={{ position: "relative" }}>
            <div
              className="edb-search-icon"
              style={{
                pointerEvents: "none",
                position: "absolute",
                left: 12,
                top: 38,
                zIndex: 10,
                color: "#9ca3af",
                transition: "color 0.15s",
              }}
            >
              <Hash style={{ width: 16, height: 16 }} />
            </div>
            <Input
              label="PMID"
              placeholder="e.g., 12345678"
              value={filters.pmid ?? ""}
              onChange={(e) => onUpdateFilter("pmid", e.target.value)}
              style={{ paddingLeft: 36 }}
            />
          </div>
        </div>
      </form>
    </>
  );
}
