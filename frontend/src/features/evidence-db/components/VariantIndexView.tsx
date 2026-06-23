import { useMemo } from "react";
import { Link } from "react-router-dom";
import {
  Dna,
  FileText,
  BookOpen,
  TrendingUp,
  Search,
  X,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  Calendar,
} from "lucide-react";
import { AutoComplete, Input } from "antd";
import { Spinner } from "@/components/ui/Spinner";
import { useVariantIndex } from "../hooks/useVariantIndex";
import { VariantIndexSkeleton } from "./VariantIndexSkeleton";
import type {
  VariantIndexEntry,
  ClassificationLevel,
} from "../types/variantDb";
import {
  classificationColor,
  classificationShortLabel,
} from "../utils/pathogenicity";
import { CATEGORY_COLORS } from "@/features/evidence-search/utils/evidenceDocument";

const CLASSIFICATION_OPTIONS: { value: ClassificationLevel; label: string }[] = [
  { value: "pathogenic", label: "Pathogenic" },
  { value: "likely_pathogenic", label: "Likely Pathogenic" },
  { value: "uncertain", label: "VUS" },
  { value: "likely_benign", label: "Likely Benign" },
  { value: "benign", label: "Benign" },
];

/* ── Badge style helper (replaces classificationBadgeClasses Tailwind output) ── */

function badgeInlineStyle(level: ClassificationLevel): React.CSSProperties {
  const color = classificationColor(level);
  return {
    display: "inline-flex",
    alignItems: "center",
    borderRadius: 6,
    border: `1px solid ${color}40`,
    padding: "2px 8px",
    fontSize: 12,
    fontWeight: 500,
    fontFamily: "var(--font-mono)",
    backgroundColor: `${color}18`,
    color: color,
  };
}

/* ── Date formatter ─────────────────────────────────────── */

function formatDate(isoString?: string | null): string {
  if (!isoString) return "—";
  try {
    return new Date(isoString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return "—";
  }
}

/* ── Embedded responsive styles ──────────────────────────── */

const embeddedCSS = `
.viv-stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
@media (min-width: 640px) {
  .viv-stats-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}
.viv-search-bar {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
@media (min-width: 640px) {
  .viv-search-bar {
    flex-direction: row;
    align-items: center;
  }
  .viv-disease-filter {
    width: 192px;
  }
}
.viv-variant-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: 1fr;
  align-items: stretch;
  grid-auto-rows: 1fr;
}
@media (min-width: 640px) {
  .viv-variant-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (min-width: 1024px) {
  .viv-variant-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
.viv-card:hover .viv-gene {
  color: var(--color-primary-600);
}
.viv-filter-pill:hover {
  border-color: #d1d5db;
}
.viv-clear-btn:hover {
  background-color: #f9fafb;
}
.viv-page-btn:hover {
  background-color: #f9fafb;
}
`;

/* ── Stat Card ──────────────────────────────────────────── */

function StatCard({
  icon: Icon,
  value,
  label,
  accent,
}: {
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
  value: string | number;
  label: string;
  accent?: string;
}) {
  const accentColor = accent ?? "#0891B2";
  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: 12,
      borderRadius: 8,
      border: "1px solid #f3f4f6",
      backgroundColor: "rgba(249,250,251,0.6)",
      padding: "12px 16px",
    }}>
      <div
        style={{
          display: "flex",
          width: 36,
          height: 36,
          flexShrink: 0,
          alignItems: "center",
          justifyContent: "center",
          borderRadius: 8,
          backgroundColor: `${accentColor}1a`,
        }}
      >
        <Icon style={{ width: 16, height: 16, color: accentColor }} />
      </div>
      <div>
        <p
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 18,
            fontWeight: 600,
            lineHeight: 1.25,
            color: accentColor,
            margin: 0,
          }}
        >
          {typeof value === "number" ? value.toLocaleString() : value}
        </p>
        <p style={{ fontSize: 12, color: "#6b7280", margin: 0 }}>{label}</p>
      </div>
    </div>
  );
}

/* ── Category Strip ─────────────────────────────────────── */

function CategoryDistributionBar({
  distribution,
}: {
  distribution: Record<string, number>;
}) {
  const entries = Object.entries(distribution)
    .filter(([, count]) => count > 0)
    .sort(([, a], [, b]) => b - a);

  if (entries.length === 0) return null;

  const total = entries.reduce((sum, [, c]) => sum + c, 0);

  return (
    <div className="edb-cat-strip" style={{ display: "flex", width: "100%" }}>
      {entries.map(([cat, count]) => (
        <span
          key={cat}
          style={{
            backgroundColor: CATEGORY_COLORS[cat]?.hex ?? "#64748B",
            flexGrow: count / total,
          }}
          title={`Category ${cat}: ${count} fields`}
        />
      ))}
    </div>
  );
}

/* ── Variant Card ───────────────────────────────────────── */

function VariantCard({ entry }: { entry: VariantIndexEntry }) {
  const borderColor = classificationColor(entry.classificationLevel);

  return (
    <Link
      to={`/evidence-db/${encodeURIComponent(entry.variantSlug)}`}
      className="edb-card edb-card-clickable viv-card"
      style={{
        display: "block",
        borderRadius: 12,
        overflow: "hidden",
        cursor: "pointer",
        textDecoration: "none",
        color: "inherit",
      }}
    >
      {/* Pathogenicity accent bar */}
      <div
        style={{ height: 2, width: "100%", backgroundColor: borderColor }}
      />

      <div style={{ padding: 16 }}>
        {/* Gene + Variant header */}
        <div style={{ marginBottom: 8 }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
            <div style={{ minWidth: 0 }}>
              <h3 className="viv-gene" style={{
                fontFamily: "var(--font-mono)",
                fontSize: 16,
                fontWeight: 600,
                color: "#111827",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                transition: "color 0.15s",
                margin: 0,
              }}>
                {entry.gene || "Unknown Gene"}
              </h3>
              <p style={{
                fontFamily: "var(--font-mono)",
                fontSize: 14,
                color: "#6b7280",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                marginTop: 2,
                margin: 0,
              }}>
                {entry.variant || "Unknown Variant"}
              </p>
            </div>
            <span
              style={{
                ...badgeInlineStyle(entry.classificationLevel),
                flexShrink: 0,
              }}
            >
              {classificationShortLabel(entry.classificationLevel)}
            </span>
          </div>
        </div>

        {/* Disease + Classification */}
        <div style={{ marginBottom: 12, display: "flex", flexDirection: "column", gap: 2 }}>
          {entry.disease && (
            <p style={{
              fontSize: 14,
              color: "#374151",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              margin: 0,
            }}>
              {entry.disease}
            </p>
          )}
          <p style={{ fontSize: 12, color: "#6b7280", margin: 0 }}>
            {entry.classification || "No classification"}
          </p>
        </div>

        {/* Stats row */}
        <div style={{
          marginBottom: 12,
          display: "flex",
          alignItems: "center",
          gap: 16,
          fontSize: 12,
          color: "#6b7280",
        }}>
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <FileText style={{ width: 14, height: 14 }} />
            <span style={{ fontWeight: 500, color: "#374151" }}>
              {entry.evidenceGroupCount}
            </span>
            evidence
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <BookOpen style={{ width: 14, height: 14 }} />
            <span style={{ fontWeight: 500, color: "#374151" }}>
              {entry.literatureCount}
            </span>
            refs
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <TrendingUp style={{ width: 14, height: 14 }} />
            <span style={{ fontWeight: 500, color: "#374151" }}>
              {Math.round(entry.avgConfidence * 100)}%
            </span>
            conf.
          </span>
        </div>

        {/* Category distribution mini-bar */}
        <CategoryDistributionBar distribution={entry.categoryDistribution} />

        {/* Updated date */}
        <div style={{
          marginTop: 8,
          display: "flex",
          alignItems: "center",
          gap: 4,
          fontSize: 11,
          color: "#9ca3af",
        }}>
          <Calendar style={{ width: 12, height: 12 }} />
          <span>Updated {formatDate(entry.createdAt)}</span>
        </div>
      </div>
    </Link>
  );
}

/* ── Classification Filter Pills ────────────────────────── */

function ClassificationFilter({
  value,
  onChange,
}: {
  value?: ClassificationLevel;
  onChange: (val?: ClassificationLevel) => void;
}) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6 }}>
      <button
        type="button"
        onClick={() => onChange(undefined)}
        className="viv-filter-pill"
        style={{
          cursor: "pointer",
          borderRadius: 9999,
          border: !value ? "1px solid #111827" : "1px solid #e5e7eb",
          backgroundColor: !value ? "#111827" : "#fff",
          color: !value ? "#fff" : "#4b5563",
          padding: "4px 10px",
          fontSize: 12,
          fontWeight: 500,
          transition: "all 0.15s",
        }}
      >
        All
      </button>
      {CLASSIFICATION_OPTIONS.map((opt) => {
        const hex = classificationColor(opt.value);
        const isActive = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() =>
              onChange(value === opt.value ? undefined : opt.value)
            }
            className="viv-filter-pill"
            style={{
              cursor: "pointer",
              borderRadius: 9999,
              border: isActive ? "1px solid transparent" : "1px solid #e5e7eb",
              backgroundColor: isActive ? hex : "#fff",
              color: isActive ? "#fff" : "#4b5563",
              padding: "4px 10px",
              fontSize: 12,
              fontWeight: 500,
              transition: "all 0.15s",
            }}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

/* ── Main View ──────────────────────────────────────────── */

export function VariantIndexView() {
  const {
    items,
    total,
    page,
    pageSize,
    stats,
    allEntries,
    isLoading,
    isFetching,
    error,
    filters,
    updateFilter,
    setPage,
    clearFilters,
  } = useVariantIndex();

  const totalPages = Math.ceil(total / pageSize);

  const searchText = filters.gene ?? filters.variant ?? "";
  const hasAnyFilter = !!(filters.gene || filters.variant || filters.disease || filters.classification);

  // Build candidate lists from all data for autocomplete
  const { geneCandidates, variantCandidates, diseaseCandidates } = useMemo(() => {
    const genes = new Set<string>();
    const variants = new Set<string>();
    const diseases = new Set<string>();
    for (const e of allEntries) {
      if (e.gene) genes.add(e.gene);
      if (e.variant) variants.add(e.variant);
      if (e.disease) diseases.add(e.disease);
    }
    const toOptions = (set: Set<string>, filterText: string) => {
      const q = filterText.toLowerCase();
      return [...set]
        .filter((v) => v.toLowerCase().includes(q))
        .sort()
        .slice(0, 20)
        .map((v) => ({ value: v, label: v }));
    };
    return {
      geneCandidates: toOptions(genes, searchText),
      variantCandidates: toOptions(variants, searchText),
      diseaseCandidates: toOptions(diseases, filters.disease ?? ""),
    };
  }, [allEntries, searchText, filters.disease]);

  // Merge gene + variant candidates for the unified search field
  const searchCandidates = useMemo(() => {
    const seen = new Set<string>();
    const merged: { value: string; label: string }[] = [];
    for (const opt of [...geneCandidates, ...variantCandidates]) {
      if (!seen.has(opt.value)) {
        seen.add(opt.value);
        merged.push(opt);
      }
    }
    return merged;
  }, [geneCandidates, variantCandidates]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <style>{embeddedCSS}</style>

      {/* Hero Stats Section */}
      <section className="edb-hero" style={{ borderRadius: 16, border: "1px solid #e5e7eb", padding: 24 }}>
        <div className="viv-stats-grid">
          <StatCard
            icon={Dna}
            value={stats.totalVariants}
            label="Unique Variants"
            accent="#8B5CF6"
          />
          <StatCard
            icon={FileText}
            value={stats.totalEvidenceGroups}
            label="Evidence Groups"
            accent="#0891B2"
          />
          <StatCard
            icon={BookOpen}
            value={stats.totalLiterature}
            label="Literature Sources"
            accent="#F59E0B"
          />
          <StatCard
            icon={TrendingUp}
            value={`${Math.round(stats.avgConfidence * 100)}%`}
            label="Avg Confidence"
            accent="#0F766E"
          />
        </div>
      </section>

      {/* Search & Filter Bar */}
      <section style={{ borderRadius: 12, border: "1px solid #e5e7eb", backgroundColor: "#fff", padding: 16 }}>
        <div className="viv-search-bar">
          {/* Text search — gene or variant autocomplete */}
          <div style={{ flex: 1 }}>
            <AutoComplete
              style={{ width: "100%" }}
              options={searchCandidates}
              value={searchText}
              onChange={(val) => {
                updateFilter("gene", val || undefined);
                if (val) updateFilter("variant", undefined);
              }}
              popupMatchSelectWidth={true}
            >
              <Input
                placeholder="Search by gene or variant..."
                prefix={<Search style={{ width: 16, height: 16, color: "#9ca3af" }} />}
                suffix={
                  searchText ? (
                    <button
                      type="button"
                      onClick={() => {
                        updateFilter("gene", undefined);
                        updateFilter("variant", undefined);
                      }}
                      style={{
                        cursor: "pointer",
                        border: "none",
                        background: "none",
                        padding: 2,
                        color: "#9ca3af",
                        display: "flex",
                        alignItems: "center",
                      }}
                    >
                      <X style={{ width: 14, height: 14 }} />
                    </button>
                  ) : undefined
                }
                allowClear={false}
              />
            </AutoComplete>
          </div>

          {/* Disease filter — autocomplete */}
          <div className="viv-disease-filter">
            <AutoComplete
              style={{ width: "100%" }}
              options={diseaseCandidates}
              value={filters.disease ?? ""}
              onChange={(val) =>
                updateFilter("disease", val || undefined)
              }
              popupMatchSelectWidth={true}
            >
              <Input placeholder="Filter by disease..." />
            </AutoComplete>
          </div>

          {/* Clear all */}
          {hasAnyFilter && (
            <button
              type="button"
              onClick={clearFilters}
              className="viv-clear-btn"
              style={{
                cursor: "pointer",
                flexShrink: 0,
                borderRadius: 8,
                border: "1px solid #e5e7eb",
                padding: "4px 12px",
                fontSize: 12,
                fontWeight: 500,
                color: "#4b5563",
                backgroundColor: "#fff",
                transition: "background-color 0.15s",
              }}
            >
              Clear all
            </button>
          )}
        </div>

        {/* Classification filter pills */}
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #f3f4f6" }}>
          <ClassificationFilter
            value={filters.classification}
            onChange={(val) => updateFilter("classification", val)}
          />
        </div>
      </section>

      {/* Results */}
      {error ? (
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          borderRadius: 12,
          border: "1px solid #fecaca",
          backgroundColor: "#fef2f2",
          padding: 16,
          fontSize: 14,
          color: "#b91c1c",
        }}>
          <AlertCircle style={{ width: 20, height: 20, flexShrink: 0 }} />
          <span>Failed to load variant data. Please try again.</span>
        </div>
      ) : isLoading ? (
        <VariantIndexSkeleton />
      ) : items.length === 0 ? (
        <div style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: 12,
          border: "1px dashed #d1d5db",
          padding: "80px 0",
          textAlign: "center",
        }}>
          <Dna style={{ width: 40, height: 40, color: "#d1d5db", marginBottom: 12 }} />
          <p style={{ fontSize: 14, fontWeight: 500, color: "#374151", margin: 0 }}>
            No variants found
          </p>
          <p style={{ fontSize: 12, color: "#6b7280", marginTop: 4, margin: 0 }}>
            Try adjusting your search filters
          </p>
        </div>
      ) : (
        <div className="content-fade-in">
          {/* Result count */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <p style={{ fontSize: 14, color: "#4b5563", margin: 0 }}>
              <span style={{ fontWeight: 500, color: "#111827" }}>{total}</span>{" "}
              variant{total !== 1 ? "s" : ""} found
              {isFetching && (
                <span style={{ marginLeft: 8, display: "inline-block" }}>
                  <Spinner size="sm" />
                </span>
              )}
            </p>
            <p style={{ fontSize: 12, color: "#6b7280", margin: 0 }}>
              Page {page} of {totalPages || 1}
            </p>
          </div>

          {/* Variant Grid */}
          <div className="viv-variant-grid" style={{ marginTop: 16 }}>
            {items.map((entry, i) => (
              <div
                key={entry.variantSlug}
                className="edb-stagger"
                style={{ animationDelay: `${Math.min(i * 35, 350)}ms` }}
              >
                <VariantCard entry={entry} />
              </div>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              paddingTop: 8,
            }}>
              <button
                type="button"
                onClick={() => setPage(page - 1)}
                disabled={page <= 1}
                className={page > 1 ? "viv-page-btn" : undefined}
                style={{
                  display: "flex",
                  width: 36,
                  height: 36,
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: 8,
                  border: page <= 1 ? "1px solid #f3f4f6" : "1px solid #e5e7eb",
                  fontSize: 14,
                  color: page <= 1 ? "#d1d5db" : "#4b5563",
                  cursor: page <= 1 ? "not-allowed" : "pointer",
                  backgroundColor: "#fff",
                  transition: "background-color 0.15s",
                }}
              >
                <ChevronLeft style={{ width: 16, height: 16 }} />
              </button>
              {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                const pageNum = i + 1;
                const isActive = pageNum === page;
                return (
                  <button
                    key={pageNum}
                    type="button"
                    onClick={() => setPage(pageNum)}
                    className={!isActive ? "viv-page-btn" : undefined}
                    style={{
                      display: "flex",
                      width: 36,
                      height: 36,
                      alignItems: "center",
                      justifyContent: "center",
                      borderRadius: 8,
                      border: isActive ? "1px solid var(--color-primary-600)" : "1px solid #e5e7eb",
                      fontSize: 14,
                      fontWeight: 500,
                      backgroundColor: isActive ? "var(--color-primary-600)" : "#fff",
                      color: isActive ? "#fff" : "#4b5563",
                      cursor: "pointer",
                      transition: "background-color 0.15s",
                    }}
                  >
                    {pageNum}
                  </button>
                );
              })}
              {totalPages > 7 && (
                <span style={{ padding: "0 4px", color: "#9ca3af" }}>&hellip;</span>
              )}
              <button
                type="button"
                onClick={() => setPage(page + 1)}
                disabled={page >= totalPages}
                className={page < totalPages ? "viv-page-btn" : undefined}
                style={{
                  display: "flex",
                  width: 36,
                  height: 36,
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: 8,
                  border: page >= totalPages ? "1px solid #f3f4f6" : "1px solid #e5e7eb",
                  fontSize: 14,
                  color: page >= totalPages ? "#d1d5db" : "#4b5563",
                  cursor: page >= totalPages ? "not-allowed" : "pointer",
                  backgroundColor: "#fff",
                  transition: "background-color 0.15s",
                }}
              >
                <ChevronRight style={{ width: 16, height: 16 }} />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
