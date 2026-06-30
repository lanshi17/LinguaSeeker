import "../evidence-db.css";
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
import { StatCard } from "./StatCard";
import { CategoryDistributionBar } from "./CategoryDistributionBar";
import { Spinner } from "@/components/ui/Spinner";
import { useVariantIndex } from "../hooks/useVariantIndex";
import { useEvidenceDbViewPrefs } from "../hooks/useEvidenceDbViewPrefs";
import { VariantIndexSkeleton } from "./VariantIndexSkeleton";
import type {
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
  getEvidenceDbLabels,
  formatConfidencePercent,
  formatReviewedCount,
} from "../utils/fieldLabels";
import { useI18n } from "@/lib/i18n";
import { usePagination } from "@/lib/hooks/usePagination";

function getClassificationOptions(t: (key: string) => string) {
  return [
    { value: "pathogenic" as ClassificationLevel, label: t("evidenceDb.class.pathogenic") },
    { value: "likely_pathogenic" as ClassificationLevel, label: t("evidenceDb.class.likelyPathogenic") },
    { value: "uncertain" as ClassificationLevel, label: t("evidenceDb.class.vus") },
    { value: "likely_benign" as ClassificationLevel, label: t("evidenceDb.class.likelyBenign") },
    { value: "benign" as ClassificationLevel, label: t("evidenceDb.class.benign") },
  ];
}

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


/* ── Main View ──────────────────────────────────────────── */

export function VariantIndexView() {
  const { t } = useI18n();
  const labels = getEvidenceDbLabels(t);
  const classificationOptions = getClassificationOptions(t);
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

  const { pageNumbers, canPrev, canNext, goPrev, goNext, goTo } = usePagination({
    page,
    totalPages,
    onPageChange: setPage,
  });

  const [jumpValue, setJumpValue] = useState("");

  const handleJump = useCallback(() => {
    const num = parseInt(jumpValue, 10);
    if (!Number.isNaN(num) && num >= 1 && num <= totalPages) {
      goTo(num);
      setJumpValue("");
    }
  }, [jumpValue, totalPages, goTo]);

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

      {/* Hero Stats Section */}
      <section className="edb-hero" style={{ borderRadius: 16, border: "1px solid var(--color-border)", padding: 24 }}>
        <div className="viv-stats-grid">
          <StatCard
            icon={Dna}
            value={stats.totalVariants}
            label={labels.uniqueVariants}
            accent="#8B5CF6"
          />
          <StatCard
            icon={FileText}
            value={stats.totalEvidenceGroups}
            label={labels.evidenceGroups}
            accent="#0891B2"
          />
          <StatCard
            icon={BookOpen}
            value={stats.totalLiterature}
            label={labels.literatureSources}
            accent="#F59E0B"
          />
          <StatCard
            icon={TrendingUp}
            value={formatConfidencePercent(stats.avgConfidence)}
            label={labels.avgConfidence}
            accent="#0F766E"
          />
        </div>
      </section>

      {/* Search & Filter Bar */}
      <section style={{ borderRadius: 12, border: "1px solid var(--color-border)", backgroundColor: "var(--color-surface)", padding: 16 }}>
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
                placeholder={t("evidenceDb.searchGenePh")}
                prefix={<Search style={{ width: 16, height: 16, color: "var(--color-text-muted)" }} />}
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
                        color: "var(--color-text-muted)",
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
              <Input placeholder={t("evidenceDb.filterDiseasePh")} />
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
                border: "1px solid var(--color-border)",
                padding: "4px 12px",
                fontSize: 12,
                fontWeight: 500,
                color: "var(--color-text-strong)",
                backgroundColor: "var(--color-surface)",
                transition: "background-color 0.15s",
              }}
            >
              {t("evidenceDb.clearAll")}
            </button>
          )}
        </div>

        {/* Classification filter pills */}
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--color-bg-muted)" }}>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6 }}>
            <button
              type="button"
              onClick={() => updateFilter("classification", undefined)}
              className="viv-filter-pill"
              style={{
                cursor: "pointer",
                borderRadius: 9999,
                border: !filters.classification ? "1px solid var(--color-text)" : "1px solid var(--color-border)",
                backgroundColor: !filters.classification ? "var(--color-text)" : "var(--color-surface)",
                color: !filters.classification ? "var(--color-surface)" : "var(--color-text-strong)",
                padding: "4px 10px",
                fontSize: 12,
                fontWeight: 500,
                transition: "all 0.15s",
              }}
            >
              {t("evidenceDb.class.all")}
            </button>
            {classificationOptions.map((opt) => {
              const hex = classificationColor(opt.value);
              const isActive = filters.classification === opt.value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() =>
                    updateFilter("classification", filters.classification === opt.value ? undefined : opt.value)
                  }
                  className="viv-filter-pill"
                  style={{
                    cursor: "pointer",
                    borderRadius: 9999,
                    border: isActive ? "1px solid transparent" : "1px solid var(--color-border)",
                    backgroundColor: isActive ? hex : "var(--color-surface)",
                    color: isActive ? "var(--color-surface)" : "var(--color-text-strong)",
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
        </div>
      </section>

      {/* Results */}
      {error ? (
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          borderRadius: 12,
          border: "1px solid var(--color-error-border)",
          backgroundColor: "var(--color-error-bg)",
          padding: 16,
          fontSize: 14,
          color: "var(--color-error-text)",
        }}>
          <AlertCircle style={{ width: 20, height: 20, flexShrink: 0 }} />
          <span>{t("evidenceDb.loadError")}</span>
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
          border: "1px dashed var(--color-text-muted)",
          padding: "80px 0",
          textAlign: "center",
        }}>
          <Dna style={{ width: 40, height: 40, color: "var(--color-text-muted)", marginBottom: 12 }} />
          <p style={{ fontSize: 14, fontWeight: 500, color: "var(--color-text-strong)", margin: 0 }}>
            {t("evidenceDb.empty.noVariants")}
          </p>
          <p style={{ fontSize: 12, color: "var(--color-text-secondary)", marginTop: 4, margin: 0 }}>
            {t("evidenceDb.empty.adjustFilters")}
          </p>
        </div>
      ) : (
        <div className="content-fade-in">
          {/* Result count */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
            <p style={{ fontSize: 14, color: "var(--color-text-strong)", margin: 0 }}>
              <span style={{ fontWeight: 500, color: "var(--color-text)" }}>{total}</span>{" "}
              {t("evidenceDb.variantsFound")}
              {isFetching && (
                <span style={{ marginLeft: 8, display: "inline-block" }}>
                  <Spinner size="sm" />
                </span>
              )}
            </p>
            <p style={{ fontSize: 12, color: "var(--color-text-secondary)", margin: 0 }}>
              {t("evidenceDb.pageInfo", { current: String(page), total: String(totalPages || 1) })}
            </p>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                flexWrap: "wrap",
                fontSize: 12,
                color: "var(--color-text-strong)",
              }}
              aria-label={t("evidenceDb.label.evidenceFields")}
            >
              <span style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-secondary)" }}>{t("evidenceDb.label.evidenceFields")}</span>
              <Checkbox
                checked={viewPrefs.showUpdated}
                onChange={(e) => setPreference("showUpdated", e.target.checked)}
              >
                {labels.updated}
              </Checkbox>
              <Checkbox
                checked={viewPrefs.showCategories}
                onChange={(e) => setPreference("showCategories", e.target.checked)}
              >
                {labels.categories}
              </Checkbox>
              <Checkbox
                checked={viewPrefs.showReviewProgress}
                onChange={(e) => setPreference("showReviewProgress", e.target.checked)}
              >
                {labels.reviewProgress}
              </Checkbox>
            </div>
          </div>

          {/* Variant List */}
          <div className="viv-variant-list" style={{ marginTop: 16 }}>
            <div
              className="viv-list-header"
              style={{ gridTemplateColumns: variantGridTemplateColumns(viewPrefs) }}
            >
              <span>{t("evidenceDb.listGene")} / {t("evidenceDb.listVariant")}</span>
              <span>{t("evidenceDb.listDisease")}</span>
              <span>{t("evidenceDb.listClass")}</span>
              <span>{t("evidenceDb.listEvidence")}</span>
              <span>{t("evidenceDb.listRefs")}</span>
              <span>{t("evidenceDb.listConf")}</span>
              {hasQualityColumn(viewPrefs) && (
                <span>
                  {viewPrefs.showCategories ? labels.categories : labels.reviewed}
                </span>
              )}
              {viewPrefs.showUpdated && (
                <button
                  type="button"
                  className="viv-sort-header"
                  onClick={toggleSort}
                  title={labels.updated}
                  style={{
                    background: "none",
                    border: "none",
                    padding: 0,
                    font: "inherit",
                    color: filters.sortBy === "updated" ? "var(--color-text)" : "var(--color-text-secondary)",
                  }}
                >
                  {labels.updated}
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
                <Link
                  to={`/evidence-db/${encodeURIComponent(entry.variantSlug)}`}
                  state={{ variantEntry: entry }}
                  className="viv-row"
                  style={{ gridTemplateColumns: variantGridTemplateColumns(viewPrefs) }}
                >
                  {/* Gene + Variant (primary column) */}
                  <div style={{ minWidth: 0, display: "flex", alignItems: "baseline", flexWrap: "nowrap" }} title={`${entry.gene || t("evidenceDb.unknownGene")} · ${entry.variant || t("evidenceDb.unknownVariant")}`}>
                    <span className="viv-row-gene">{entry.gene || t("evidenceDb.unknownGene")}</span>
                    <span style={{ margin: "0 6px", color: "var(--color-text-muted)", flexShrink: 0 }}>·</span>
                    <span className="viv-row-variant">{entry.variant || t("evidenceDb.unknownVariant")}</span>
                  </div>
                  {/* Classification shown inline on mobile */}
                  <div className="viv-row-mobile-stats" style={{ marginTop: 4 }}>
                    <span title={entry.classification || undefined}>{entry.classification || t("evidenceDb.noClass")}</span>
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
                    <span>{t("evidenceDb.statGroups")}</span>
                  </div>

                  {/* Literature */}
                  <div className="viv-row-stat">
                    <BookOpen style={{ width: 14, height: 14, flexShrink: 0 }} />
                    <span className="viv-row-stat-val">{entry.literatureCount}</span>
                    <span>{t("evidenceDb.statRefs")}</span>
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
                        <span style={{ marginTop: viewPrefs.showCategories ? 4 : 0, display: "block", fontSize: 11, color: "var(--color-text-secondary)" }}>
                          {formatReviewedCount(entry.reviewProgress)}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Updated date */}
                  {viewPrefs.showUpdated && (
                    <div className="viv-row-stat" style={{ color: "var(--color-text-muted)", fontSize: 12 }} title={entry.createdAt || undefined}>
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
                      <span style={{ color: "var(--color-text-muted)", fontSize: 11 }}>
                        {formatDate(entry.createdAt)}
                      </span>
                    )}
                    {viewPrefs.showReviewProgress && (
                      <span style={{ color: "var(--color-text-secondary)", fontSize: 11 }}>
                        {formatReviewedCount(entry.reviewProgress)}
                      </span>
                    )}
                  </div>
                </Link>
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
                onClick={goPrev}
                disabled={!canPrev}
                className={canPrev ? "viv-page-btn" : undefined}
                style={{
                  display: "flex",
                  width: 36,
                  height: 36,
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: 8,
                  border: !canPrev ? "1px solid var(--color-bg-muted)" : "1px solid var(--color-border)",
                  fontSize: 14,
                  color: !canPrev ? "var(--color-text-muted)" : "var(--color-text-strong)",
                  cursor: !canPrev ? "not-allowed" : "pointer",
                  backgroundColor: "var(--color-surface)",
                  transition: "background-color 0.15s",
                }}
              >
                <ChevronLeft style={{ width: 16, height: 16 }} />
              </button>
              {pageNumbers.map((p, idx) => {
                if (p < 0) {
                  // Ellipsis placeholder
                  return (
                    <span key={`ellipsis-${idx}`} style={{ padding: "0 2px", color: "var(--color-text-muted)", fontSize: 14 }}>
                      &hellip;
                    </span>
                  );
                }
                const isActive = p === page;
                return (
                  <button
                    key={p}
                    type="button"
                    onClick={() => goTo(p)}
                    className={!isActive ? "viv-page-btn" : undefined}
                    style={{
                      display: "flex",
                      width: 36,
                      height: 36,
                      alignItems: "center",
                      justifyContent: "center",
                      borderRadius: 8,
                      border: isActive ? "1px solid var(--color-primary-600)" : "1px solid var(--color-border)",
                      fontSize: 14,
                      fontWeight: isActive ? 600 : 500,
                      backgroundColor: isActive ? "var(--color-primary-600)" : "var(--color-surface)",
                      color: isActive ? "var(--color-surface)" : "var(--color-text-strong)",
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
                aria-label={t("evidenceDb.jumpToPage")}
                title={`${t("evidenceDb.jumpToPage")} (1\u2013${totalPages})`}
              />
              <button
                type="button"
                onClick={goNext}
                disabled={!canNext}
                className={canNext ? "viv-page-btn" : undefined}
                style={{
                  display: "flex",
                  width: 36,
                  height: 36,
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: 8,
                  border: !canNext ? "1px solid var(--color-bg-muted)" : "1px solid var(--color-border)",
                  fontSize: 14,
                  color: !canNext ? "var(--color-text-muted)" : "var(--color-text-strong)",
                  cursor: !canNext ? "not-allowed" : "pointer",
                  backgroundColor: "var(--color-surface)",
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
