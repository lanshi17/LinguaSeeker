import { useMemo, useState, useCallback } from "react";
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
  ArrowUp,
  ArrowDown,
} from "lucide-react";
import { AutoComplete, Checkbox, Input } from "antd";
import { Spinner } from "@/components/ui/Spinner";
import { useVariantIndex } from "../hooks/useVariantIndex";
import { useEvidenceDbViewPrefs } from "../hooks/useEvidenceDbViewPrefs";
import { VariantIndexSkeleton } from "./VariantIndexSkeleton";
import type {
  VariantIndexEntry,
  ClassificationLevel,
  SortBy,
  SortOrder,
} from "../types/variantDb";
import type { EvidenceDbViewPrefs } from "../hooks/useEvidenceDbViewPrefs";
import {
  classificationColor,
  classificationShortLabel,
} from "../utils/pathogenicity";
import {
  EVIDENCE_DB_LABELS,
  formatConfidencePercent,
  formatReviewedCount,
} from "../utils/fieldLabels";
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

function hasQualityColumn(prefs: EvidenceDbViewPrefs): boolean {
  return prefs.showCategories || prefs.showReviewProgress;
}

function variantGridTemplateColumns(prefs: EvidenceDbViewPrefs): string {
  const columns = ["2fr", "1.5fr", "120px", "100px", "100px", "100px"];
  if (hasQualityColumn(prefs)) columns.push("120px");
  if (prefs.showUpdated) columns.push("90px");
  return columns.join(" ");
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
.viv-variant-list {
  display: flex;
  flex-direction: column;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
}
.viv-list-header {
  display: none;
}
@media (min-width: 768px) {
  .viv-list-header {
    display: grid;
    grid-template-columns: 2fr 1.5fr 120px 100px 100px 100px 120px 90px;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    background: #f9fafb;
    border-bottom: 1px solid #e5e7eb;
    font-size: 11px;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
}
.viv-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid #f3f4f6;
  cursor: pointer;
  text-decoration: none;
  color: inherit;
  transition: background-color 0.15s;
}
.viv-row:last-child {
  border-bottom: none;
}
.viv-row:hover {
  background-color: #f9fafb;
}
@media (min-width: 768px) {
  .viv-row {
    display: grid;
    grid-template-columns: 2fr 1.5fr 120px 100px 100px 100px 120px 90px;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
  }
}
.viv-row-gene {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 600;
  color: #111827;
  white-space: nowrap;
  flex-shrink: 0;
  transition: color 0.15s;
}
.viv-row:hover .viv-row-gene {
  color: var(--color-primary-600);
}
.viv-row-variant {
  font-family: var(--font-mono);
  font-size: 13px;
  color: #6b7280;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  flex: 1;
}
.viv-row-disease {
  font-size: 13px;
  color: #374151;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.viv-row-stat {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #6b7280;
  white-space: nowrap;
}
.viv-row-stat-val {
  font-weight: 500;
  color: #374151;
}
.viv-row-mobile-stats {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: #6b7280;
}
@media (min-width: 768px) {
  .viv-row-mobile-stats {
    display: none;
  }
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
.viv-page-jump-input {
  width: 48px;
  height: 36px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  text-align: center;
  font-size: 13px;
  font-family: var(--font-mono);
  color: #374151;
  outline: none;
  transition: border-color 0.15s;
}
.viv-page-jump-input:focus {
  border-color: var(--color-primary-600);
  box-shadow: 0 0 0 2px var(--color-primary-100, rgba(8,145,178,0.15));
}
.viv-page-jump-input::placeholder {
  color: #9ca3af;
}
.viv-sort-header {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  user-select: none;
  transition: color 0.15s;
}
.viv-sort-header:hover {
  color: #374151;
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

/* ── Variant Row ────────────────────────────────────────── */

function VariantRow({
  entry,
  viewPrefs,
}: {
  entry: VariantIndexEntry;
  viewPrefs: EvidenceDbViewPrefs;
}) {
  return (
    <Link
      to={`/evidence-db/${encodeURIComponent(entry.variantSlug)}`}
      state={{ variantEntry: entry }}
      className="viv-row"
      style={{ gridTemplateColumns: variantGridTemplateColumns(viewPrefs) }}
    >
      {/* Gene + Variant (primary column) */}
      <div style={{ minWidth: 0, display: "flex", alignItems: "baseline", flexWrap: "nowrap" }} title={`${entry.gene || "Unknown Gene"} · ${entry.variant || "Unknown Variant"}`}>
        <span className="viv-row-gene">{entry.gene || "Unknown Gene"}</span>
        <span style={{ margin: "0 6px", color: "#d1d5db", flexShrink: 0 }}>·</span>
        <span className="viv-row-variant">{entry.variant || "Unknown Variant"}</span>
      </div>
      {/* Classification shown inline on mobile */}
      <div className="viv-row-mobile-stats" style={{ marginTop: 4 }}>
        <span title={entry.classification || undefined}>{entry.classification || "No classification"}</span>
      </div>

      {/* Disease */}
      <div className="viv-row-disease" title={entry.disease || undefined}>
        {entry.disease || "—"}
      </div>

      {/* Classification badge */}
      <div>
        <span style={badgeInlineStyle(entry.classificationLevel)}>
          {classificationShortLabel(entry.classificationLevel)}
        </span>
      </div>

      {/* Evidence groups */}
      <div className="viv-row-stat">
        <FileText style={{ width: 14, height: 14, flexShrink: 0 }} />
        <span className="viv-row-stat-val">{entry.evidenceGroupCount}</span>
        <span>groups</span>
      </div>

      {/* Literature */}
      <div className="viv-row-stat">
        <BookOpen style={{ width: 14, height: 14, flexShrink: 0 }} />
        <span className="viv-row-stat-val">{entry.literatureCount}</span>
        <span>refs</span>
      </div>

      {/* Confidence */}
      <div className="viv-row-stat">
        <TrendingUp style={{ width: 14, height: 14, flexShrink: 0 }} />
        <span className="viv-row-stat-val">{formatConfidencePercent(entry.avgConfidence)}</span>
      </div>

      {hasQualityColumn(viewPrefs) && (
        <div style={{ minWidth: 0 }}>
          {viewPrefs.showCategories && (
            <CategoryDistributionBar distribution={entry.categoryDistribution} />
          )}
          {viewPrefs.showReviewProgress && (
            <span style={{ marginTop: viewPrefs.showCategories ? 4 : 0, display: "block", fontSize: 11, color: "#6b7280" }}>
              {formatReviewedCount(entry.reviewProgress)}
            </span>
          )}
        </div>
      )}

      {/* Updated date */}
      {viewPrefs.showUpdated && (
        <div className="viv-row-stat" style={{ color: "#9ca3af", fontSize: 12 }} title={entry.createdAt || undefined}>
          <Calendar style={{ width: 12, height: 12, flexShrink: 0 }} />
          <span>{formatDate(entry.createdAt)}</span>
        </div>
      )}

      {/* Mobile compact stats */}
      <div className="viv-row-mobile-stats">
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <FileText style={{ width: 12, height: 12 }} />
          <span className="viv-row-stat-val">{entry.evidenceGroupCount}</span>
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <BookOpen style={{ width: 12, height: 12 }} />
          <span className="viv-row-stat-val">{entry.literatureCount}</span>
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <TrendingUp style={{ width: 12, height: 12 }} />
          <span className="viv-row-stat-val">{formatConfidencePercent(entry.avgConfidence)}</span>
        </span>
        <span style={badgeInlineStyle(entry.classificationLevel)}>
          {classificationShortLabel(entry.classificationLevel)}
        </span>
        {viewPrefs.showUpdated && (
          <span style={{ color: "#9ca3af", fontSize: 11 }}>
            {formatDate(entry.createdAt)}
          </span>
        )}
        {viewPrefs.showReviewProgress && (
          <span style={{ color: "#6b7280", fontSize: 11 }}>
            {formatReviewedCount(entry.reviewProgress)}
          </span>
        )}
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
  const { prefs: viewPrefs, setPreference } = useEvidenceDbViewPrefs();

  const totalPages = Math.ceil(total / pageSize);

  const [jumpValue, setJumpValue] = useState("");

  const handleJump = useCallback(() => {
    const num = parseInt(jumpValue, 10);
    if (!Number.isNaN(num) && num >= 1 && num <= totalPages) {
      setPage(num);
      setJumpValue("");
    }
  }, [jumpValue, totalPages, setPage]);

  // Sort toggle for "Updated" column
  const toggleSort = useCallback(() => {
    const currentSortBy = filters.sortBy;
    const currentOrder = filters.sortOrder ?? "desc";
    if (currentSortBy !== "updated") {
      updateFilter("sortBy", "updated" as SortBy);
      updateFilter("sortOrder", "desc" as SortOrder);
    } else {
      // Cycle: desc → asc → clear
      if (currentOrder === "desc") {
        updateFilter("sortOrder", "asc" as SortOrder);
      } else {
        updateFilter("sortBy", undefined as unknown as SortBy);
        updateFilter("sortOrder", undefined as unknown as SortOrder);
      }
    }
  }, [filters.sortBy, filters.sortOrder, updateFilter]);

  // Generate page numbers with window around current page
  const pageNumbers = useMemo(() => {
    if (totalPages <= 7) {
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    }
    // Always show first, last, and a window around current
    const pages: number[] = [1];
    const windowStart = Math.max(2, page - 1);
    const windowEnd = Math.min(totalPages - 1, page + 1);
    if (windowStart > 2) pages.push(-1); // -1 = left ellipsis
    for (let p = windowStart; p <= windowEnd; p++) pages.push(p);
    if (windowEnd < totalPages - 1) pages.push(-2); // -2 = right ellipsis
    pages.push(totalPages);
    return pages;
  }, [totalPages, page]);

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
            label={EVIDENCE_DB_LABELS.uniqueVariants}
            accent="#8B5CF6"
          />
          <StatCard
            icon={FileText}
            value={stats.totalEvidenceGroups}
            label={EVIDENCE_DB_LABELS.evidenceGroups}
            accent="#0891B2"
          />
          <StatCard
            icon={BookOpen}
            value={stats.totalLiterature}
            label={EVIDENCE_DB_LABELS.literatureSources}
            accent="#F59E0B"
          />
          <StatCard
            icon={TrendingUp}
            value={formatConfidencePercent(stats.avgConfidence)}
            label={EVIDENCE_DB_LABELS.avgConfidence}
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
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
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
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                flexWrap: "wrap",
                fontSize: 12,
                color: "#4b5563",
              }}
              aria-label="Variant index display fields"
            >
              <span style={{ fontSize: 12, fontWeight: 500, color: "#6b7280" }}>Fields</span>
              <Checkbox
                checked={viewPrefs.showUpdated}
                onChange={(e) => setPreference("showUpdated", e.target.checked)}
              >
                {EVIDENCE_DB_LABELS.updated}
              </Checkbox>
              <Checkbox
                checked={viewPrefs.showCategories}
                onChange={(e) => setPreference("showCategories", e.target.checked)}
              >
                {EVIDENCE_DB_LABELS.categories}
              </Checkbox>
              <Checkbox
                checked={viewPrefs.showReviewProgress}
                onChange={(e) => setPreference("showReviewProgress", e.target.checked)}
              >
                {EVIDENCE_DB_LABELS.reviewProgress}
              </Checkbox>
            </div>
          </div>

          {/* Variant List */}
          <div className="viv-variant-list" style={{ marginTop: 16 }}>
            <div
              className="viv-list-header"
              style={{ gridTemplateColumns: variantGridTemplateColumns(viewPrefs) }}
            >
              <span>Gene / Variant</span>
              <span>Disease</span>
              <span>Class.</span>
              <span>Evidence</span>
              <span>Refs</span>
              <span>Conf.</span>
              {hasQualityColumn(viewPrefs) && (
                <span>
                  {viewPrefs.showCategories ? EVIDENCE_DB_LABELS.categories : EVIDENCE_DB_LABELS.reviewed}
                </span>
              )}
              {viewPrefs.showUpdated && (
                <button
                  type="button"
                  className="viv-sort-header"
                  onClick={toggleSort}
                  title="Sort by updated date"
                  style={{
                    background: "none",
                    border: "none",
                    padding: 0,
                    font: "inherit",
                    color: filters.sortBy === "updated" ? "#111827" : "#6b7280",
                  }}
                >
                  {EVIDENCE_DB_LABELS.updated}
                  {filters.sortBy === "updated" && (
                    filters.sortOrder === "asc"
                      ? <ArrowUp style={{ width: 12, height: 12 }} />
                      : <ArrowDown style={{ width: 12, height: 12 }} />
                  )}
                </button>
              )}
            </div>
            {items.map((entry, i) => (
              <div
                key={entry.variantSlug}
                className="edb-stagger"
                style={{ animationDelay: `${Math.min(i * 25, 250)}ms` }}
              >
                <VariantRow entry={entry} viewPrefs={viewPrefs} />
              </div>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              paddingTop: 8,
              flexWrap: "wrap",
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
              {pageNumbers.map((p, idx) => {
                if (p < 0) {
                  // Ellipsis placeholder
                  return (
                    <span key={`ellipsis-${idx}`} style={{ padding: "0 2px", color: "#9ca3af", fontSize: 14 }}>
                      &hellip;
                    </span>
                  );
                }
                const isActive = p === page;
                return (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setPage(p)}
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
                      fontWeight: isActive ? 600 : 500,
                      backgroundColor: isActive ? "var(--color-primary-600)" : "#fff",
                      color: isActive ? "#fff" : "#4b5563",
                      cursor: "pointer",
                      transition: "background-color 0.15s",
                    }}
                  >
                    {p}
                  </button>
                );
              })}
              <input
                className="viv-page-jump-input"
                type="text"
                inputMode="numeric"
                placeholder="#"
                value={jumpValue}
                onChange={(e) => {
                  const v = e.target.value.replace(/\D/g, "");
                  setJumpValue(v);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleJump();
                }}
                onBlur={handleJump}
                aria-label="Jump to page"
                title={`Jump to page (1–${totalPages})`}
              />
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
