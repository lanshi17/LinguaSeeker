import { Search, X, Dna, FlaskConical, Stethoscope, Hash } from "lucide-react";
import { Button, Input } from "antd";
import type { EvidenceSearchQuery } from "../types/evidenceSearch";
import { useI18n } from "@/lib/i18n";

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
  const { t } = useI18n();

  return (
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {/* Header */}
        <div
          style={{
            borderRadius: 6,
            border: "1px solid var(--color-border)",
            padding: "14px 18px",
          }}
        >
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
              <div
                style={{
                  display: "flex",
                  height: 36,
                  width: 36,
                  flexShrink: 0,
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: 6,
                  border: "1px solid var(--color-border)",
                  color: "var(--color-primary-600)",
                }}
              >
                <Search style={{ width: 16, height: 16 }} />
              </div>
              <div>
                <h2 style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--color-text-secondary)", margin: 0 }}>
                  {t("evidence.search.heading")}
                </h2>
                <p style={{ marginTop: 4, fontSize: 13, color: "var(--color-text-strong)" }}>
                  {t("evidence.search.description")}
                </p>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Button htmlType="submit" loading={isSearching}>
                <Search style={{ width: 16, height: 16, marginRight: 8 }} />
                {t("evidence.search.btn")}
              </Button>
              <Button type="text" onClick={onClear}>
                <X style={{ width: 16, height: 16, marginRight: 8 }} />
                {t("evidence.search.clear")}
              </Button>
            </div>
          </div>
        </div>

        {/* Input fields with icons */}
        <div className="edb-search-grid">
          <div>
            <label style={{ display: "block", marginBottom: 6, fontSize: 14, fontWeight: 500, color: "var(--color-text)" }}>{t("evidence.search.gene")}</label>
            <Input
              prefix={<Dna style={{ width: 16, height: 16, color: "var(--color-text-muted)" }} />}
              placeholder={t("evidence.search.genePh")}
              value={filters.gene ?? ""}
              onChange={(e) => onUpdateFilter("gene", e.target.value)}
            />
          </div>
          <div>
            <label style={{ display: "block", marginBottom: 6, fontSize: 14, fontWeight: 500, color: "var(--color-text)" }}>{t("evidence.search.variant")}</label>
            <Input
              prefix={<FlaskConical style={{ width: 16, height: 16, color: "var(--color-text-muted)" }} />}
              placeholder={t("evidence.search.variantPh")}
              value={filters.variant ?? ""}
              onChange={(e) => onUpdateFilter("variant", e.target.value)}
            />
          </div>
          <div>
            <label style={{ display: "block", marginBottom: 6, fontSize: 14, fontWeight: 500, color: "var(--color-text)" }}>{t("evidence.search.disease")}</label>
            <Input
              prefix={<Stethoscope style={{ width: 16, height: 16, color: "var(--color-text-muted)" }} />}
              placeholder={t("evidence.search.diseasePh")}
              value={filters.disease ?? ""}
              onChange={(e) => onUpdateFilter("disease", e.target.value)}
            />
          </div>
          <div>
            <label style={{ display: "block", marginBottom: 6, fontSize: 14, fontWeight: 500, color: "var(--color-text)" }}>{t("evidence.search.pmid")}</label>
            <Input
              prefix={<Hash style={{ width: 16, height: 16, color: "var(--color-text-muted)" }} />}
              placeholder={t("evidence.search.pmidPh")}
              value={filters.pmid ?? ""}
              onChange={(e) => onUpdateFilter("pmid", e.target.value)}
            />
          </div>
        </div>
      </form>
  );
}
