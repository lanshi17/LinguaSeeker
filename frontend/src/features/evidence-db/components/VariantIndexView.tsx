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
} from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { Spinner } from "@/components/ui/Spinner";
import { useVariantIndex } from "../hooks/useVariantIndex";
import type {
  VariantIndexEntry,
  ClassificationLevel,
} from "../types/variantDb";
import {
  classificationColor,
  classificationBadgeStyle,
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
  const accentColor = accent ?? "#22D3EE";
  return (
    <div className="flex items-center gap-3 rounded-lg border border-slate-700/30 bg-slate-900/40 px-4 py-3">
      <div
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
        style={{ backgroundColor: `${accentColor}1a` }}
      >
        <Icon className="h-4 w-4" style={{ color: accentColor }} />
      </div>
      <div>
        <p
          className="font-mono text-lg font-semibold leading-tight"
          style={{ color: accentColor }}
        >
          {typeof value === "number" ? value.toLocaleString() : value}
        </p>
        <p className="text-xs text-slate-500">{label}</p>
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
    <div className="edb-cat-strip w-full">
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
  const badgeStyle = classificationBadgeStyle(entry.classificationLevel);

  return (
    <Link
      to={`/evidence-db/${encodeURIComponent(entry.variantSlug)}`}
      className="edb-card edb-card-clickable group block rounded-xl overflow-hidden"
    >
      {/* Pathogenicity accent bar with glow */}
      <div
        className="h-0.5 w-full"
        style={{
          backgroundColor: borderColor,
          boxShadow: `0 0 8px ${borderColor}`,
        }}
      />

      <div className="p-4">
        {/* Gene + Variant header */}
        <div className="mb-2">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h3 className="font-mono text-base font-semibold text-slate-100 truncate group-hover:text-cyan-300 transition-colors">
                {entry.gene || "Unknown Gene"}
              </h3>
              <p className="font-mono text-sm text-slate-400 truncate mt-0.5">
                {entry.variant || "Unknown Variant"}
              </p>
            </div>
            <span
              className="shrink-0 inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium font-mono"
              style={badgeStyle}
            >
              {classificationShortLabel(entry.classificationLevel)}
            </span>
          </div>
        </div>

        {/* Disease + Classification */}
        <div className="mb-3 space-y-0.5">
          {entry.disease && (
            <p className="text-sm text-slate-300 truncate">{entry.disease}</p>
          )}
          <p className="text-xs text-slate-600">
            {entry.classification || "No classification"}
          </p>
        </div>

        {/* Stats row */}
        <div className="mb-3 flex items-center gap-4 text-xs text-slate-500">
          <span className="flex items-center gap-1">
            <FileText className="h-3.5 w-3.5" />
            <span className="font-medium text-slate-300">
              {entry.evidenceGroupCount}
            </span>
            evidence
          </span>
          <span className="flex items-center gap-1">
            <BookOpen className="h-3.5 w-3.5" />
            <span className="font-medium text-slate-300">
              {entry.literatureCount}
            </span>
            refs
          </span>
          <span className="flex items-center gap-1">
            <TrendingUp className="h-3.5 w-3.5" />
            <span className="font-medium text-slate-300">
              {Math.round(entry.avgConfidence * 100)}%
            </span>
            conf.
          </span>
        </div>

        {/* Category distribution mini-bar */}
        <CategoryDistributionBar distribution={entry.categoryDistribution} />
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
    <div className="flex flex-wrap items-center gap-1.5">
      <button
        type="button"
        onClick={() => onChange(undefined)}
        className={cn(
          "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
          !value
            ? "border-slate-500 bg-slate-200 text-slate-900"
            : "border-slate-700 bg-slate-900/40 text-slate-400 hover:border-slate-600",
        )}
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
            className={cn(
              "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
              isActive
                ? "border-transparent"
                : "border-slate-700 bg-slate-900/40 text-slate-400 hover:border-slate-600",
            )}
            style={
              isActive
                ? { backgroundColor: hex, color: "#0a0e17" }
                : undefined
            }
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
    isLoading,
    isFetching,
    error,
    filters,
    updateFilter,
    setPage,
    clearFilters,
  } = useVariantIndex();

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-6">
      {/* Hero Stats Section */}
      <section className="edb-surface rounded-2xl p-6">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
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
            accent="#22D3EE"
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
            accent="#22C55E"
          />
        </div>
      </section>

      {/* Search & Filter Bar */}
      <section className="edb-surface rounded-xl p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          {/* Text search */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              placeholder="Search by gene or variant..."
              value={filters.gene ?? filters.variant ?? ""}
              onChange={(e) => {
                const val = e.target.value;
                updateFilter("gene", val || undefined);
                if (val) updateFilter("variant", undefined);
              }}
              className="w-full rounded-lg border border-slate-700/50 bg-slate-900/50 py-2 pl-9 pr-3 text-sm text-slate-200 placeholder-slate-600 transition-colors focus:border-cyan-500/50 focus:bg-slate-900 focus:outline-none"
            />
            {(filters.gene || filters.variant) && (
              <button
                type="button"
                onClick={() => {
                  updateFilter("gene", undefined);
                  updateFilter("variant", undefined);
                }}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-slate-500 hover:text-slate-300"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {/* Disease filter */}
          <div className="relative sm:w-48">
            <input
              type="text"
              placeholder="Filter by disease..."
              value={filters.disease ?? ""}
              onChange={(e) =>
                updateFilter("disease", e.target.value || undefined)
              }
              className="w-full rounded-lg border border-slate-700/50 bg-slate-900/50 py-2 px-3 text-sm text-slate-200 placeholder-slate-600 transition-colors focus:border-cyan-500/50 focus:bg-slate-900 focus:outline-none"
            />
          </div>

          {/* Clear all */}
          {(filters.gene || filters.variant || filters.disease || filters.classification) && (
            <button
              type="button"
              onClick={clearFilters}
              className="shrink-0 rounded-lg border border-slate-700/50 px-3 py-2 text-xs font-medium text-slate-400 hover:bg-slate-800/50 transition-colors"
            >
              Clear all
            </button>
          )}
        </div>

        {/* Classification filter pills */}
        <div className="mt-3 pt-3 border-t border-slate-800/50">
          <ClassificationFilter
            value={filters.classification}
            onChange={(val) => updateFilter("classification", val)}
          />
        </div>
      </section>

      {/* Results */}
      {error ? (
        <div className="flex items-center gap-3 rounded-xl border border-red-500/30 bg-red-950/30 p-4 text-sm text-red-300">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <span>Failed to load variant data. Please try again.</span>
        </div>
      ) : isLoading ? (
        <div className="flex items-center justify-center py-20">
          <Spinner className="h-6 w-6 text-cyan-400" />
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-700 py-20 text-center">
          <Dna className="h-10 w-10 text-slate-700 mb-3" />
          <p className="text-sm font-medium text-slate-400">
            No variants found
          </p>
          <p className="text-xs text-slate-600 mt-1">
            Try adjusting your search filters
          </p>
        </div>
      ) : (
        <>
          {/* Result count */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-500">
              <span className="font-medium text-slate-300">{total}</span>{" "}
              variant{total !== 1 ? "s" : ""} found
              {isFetching && (
                <span className="ml-2 inline-block">
                  <Spinner className="h-3 w-3 text-cyan-400 inline" />
                </span>
              )}
            </p>
            <p className="text-xs text-slate-600">
              Page {page} of {totalPages || 1}
            </p>
          </div>

          {/* Variant Grid */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
            <div className="flex items-center justify-center gap-2 pt-2">
              <button
                type="button"
                onClick={() => setPage(page - 1)}
                disabled={page <= 1}
                className={cn(
                  "flex h-9 w-9 items-center justify-center rounded-lg border text-sm transition-colors",
                  page <= 1
                    ? "cursor-not-allowed border-slate-800/50 text-slate-700"
                    : "border-slate-700/50 text-slate-400 hover:bg-slate-800/50",
                )}
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                const pageNum = i + 1;
                return (
                  <button
                    key={pageNum}
                    type="button"
                    onClick={() => setPage(pageNum)}
                    className={cn(
                      "flex h-9 w-9 items-center justify-center rounded-lg border text-sm font-medium transition-colors",
                      pageNum === page
                        ? "border-cyan-500 bg-cyan-500 text-slate-900"
                        : "border-slate-700/50 text-slate-400 hover:bg-slate-800/50",
                    )}
                  >
                    {pageNum}
                  </button>
                );
              })}
              {totalPages > 7 && (
                <span className="px-1 text-slate-600">…</span>
              )}
              <button
                type="button"
                onClick={() => setPage(page + 1)}
                disabled={page >= totalPages}
                className={cn(
                  "flex h-9 w-9 items-center justify-center rounded-lg border text-sm transition-colors",
                  page >= totalPages
                    ? "cursor-not-allowed border-slate-800/50 text-slate-700"
                    : "border-slate-700/50 text-slate-400 hover:bg-slate-800/50",
                )}
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
