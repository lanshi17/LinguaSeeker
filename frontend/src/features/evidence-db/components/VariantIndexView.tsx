import "../evidence-db.css";
import { useMemo, useState, useCallback, useEffect } from "react";
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
  Download,
} from "lucide-react";
import { AutoComplete, Checkbox, Input, Select, message } from "antd";
import { CategoryDistributionBar } from "./CategoryDistributionBar";
import { Spinner } from "@/components/ui/Spinner";
import { useVariantIndex } from "../hooks/useVariantIndex";
import { useEvidenceDbViewPrefs } from "../hooks/useEvidenceDbViewPrefs";
import { VariantIndexSkeleton } from "./VariantIndexSkeleton";
import type {
  SortBy,
  SortOrder,
  ReviewStatusFilter,
  SourceLanguageFilter,
  VariantIndexEntry,
} from "../types/variantDb";
import type { EvidenceDbViewPrefs } from "../hooks/useEvidenceDbViewPrefs";
import {
  classificationColor,
  classificationLabel,
  classificationShortLabel,
} from "../utils/pathogenicity";
import { CATEGORY_COLORS } from "@/features/evidence-search/utils/evidenceDocument";
import {
  getEvidenceDbLabels,
  formatConfidencePercent,
  formatReviewedCount,
} from "../utils/fieldLabels";
import { useI18n } from "@/lib/i18n";
import { usePagination } from "@/lib/hooks/usePagination";

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

function variantGridTemplateColumns(prefs: EvidenceDbViewPrefs, hasSelection: boolean): string {
  const columns: string[] = ["4px"];
  if (hasSelection) columns.push("36px");
  columns.push("2fr", "1.5fr", "100px", "100px", "100px");
  if (hasQualityColumn(prefs)) columns.push("120px");
  if (prefs.showFieldCount) columns.push("70px");
  if (prefs.showSourceLanguage) columns.push("96px");
  if (prefs.showPmid) columns.push("110px");
  if (prefs.showUpdated) columns.push("90px");
  return columns.join(" ");
}

/** Color for review status indicators */
function reviewStatusColor(status: string): string {
  switch (status) {
    case "approved": return "#16A34A";
    case "corrected": return "#D97706";
    case "rejected": return "#DC2626";
    default: return "#6B7280";
  }
}

/* ── Sort options ────────────────────────────────────────── */

function getSortOptions(t: (key: string) => string): { value: SortBy; label: string }[] {
  return [
    { value: "gene", label: t("evidenceDb.sort.gene") },
    { value: "variant", label: t("evidenceDb.sort.variant") },
    { value: "disease", label: t("evidenceDb.sort.disease") },
    { value: "evidence", label: t("evidenceDb.sort.evidence") },
    { value: "refs", label: t("evidenceDb.sort.refs") },
    { value: "confidence", label: t("evidenceDb.sort.confidence") },
    { value: "updated", label: t("evidenceDb.sort.updated") },
  ];
}

function getReviewStatusOptions(t: (key: string) => string) {
  return [
    { value: "provisional" as ReviewStatusFilter, label: t("evidenceDb.review.provisional") },
    { value: "approved" as ReviewStatusFilter, label: t("evidenceDb.review.approved") },
    { value: "corrected" as ReviewStatusFilter, label: t("evidenceDb.review.corrected") },
    { value: "rejected" as ReviewStatusFilter, label: t("evidenceDb.review.rejected") },
  ];
}

function getSourceLanguageOptions(t: (key: string) => string) {
  return [
    { value: "en" as SourceLanguageFilter, label: t("evidenceDb.language.en") },
    { value: "zh" as SourceLanguageFilter, label: t("evidenceDb.language.zh") },
    { value: "ja" as SourceLanguageFilter, label: t("evidenceDb.language.ja") },
    { value: "de" as SourceLanguageFilter, label: t("evidenceDb.language.de") },
    { value: "fr" as SourceLanguageFilter, label: t("evidenceDb.language.fr") },
    { value: "ru" as SourceLanguageFilter, label: t("evidenceDb.language.ru") },
  ];
}

function sourceLanguageLabel(code: string | undefined, t: (key: string) => string): string {
  if (!code) return t("evidenceDb.language.unknown");
  const key = `evidenceDb.language.${code}`;
  const label = t(key);
  return label === key ? code.toUpperCase() : label;
}

function sourceLanguageSummary(entry: VariantIndexEntry, t: (key: string) => string): string {
  if (entry.sourceLanguages.length === 0) {
    return sourceLanguageLabel(undefined, t);
  }
  return entry.sourceLanguages.map((code) => sourceLanguageLabel(code, t)).join(" / ");
}

/* ── Batch export helpers ────────────────────────────────── */

function csvEscape(value: unknown): string {
  const str = value == null ? "" : String(value);
  if (str.includes('"') || str.includes(",") || str.includes("\n") || str.includes("\r")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function buildExportCsv(entries: VariantIndexEntry[]): string {
  const headers = [
    "gene", "variant", "disease", "classification",
    "evidence_groups", "field_count", "literature_refs", "avg_confidence",
    "review_status", "source_language", "created_at", "title", "pmid", "doi",
  ];
  const rows = entries.map((e) => [
    e.gene, e.variant, e.disease, e.classification,
    String(e.evidenceGroupCount), String(e.fieldCount), String(e.literatureCount),
    e.avgConfidence.toFixed(2), e.reviewStatus, e.sourceLanguages.join(";"), e.createdAt ?? "",
    e.representative.title ?? "", e.representative.pmid ?? "", e.representative.doi ?? "",
  ]);
  return [headers.join(","), ...rows.map((r) => r.map(csvEscape).join(","))].join("\n");
}

function buildExportJson(entries: VariantIndexEntry[]): string {
  const payload = entries.map((e) => ({
    gene: e.gene,
    variant: e.variant,
    disease: e.disease,
    classification: e.classification,
    evidence_groups: e.evidenceGroupCount,
    field_count: e.fieldCount,
    literature_refs: e.literatureCount,
    avg_confidence: Number(e.avgConfidence.toFixed(3)),
    review_status: e.reviewStatus,
    source_language: e.sourceLanguages,
    created_at: e.createdAt ?? null,
    title: e.representative.title ?? null,
    pmid: e.representative.pmid ?? null,
    doi: e.representative.doi ?? null,
  }));
  return JSON.stringify({ variants: payload, exported_at: new Date().toISOString() }, null, 2);
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function exportVariants(
  entries: VariantIndexEntry[],
  format: "csv" | "json",
): void {
  const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  if (format === "csv") {
    triggerDownload(
      new Blob(["\uFEFF" + buildExportCsv(entries)], { type: "text/csv;charset=utf-8" }),
      `evidence-db-${ts}.csv`,
    );
  } else {
    triggerDownload(
      new Blob([buildExportJson(entries)], { type: "application/json;charset=utf-8" }),
      `evidence-db-${ts}.json`,
    );
  }
}


/* ── Main View ──────────────────────────────────────────── */

export function VariantIndexView() {
  const { t } = useI18n();
  const labels = getEvidenceDbLabels(t);
  const sortOptions = useMemo(() => getSortOptions(t), [t]);
  const reviewStatusOptions = useMemo(() => getReviewStatusOptions(t), [t]);
  const sourceLanguageOptions = useMemo(() => getSourceLanguageOptions(t), [t]);
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

  // ── Selection state ──────────────────────────────────────
  const [selectedSlugs, setSelectedSlugs] = useState<Set<string>>(new Set());

  // Reset selection when the visible items change (page / filter / sort)
  const itemSlugsKey = useMemo(() => items.map((i) => i.variantSlug).join("\0"), [items]);
  useEffect(() => {
    setSelectedSlugs(new Set());
  }, [itemSlugsKey]);

  const toggleSelectOne = useCallback((slug: string) => {
    setSelectedSlugs((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    setSelectedSlugs((prev) => {
      if (prev.size === items.length) return new Set();
      return new Set(items.map((i) => i.variantSlug));
    });
  }, [items]);

  const selectedEntries = useMemo(
    () => items.filter((i) => selectedSlugs.has(i.variantSlug)),
    [items, selectedSlugs],
  );

  const handleExport = useCallback(
    (format: "csv" | "json", scope: "selected" | "filtered") => {
      const entries = scope === "selected" ? selectedEntries : items;
      if (entries.length === 0) {
        void message.warning(t("evidenceDb.export.empty"));
        return;
      }
      try {
        exportVariants(entries, format);
        void message.success(
          t("evidenceDb.export.success", { count: String(entries.length) }),
        );
      } catch {
        void message.error(t("evidenceDb.export.error"));
      }
    },
    [selectedEntries, items, t],
  );

  // ── Sort dropdown handler ────────────────────────────────
  const handleSortChange = useCallback(
    (value: SortBy | "__clear__") => {
      if (value === "__clear__") {
        updateFilter("sortBy", undefined as unknown as SortBy);
        updateFilter("sortOrder", undefined as unknown as SortOrder);
        return;
      }
      // Toggle order if already active; default to asc for textual, desc for numeric
      if (filters.sortBy === value) {
        updateFilter(
          "sortOrder",
          (filters.sortOrder === "asc" ? "desc" : "asc") as SortOrder,
        );
        return;
      }
      const defaultOrder: SortOrder =
        value === "evidence" || value === "refs" || value === "confidence" || value === "updated"
          ? "desc"
          : "asc";
      updateFilter("sortBy", value);
      updateFilter("sortOrder", defaultOrder);
    },
    [filters.sortBy, filters.sortOrder, updateFilter],
  );

  const searchText = filters.gene ?? filters.variant ?? "";
  const hasAnyFilter = !!(
    filters.gene ||
    filters.variant ||
    filters.disease ||
    filters.classification ||
    filters.reviewStatus ||
    filters.sourceLanguage
  );
  const allPageSelected = items.length > 0 && selectedSlugs.size === items.length;
  const anySelected = selectedSlugs.size > 0;

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

      {/* Dataset at a glance — research-panel aesthetic */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          border: "1px solid var(--color-border)",
          borderRadius: 10,
          backgroundColor: "var(--color-surface)",
          overflow: "hidden",
        }}
      >
        {[
          { label: labels.uniqueVariants, value: String(stats.totalVariants) },
          { label: labels.evidenceGroups, value: String(stats.totalEvidenceGroups) },
          { label: labels.literatureSources, value: String(stats.totalLiterature) },
          { label: labels.avgConfidence, value: formatConfidencePercent(stats.avgConfidence) },
        ].map((s, i) => (
          <div
            key={s.label}
            style={{
              padding: "14px 18px",
              borderRight: i < 3 ? "1px solid var(--color-border)" : "none",
            }}
          >
            <div
              style={{
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                color: "var(--color-text-secondary)",
                marginBottom: 6,
              }}
            >
              {s.label}
            </div>
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 20,
                fontWeight: 500,
                color: "var(--color-text)",
                letterSpacing: "-0.01em",
              }}
            >
              {s.value}
            </div>
          </div>
        ))}
      </section>

      {/* Search & filter — compact research-tool layout */}
      <section
        style={{
          borderRadius: 10,
          border: "1px solid var(--color-border)",
          backgroundColor: "var(--color-surface)",
          overflow: "hidden",
        }}
      >
        {/* Primary search row */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 220px 170px 180px",
            gap: 12,
            padding: "10px 12px",
            alignItems: "center",
          }}
        >
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
              variant="borderless"
              prefix={<Search style={{ width: 14, height: 14, color: "var(--color-text-muted)" }} />}
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
                      padding: 0,
                      color: "var(--color-text-muted)",
                      display: "flex",
                      alignItems: "center",
                    }}
                    aria-label={t("evidenceDb.clearAll")}
                  >
                    <X style={{ width: 13, height: 13 }} />
                  </button>
                ) : undefined
              }
              allowClear={false}
            />
          </AutoComplete>

          <AutoComplete
            style={{ width: "100%" }}
            options={diseaseCandidates}
            value={filters.disease ?? ""}
            onChange={(val) => updateFilter("disease", val || undefined)}
            popupMatchSelectWidth={true}
          >
            <Input
              placeholder={t("evidenceDb.filterDiseasePh")}
              variant="borderless"
            />
          </AutoComplete>

          <Select
            size="small"
            allowClear
            placeholder={t("evidenceDb.language.label")}
            value={filters.sourceLanguage}
            onChange={(v) => updateFilter("sourceLanguage", v as SourceLanguageFilter | undefined)}
            style={{ width: "100%" }}
            popupMatchSelectWidth={false}
            options={sourceLanguageOptions}
          />

          <Select
            size="small"
            allowClear
            placeholder={t("evidenceDb.review.label")}
            value={filters.reviewStatus}
            onChange={(v) => updateFilter("reviewStatus", v as ReviewStatusFilter | undefined)}
            style={{ width: "100%" }}
            popupMatchSelectWidth={false}
            options={reviewStatusOptions}
          />
        </div>

        {/* Sort strip */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: 8,
            padding: "8px 12px",
            borderTop: "1px solid var(--color-border)",
            backgroundColor: "var(--color-bg)",
          }}
        >
          <div style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span
              style={{
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                color: "var(--color-text-secondary)",
              }}
            >
              {t("evidenceDb.sort.label")}
            </span>
            <Select
              size="small"
              value={filters.sortBy ?? "__clear__"}
              onChange={(v) => handleSortChange(v as SortBy | "__clear__")}
              style={{ minWidth: 150 }}
              popupMatchSelectWidth={false}
              options={[
                { value: "__clear__", label: t("evidenceDb.sort.default") },
                ...sortOptions,
              ]}
            />
            {filters.sortBy && (
              <button
                type="button"
                onClick={() =>
                  updateFilter(
                    "sortOrder",
                    (filters.sortOrder === "asc" ? "desc" : "asc") as SortOrder,
                  )
                }
                title={
                  filters.sortOrder === "asc"
                    ? t("evidenceDb.sort.orderAsc")
                    : t("evidenceDb.sort.orderDesc")
                }
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  cursor: "pointer",
                  borderRadius: 6,
                  border: "1px solid var(--color-border)",
                  backgroundColor: "var(--color-surface)",
                  color: "var(--color-text-strong)",
                  padding: "3px 8px",
                  fontSize: 11,
                  fontWeight: 500,
                }}
              >
                {filters.sortOrder === "asc" ? (
                  <ArrowUp style={{ width: 11, height: 11 }} />
                ) : (
                  <ArrowDown style={{ width: 11, height: 11 }} />
                )}
                {filters.sortOrder === "asc"
                  ? t("evidenceDb.sort.orderAsc")
                  : t("evidenceDb.sort.orderDesc")}
              </button>
            )}
          </div>

          {hasAnyFilter && (
            <button
              type="button"
              onClick={clearFilters}
              className="viv-clear-btn"
              style={{
                cursor: "pointer",
                marginLeft: "auto",
                borderRadius: 6,
                border: "none",
                padding: "3px 8px",
                fontSize: 11,
                fontWeight: 500,
                color: "var(--color-text-secondary)",
                backgroundColor: "transparent",
                transition: "color 0.15s",
              }}
            >
              {t("evidenceDb.clearAll")}
            </button>
          )}
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
          {/* Status hairline */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "auto 1fr auto",
              alignItems: "center",
              gap: 16,
              padding: "6px 4px",
              borderBottom: "1px solid var(--color-border)",
              marginBottom: 12,
            }}
          >
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 12,
                color: "var(--color-text-strong)",
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <span style={{ fontWeight: 600 }}>{total}</span>
              <span style={{ color: "var(--color-text-secondary)", fontWeight: 400 }}>
                {t("evidenceDb.variantsFound")}
              </span>
              {isFetching && <Spinner size="sm" />}
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 10,
                fontSize: 11,
                color: "var(--color-text-secondary)",
                flexWrap: "wrap",
              }}
            >
              <span style={{ fontWeight: 500, letterSpacing: "0.05em" }}>
                {t("evidenceDb.label.evidenceFields")}
              </span>
              {[
                { key: "showFieldCount" as const, label: labels.fieldCount },
                { key: "showSourceLanguage" as const, label: t("evidenceDb.language.label") },
                { key: "showPmid" as const, label: labels.pmid },
                { key: "showCategories" as const, label: labels.categories },
                { key: "showReviewProgress" as const, label: labels.reviewProgress },
                { key: "showUpdated" as const, label: labels.updated },
              ].map((opt) => (
                <button
                  key={opt.key}
                  type="button"
                  onClick={() => setPreference(opt.key, !viewPrefs[opt.key])}
                  style={{
                    cursor: "pointer",
                    borderRadius: 9999,
                    border: `1px solid ${viewPrefs[opt.key] ? "var(--color-text)" : "var(--color-border)"}`,
                    backgroundColor: viewPrefs[opt.key] ? "var(--color-text)" : "transparent",
                    color: viewPrefs[opt.key] ? "var(--color-surface)" : "var(--color-text-secondary)",
                    padding: "2px 8px",
                    fontSize: 10,
                    fontWeight: 500,
                    letterSpacing: "0.02em",
                    transition: "all 0.15s",
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                color: "var(--color-text-secondary)",
              }}
            >
              {t("evidenceDb.pageInfo", { current: String(page), total: String(totalPages || 1) })}
            </div>
          </div>

          {/* Batch actions bar */}
          {anySelected && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
                flexWrap: "wrap",
                marginBottom: 12,
                padding: "8px 12px",
                borderRadius: 8,
                border: "1px solid var(--color-text)",
                backgroundColor: "var(--color-surface)",
              }}
            >
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                  fontWeight: 500,
                  color: "var(--color-text-strong)",
                }}
              >
                {t("evidenceDb.export.selected", { count: String(selectedSlugs.size) })}
              </span>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <button
                  type="button"
                  onClick={() => handleExport("csv", "selected")}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    cursor: "pointer",
                    borderRadius: 6,
                    border: "1px solid var(--color-border)",
                    backgroundColor: "var(--color-surface)",
                    color: "var(--color-text-strong)",
                    padding: "3px 10px",
                    fontSize: 11,
                    fontWeight: 500,
                  }}
                >
                  <Download style={{ width: 11, height: 11 }} />
                  {t("evidenceDb.export.csv")}
                </button>
                <button
                  type="button"
                  onClick={() => handleExport("json", "selected")}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    cursor: "pointer",
                    borderRadius: 6,
                    border: "1px solid var(--color-border)",
                    backgroundColor: "var(--color-surface)",
                    color: "var(--color-text-strong)",
                    padding: "3px 10px",
                    fontSize: 11,
                    fontWeight: 500,
                  }}
                >
                  <Download style={{ width: 11, height: 11 }} />
                  {t("evidenceDb.export.json")}
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedSlugs(new Set())}
                  style={{
                    cursor: "pointer",
                    borderRadius: 6,
                    border: "none",
                    backgroundColor: "transparent",
                    color: "var(--color-text-secondary)",
                    padding: "3px 8px",
                    fontSize: 11,
                    fontWeight: 500,
                  }}
                >
                  {t("evidenceDb.export.clearSelection")}
                </button>
              </div>
            </div>
          )}

          {!anySelected && items.length > 0 && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "flex-end",
                gap: 6,
                marginBottom: 12,
                flexWrap: "wrap",
              }}
            >
              <span style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>
                {t("evidenceDb.export.downloadPage")}
              </span>
              <button
                type="button"
                onClick={() => handleExport("csv", "filtered")}
                disabled={items.length === 0}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 5,
                  cursor: "pointer",
                  borderRadius: 6,
                  border: "1px solid var(--color-border)",
                  backgroundColor: "var(--color-surface)",
                  color: "var(--color-text-strong)",
                  padding: "3px 9px",
                  fontSize: 11,
                  fontWeight: 500,
                }}
              >
                <Download style={{ width: 11, height: 11 }} />
                {t("evidenceDb.export.csv")}
              </button>
              <button
                type="button"
                onClick={() => handleExport("json", "filtered")}
                disabled={items.length === 0}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 5,
                  cursor: "pointer",
                  borderRadius: 6,
                  border: "1px solid var(--color-border)",
                  backgroundColor: "var(--color-surface)",
                  color: "var(--color-text-strong)",
                  padding: "3px 9px",
                  fontSize: 11,
                  fontWeight: 500,
                }}
              >
                <Download style={{ width: 11, height: 11 }} />
                {t("evidenceDb.export.json")}
              </button>
            </div>
          )}

          {/* Variant List */}
          <div className="viv-variant-list" style={{ marginTop: 16 }}>
            <div
              className="viv-list-header"
              style={{ gridTemplateColumns: variantGridTemplateColumns(viewPrefs, true) }}
            >
              <span aria-hidden />
              <div style={{ display: "flex", alignItems: "center" }}>
                <Checkbox
                  checked={allPageSelected}
                  indeterminate={anySelected && !allPageSelected}
                  onChange={toggleSelectAll}
                  aria-label={t("evidenceDb.export.selectAll")}
                />
              </div>
              <span>{t("evidenceDb.listGene")} / {t("evidenceDb.listVariant")}</span>
              <span>{t("evidenceDb.listDisease")}</span>
              <span>{t("evidenceDb.listEvidence")}</span>
              <span>{t("evidenceDb.listRefs")}</span>
              <span>{t("evidenceDb.listConf")}</span>
              {hasQualityColumn(viewPrefs) && (
                <span>
                  {viewPrefs.showCategories ? labels.categories : labels.reviewed}
                </span>
              )}
              {viewPrefs.showFieldCount && (
                <span>{t("evidenceDb.listFields")}</span>
              )}
              {viewPrefs.showSourceLanguage && (
                <span>{t("evidenceDb.language.label")}</span>
              )}
              {viewPrefs.showPmid && (
                <span>{t("evidenceDb.listPmid")}</span>
              )}
              {viewPrefs.showUpdated && (
                <span>{labels.updated}</span>
              )}
            </div>
            {items.map((entry, i) => {
              const isSelected = selectedSlugs.has(entry.variantSlug);
              return (
                <div
                  key={entry.variantSlug}
                  className="edb-stagger"
                  style={{ animationDelay: `${Math.min(i * 25, 250)}ms` }}
                >
                  <Link
                    to={`/evidence-db/${encodeURIComponent(entry.variantSlug)}`}
                    state={{ variantEntry: entry }}
                    className="viv-row"
                    style={{
                      gridTemplateColumns: variantGridTemplateColumns(viewPrefs, true),
                      backgroundColor: isSelected ? "var(--color-primary-50, #eff6ff)" : undefined,
                    }}
                  >
                    {/* Classification color indicator */}
                    <div
                      style={{
                        width: 4,
                        alignSelf: "stretch",
                        borderRadius: 2,
                        backgroundColor: classificationColor(entry.classificationLevel),
                      }}
                      title={entry.classification || classificationShortLabel(entry.classificationLevel)}
                    />
                    {/* Selection checkbox */}
                    <div
                      style={{ display: "flex", alignItems: "center", justifyContent: "flex-start" }}
                      onClick={(e) => e.stopPropagation()}
                      onKeyDown={(e) => e.stopPropagation()}
                    >
                      <Checkbox
                        checked={isSelected}
                        onChange={() => toggleSelectOne(entry.variantSlug)}
                        aria-label={t("evidenceDb.export.selectRow", {
                          variant: `${entry.gene || "?"} ${entry.variant || "?"}`.trim(),
                        })}
                      />
                    </div>
                    {/* Gene + Variant (primary column) with classification badge */}
                    <div style={{ minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span className="viv-row-gene">{entry.gene || t("evidenceDb.unknownGene")}</span>
                        {entry.classification && entry.classificationLevel !== "uncertain" && (
                          <span
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              height: 16,
                              padding: "0 5px",
                              borderRadius: 3,
                              fontSize: 9,
                              fontWeight: 700,
                              letterSpacing: "0.03em",
                              backgroundColor: `${classificationColor(entry.classificationLevel)}18`,
                              color: classificationColor(entry.classificationLevel),
                              border: `1px solid ${classificationColor(entry.classificationLevel)}30`,
                              flexShrink: 0,
                              lineHeight: 1,
                            }}
                            title={classificationLabel(entry.classificationLevel, t)}
                          >
                            {classificationShortLabel(entry.classificationLevel)}
                          </span>
                        )}
                      </div>
                      <span className="viv-row-variant">{entry.variant || t("evidenceDb.unknownVariant")}</span>
                    </div>
                  {/* Disease with review status */}
                  <div style={{ minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
                    <div className="viv-row-disease" title={entry.disease || undefined}>
                      {entry.disease || "—"}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      <span
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: "50%",
                          backgroundColor: reviewStatusColor(entry.reviewStatus),
                          flexShrink: 0,
                        }}
                      />
                      <span style={{ fontSize: 10, color: "var(--color-text-muted)" }}>
                        {t(`evidenceDb.review.${entry.reviewStatus}`)}
                      </span>
                    </div>
                  </div>

                  {/* Evidence categories with inline review progress */}
                  <div style={{ minWidth: 0, display: "flex", flexDirection: "column", gap: 3 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 3, flexWrap: "wrap" }}>
                      {(() => {
                        const cats = Object.entries(entry.categoryDistribution)
                          .filter(([, c]) => c > 0)
                          .sort(([a], [b]) => a.localeCompare(b));
                        if (cats.length === 0) return <span style={{ color: "var(--color-text-muted)", fontSize: 12 }}>—</span>;
                        const max = 6;
                        return (
                          <>
                            {cats.slice(0, max).map(([cat, count]) => {
                              const color = CATEGORY_COLORS[cat]?.hex ?? "#64748B";
                              return (
                                <span
                                  key={cat}
                                  style={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    width: 18,
                                    height: 18,
                                    borderRadius: 4,
                                    border: `1px solid ${color}40`,
                                    backgroundColor: `${color}18`,
                                    color: color,
                                    fontSize: 10,
                                    fontWeight: 600,
                                    fontFamily: "var(--font-mono)",
                                  }}
                                  title={`${CATEGORY_COLORS[cat]?.label ?? `Cat. ${cat}`}: ${count}`}
                                >
                                  {cat}
                                </span>
                              );
                            })}
                            {cats.length > max && (
                              <span style={{ fontSize: 10, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
                                +{cats.length - max}
                              </span>
                            )}
                          </>
                        );
                      })()}
                    </div>
                    <span style={{ fontSize: 10, color: "var(--color-text-muted)" }}>
                      {formatReviewedCount(entry.reviewProgress)}
                    </span>
                  </div>

                  {/* Literature with inline PMID */}
                  <div style={{ minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
                    <div className="viv-row-stat">
                      <BookOpen style={{ width: 14, height: 14, flexShrink: 0 }} />
                      <span className="viv-row-stat-val">{entry.literatureCount}</span>
                      <span>{t("evidenceDb.statRefs")}</span>
                    </div>
                    {entry.representative.pmid && (
                      <span
                        style={{
                          fontSize: 10,
                          fontFamily: "var(--font-mono)",
                          color: "var(--color-primary-600)",
                          cursor: "pointer",
                          textDecoration: "none",
                        }}
                        onClick={(e) => {
                          e.stopPropagation();
                          e.preventDefault();
                          window.open(`https://pubmed.ncbi.nlm.nih.gov/${entry.representative.pmid}`, "_blank", "noopener,noreferrer");
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.stopPropagation();
                            e.preventDefault();
                            window.open(`https://pubmed.ncbi.nlm.nih.gov/${entry.representative.pmid}`, "_blank", "noopener,noreferrer");
                          }
                        }}
                        title={`PMID: ${entry.representative.pmid}`}
                      >
                        PMID:{entry.representative.pmid}
                      </span>
                    )}
                  </div>

                  {/* Confidence with review status */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <div className="viv-row-stat">
                      <span className="viv-row-stat-val">{formatConfidencePercent(entry.avgConfidence)}</span>
                    </div>
                    <div style={{ width: "100%", height: 3, borderRadius: 2, backgroundColor: "var(--color-border)" }}>
                      <div
                        style={{
                          width: `${Math.round((entry.avgConfidence ?? 0) * 100)}%`,
                          height: 3,
                          borderRadius: 2,
                          backgroundColor: (entry.avgConfidence ?? 0) >= 0.7
                            ? "var(--color-success-600, #16a34a)"
                            : (entry.avgConfidence ?? 0) >= 0.4
                              ? "var(--color-warning-600, #d97706)"
                              : "var(--color-error-600, #dc2626)",
                        }}
                      />
                    </div>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 500,
                        color: reviewStatusColor(entry.reviewStatus),
                      }}
                    >
                      {t(`evidenceDb.review.${entry.reviewStatus}`)}
                    </span>
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

                  {/* Field count */}
                  {viewPrefs.showFieldCount && (
                    <div className="viv-row-stat">
                      <FileText style={{ width: 12, height: 12, flexShrink: 0 }} />
                      <span className="viv-row-stat-val">{entry.fieldCount}</span>
                    </div>
                  )}

                  {/* Source language */}
                  {viewPrefs.showSourceLanguage && (
                    <div style={{ minWidth: 0 }}>
                      <span
                        className="viv-source-language-chip"
                        title={t("evidenceDb.language.label")}
                      >
                        {sourceLanguageSummary(entry, t)}
                      </span>
                    </div>
                  )}

                  {/* PMID standalone column */}
                  {viewPrefs.showPmid && (
                    <div style={{ minWidth: 0 }}>
                      {entry.representative.pmid ? (
                        <span
                          style={{
                            fontSize: 11,
                            fontFamily: "var(--font-mono)",
                            color: "var(--color-primary-600)",
                            cursor: "pointer",
                          }}
                          onClick={(e) => {
                            e.stopPropagation();
                            e.preventDefault();
                            window.open(`https://pubmed.ncbi.nlm.nih.gov/${entry.representative.pmid}`, "_blank", "noopener,noreferrer");
                          }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.stopPropagation();
                              e.preventDefault();
                              window.open(`https://pubmed.ncbi.nlm.nih.gov/${entry.representative.pmid}`, "_blank", "noopener,noreferrer");
                            }
                          }}
                          title={`PMID: ${entry.representative.pmid}`}
                        >
                          {entry.representative.pmid}
                        </span>
                      ) : (
                        <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>—</span>
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
                    {entry.classification && entry.classificationLevel !== "uncertain" && (
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          height: 14,
                          padding: "0 4px",
                          borderRadius: 3,
                          fontSize: 9,
                          fontWeight: 700,
                          backgroundColor: `${classificationColor(entry.classificationLevel)}18`,
                          color: classificationColor(entry.classificationLevel),
                        }}
                      >
                        {classificationShortLabel(entry.classificationLevel)}
                      </span>
                    )}
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
                    {viewPrefs.showSourceLanguage && (
                      <span className="viv-source-language-chip">
                        {sourceLanguageSummary(entry, t)}
                      </span>
                    )}
                  </div>
                </Link>
              </div>
              );
            })}
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
