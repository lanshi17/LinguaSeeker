import { Link } from "react-router-dom";
import {
  ArrowLeft,
  BookOpen,
  Stethoscope,
  Layers3,
  AlertCircle,
  ChevronRight,
} from "lucide-react";
import { Spinner } from "@/components/ui/Spinner";
import { useVariantDetail } from "../hooks/useVariantDetail";
import type { LiteratureReference } from "../types/variantDb";
import type { EvidenceGroupItem } from "@/features/evidence-search/types/evidenceSearch";
import {
  classificationColor,
  classificationBadgeStyle,
  classificationLabel,
} from "../utils/pathogenicity";
import { categoryLabel } from "@/features/evidence-search/utils/categoryStyles";
import { CATEGORY_COLORS } from "@/features/evidence-search/utils/evidenceDocument";

/* ── Confidence Ring ────────────────────────────────────── */

function ConfidenceRing({ value, size = 56 }: { value: number; size?: number }) {
  const pct = Math.round(value * 100);
  const ringColor = pct >= 70 ? "#22C55E" : pct >= 40 ? "#FFB323" : "#FF4D6D";
  return (
    <div
      className="edb-ring flex items-center justify-center rounded-full"
      style={
        {
          width: size,
          height: size,
          "--ring-value": pct,
          color: ringColor,
        } as React.CSSProperties
      }
    >
      <div
        className="flex items-center justify-center rounded-full bg-[#0a0e17]"
        style={{ width: size - 8, height: size - 8 }}
      >
        <span className="font-mono text-xs font-semibold text-slate-200">
          {pct}%
        </span>
      </div>
    </div>
  );
}

/* ── Evidence Item Card ─────────────────────────────────── */

function EvidenceItemCard({ item }: { item: EvidenceGroupItem }) {
  const cat = item.category ?? (item.field_id.includes(".") ? item.field_id.split(".")[0] : null);
  const catHex = cat ? CATEGORY_COLORS[cat]?.hex ?? "#64748B" : "#64748B";
  const confidence = item.confidence ?? 0;
  const confColor = confidence >= 0.7 ? "#22C55E" : confidence >= 0.4 ? "#FFB323" : "#FF4D6D";

  return (
    <div className="group flex items-start gap-3 rounded-lg border border-slate-800/40 bg-slate-900/30 p-3 transition-colors hover:border-slate-700/60">
      {/* Category accent */}
      <div
        className="mt-0.5 h-8 w-1 shrink-0 rounded-full"
        style={{ backgroundColor: catHex, boxShadow: `0 0 6px ${catHex}60` }}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-sm font-medium text-slate-200 leading-snug">
              {item.field_name ?? item.field_id}
            </p>
            {item.value && (
              <p className="mt-0.5 text-sm text-slate-400 leading-relaxed line-clamp-2">
                {typeof item.value === "string"
                  ? item.value
                  : JSON.stringify(item.value)}
              </p>
            )}
          </div>
          {cat && (
            <span
              className="shrink-0 inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-medium font-mono"
              style={{
                backgroundColor: `${catHex}1a`,
                borderColor: `${catHex}40`,
                color: catHex,
              }}
            >
              {cat}
            </span>
          )}
        </div>
        <div className="mt-1.5 flex items-center gap-3 text-[11px] text-slate-600">
          <span className="font-mono">{item.field_id}</span>
          <span>·</span>
          <span className="font-medium" style={{ color: confColor }}>
            {Math.round(confidence * 100)}% confidence
          </span>
          {item.track && (
            <>
              <span>·</span>
              <span className="capitalize">{item.track}</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Evidence Category Panel ────────────────────────────── */

function EvidenceCategoryPanel({
  items,
  category,
}: {
  items: EvidenceGroupItem[];
  category: string;
}) {
  const hex = CATEGORY_COLORS[category]?.hex ?? "#64748B";
  const label = categoryLabel(category);
  const catItems = items.filter((item) => {
    const itemCat = item.category ?? (item.field_id.includes(".") ? item.field_id.split(".")[0] : null);
    return itemCat === category;
  });

  if (catItems.length === 0) return null;

  return (
    <div className="edb-card rounded-xl overflow-hidden">
      {/* Category header */}
      <div
        className="flex items-center gap-2.5 px-4 py-2.5 border-b border-slate-800/40"
        style={{ backgroundColor: `${hex}0d` }}
      >
        <div
          className="h-2.5 w-2.5 rounded-full"
          style={{ backgroundColor: hex, boxShadow: `0 0 6px ${hex}80` }}
        />
        <h3 className="text-sm font-semibold text-slate-200">
          <span className="font-mono">{category}</span>: {label}
        </h3>
        <span className="ml-auto font-mono text-xs text-slate-600">
          {catItems.length} field{catItems.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Items */}
      <div className="p-3 space-y-2">
        {catItems.map((item) => (
          <EvidenceItemCard
            key={item.canonical_evidence_id}
            item={item}
          />
        ))}
      </div>
    </div>
  );
}

/* ── Literature Reference Card ──────────────────────────── */

function LiteratureReferenceCard({
  reference,
  variantSlug,
}: {
  reference: LiteratureReference;
  variantSlug: string;
}) {
  const confidence = Math.round(reference.avgConfidence * 100);
  const confColor = confidence >= 70 ? "#22C55E" : confidence >= 40 ? "#FFB323" : "#FF4D6D";

  return (
    <Link
      to={`/evidence-db/${encodeURIComponent(variantSlug)}/${encodeURIComponent(reference.sourceDocumentId)}`}
      className="group flex items-start gap-3 rounded-lg border border-slate-800/40 bg-slate-900/30 p-3 transition-all hover:border-cyan-500/30 hover:bg-slate-800/30"
    >
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-amber-500/10 text-amber-400">
        <BookOpen className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-slate-200 leading-snug line-clamp-2 group-hover:text-cyan-300 transition-colors">
          {reference.title}
        </p>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-slate-600">
          {reference.pmid && (
            <span className="font-mono">PMID:{reference.pmid}</span>
          )}
          {reference.doi && (
            <span className="font-mono">DOI:{reference.doi.slice(0, 20)}…</span>
          )}
          <span>{reference.fieldCount} fields</span>
          <span className="font-medium" style={{ color: confColor }}>
            {confidence}%
          </span>
        </div>
        <div className="mt-1.5 flex flex-wrap gap-1">
          {reference.categories.map((cat) => {
            const hex = CATEGORY_COLORS[cat]?.hex ?? "#64748B";
            return (
              <span
                key={cat}
                className="inline-flex items-center rounded border px-1 py-0.5 text-[10px] font-medium font-mono"
                style={{
                  backgroundColor: `${hex}1a`,
                  borderColor: `${hex}40`,
                  color: hex,
                }}
              >
                {cat}
              </span>
            );
          })}
        </div>
      </div>
      <ChevronRight className="h-4 w-4 shrink-0 text-slate-700 group-hover:text-cyan-400 transition-colors mt-1" />
    </Link>
  );
}

/* ── Main View ──────────────────────────────────────────── */

export function VariantDetailView({
  variantSlug,
}: {
  variantSlug: string;
}) {
  const { detail, isLoading, error } = useVariantDetail(variantSlug);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-6 w-6 text-cyan-400" />
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="space-y-4">
        <Link
          to="/evidence-db"
          className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Evidence Database
        </Link>
        <div className="flex items-center gap-3 rounded-xl border border-red-500/30 bg-red-950/30 p-4 text-sm text-red-300">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <span>Variant not found or failed to load.</span>
        </div>
      </div>
    );
  }

  const { entry, literature, allItems } = detail;
  const borderColor = classificationColor(entry.classificationLevel);
  const badgeStyle = classificationBadgeStyle(entry.classificationLevel);

  const categoriesWithItems = [
    ...new Set(
      allItems.map(
        (item) =>
          item.category ??
          (item.field_id.includes(".") ? item.field_id.split(".")[0] : null),
      ),
    ),
  ]
    .filter(Boolean)
    .sort() as string[];

  return (
    <div className="space-y-6">
      {/* Back navigation */}
      <Link
        to="/evidence-db"
        className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Evidence Database
      </Link>

      {/* Variant Hero */}
      <section
        className="edb-surface rounded-2xl overflow-hidden"
        style={{ borderLeftColor: borderColor, borderLeftWidth: 4 }}
      >
        <div className="p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            {/* Main info */}
            <div>
              <div className="flex items-center gap-3 mb-2">
                <h1 className="font-mono text-xl font-bold text-slate-100">
                  {entry.gene}
                </h1>
                <span
                  className="inline-flex items-center rounded-md border px-2.5 py-1 text-xs font-semibold"
                  style={badgeStyle}
                >
                  {classificationLabel(entry.classificationLevel)}
                </span>
              </div>
              <p className="font-mono text-lg text-slate-300 mb-1">
                {entry.variant}
              </p>
              {entry.disease && (
                <p className="text-sm text-slate-400">
                  <Stethoscope className="inline h-4 w-4 mr-1 -mt-0.5 text-slate-500" />
                  {entry.disease}
                </p>
              )}
              {entry.classification && (
                <p className="text-xs text-slate-600 mt-1">
                  {entry.classification}
                </p>
              )}
            </div>

            {/* Stats */}
            <div className="flex items-center gap-4">
              <ConfidenceRing value={entry.avgConfidence} size={56} />
              <div className="grid grid-cols-2 gap-x-6 gap-y-1">
                <div>
                  <p className="font-mono text-lg font-semibold text-slate-100">
                    {entry.evidenceGroupCount}
                  </p>
                  <p className="text-xs text-slate-500">Evidence groups</p>
                </div>
                <div>
                  <p className="font-mono text-lg font-semibold text-slate-100">
                    {entry.literatureCount}
                  </p>
                  <p className="text-xs text-slate-500">Literature</p>
                </div>
                <div>
                  <p className="font-mono text-lg font-semibold text-slate-100">
                    {entry.fieldCount}
                  </p>
                  <p className="text-xs text-slate-500">Total fields</p>
                </div>
                <div>
                  <p className="font-mono text-lg font-semibold text-slate-100">
                    {categoriesWithItems.length}
                  </p>
                  <p className="text-xs text-slate-500">Categories</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Two-column layout: Evidence + Literature */}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        {/* Main: Evidence by Category */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-lg font-medium text-slate-200">
              Evidence Fields
            </h2>
            <span className="text-sm text-slate-500">
              {allItems.length} field{allItems.length !== 1 ? "s" : ""} across{" "}
              {categoriesWithItems.length} categor
              {categoriesWithItems.length !== 1 ? "ies" : "y"}
            </span>
          </div>

          {categoriesWithItems.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-700 py-12 text-center">
              <Layers3 className="h-8 w-8 text-slate-700 mx-auto mb-2" />
              <p className="text-sm text-slate-500">
                No evidence fields found
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {categoriesWithItems.map((cat) => (
                <EvidenceCategoryPanel
                  key={cat}
                  items={allItems}
                  category={cat}
                />
              ))}
            </div>
          )}
        </div>

        {/* Sidebar: Literature References */}
        <aside className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-lg font-medium text-slate-200">
              References
            </h2>
            <span className="text-sm text-slate-500">
              {literature.length} source{literature.length !== 1 ? "s" : ""}
            </span>
          </div>

          {literature.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-700 py-12 text-center">
              <BookOpen className="h-8 w-8 text-slate-700 mx-auto mb-2" />
              <p className="text-sm text-slate-500">No references found</p>
            </div>
          ) : (
            <div className="space-y-2">
              {literature.map((ref) => (
                <LiteratureReferenceCard
                  key={ref.sourceDocumentId}
                  reference={ref}
                  variantSlug={variantSlug}
                />
              ))}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
