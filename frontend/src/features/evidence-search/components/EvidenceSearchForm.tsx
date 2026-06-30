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
        {/* Header with accent */}
        <div
          style={{
            position: "relative",
            overflow: "hidden",
            borderRadius: 8,
            background: "linear-gradient(to right, var(--color-primary-50, var(--color-primary-50)), var(--color-primary-50, var(--color-primary-50)) 50%, transparent)",
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
              background: "linear-gradient(to bottom, var(--color-primary-400, var(--color-primary-400)), var(--color-primary-600))",
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
                  backgroundColor: "var(--color-primary-100, var(--color-primary-100))",
                  color: "var(--color-primary-700, var(--color-primary-700))",
                }}
              >
                <Search style={{ width: 20, height: 20 }} />
              </div>
              <div>
                <h2 style={{ fontSize: 16, fontWeight: 600, color: "var(--color-text)", margin: 0 }}>
                  {t("evidence.search.heading")}
                </h2>
                <p style={{ marginTop: 2, fontSize: 14, color: "var(--color-text-strong)" }}>
                  {t("evidence.search.description")}
                </p>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Button htmlType="submit" loading={isSearching} style={{ boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)" }}>
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
