import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  BookOpen,
  Languages,
  ExternalLink,
  AlertCircle,
  ChevronRight,
  Eye,
  EyeOff,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { Spinner } from "@/components/ui/Spinner";
import { useEvidenceGroupDetail } from "@/features/evidence-search/hooks/useEvidenceGroupDetail";
import type { EvidenceGroupItem } from "@/features/evidence-search/types/evidenceSearch";
import {
  CATEGORY_COLORS,
  EVIDENCE_CATEGORIES,
  buildEvidenceDocument,
  hasTranslatedDocumentText,
  countEvidenceCategories,
} from "@/features/evidence-search/utils/evidenceDocument";
import { categoryLabel } from "@/features/evidence-search/utils/categoryStyles";
import type {
  EvidenceDocument,
  EvidenceDocumentParagraph,
} from "@/features/evidence-search/utils/evidenceDocument";
import { useVariantDetail } from "../hooks/useVariantDetail";

/* ── Highlighted Text Renderer ──────────────────────────── */

function HighlightedText({ paragraph }: { paragraph: EvidenceDocumentParagraph }) {
  const sorted = useMemo(
    () => [...paragraph.highlights].sort((a, b) => a.start - b.start),
    [paragraph.highlights],
  );

  if (sorted.length === 0) {
    return (
      <p className="text-sm leading-relaxed text-slate-300 whitespace-pre-wrap">
        {paragraph.text}
      </p>
    );
  }

  const segments: React.ReactNode[] = [];
  let cursor = 0;

  for (const hl of sorted) {
    const start = Math.max(0, Math.min(hl.start, paragraph.text.length));
    const end = Math.max(start, Math.min(hl.end, paragraph.text.length));
    if (start > end) continue;

    if (cursor < start) {
      segments.push(
        <span key={`plain-${cursor}`}>
          {paragraph.text.slice(cursor, start)}
        </span>,
      );
    }

    const hex = hl.category ? CATEGORY_COLORS[hl.category]?.hex ?? "#64748B" : "#64748B";
    segments.push(
      <mark
        key={`hl-${hl.evidenceId}-${start}`}
        className={cn(
          "rounded-sm px-0.5 cursor-help transition-all",
          hl.selected && "ring-2 ring-offset-1 ring-offset-[#0a0e17] ring-cyan-400",
        )}
        style={{
          backgroundColor: `${hex}25`,
          color: hex,
          borderBottom: `2px solid ${hex}`,
        }}
        title={`${hl.label} (${hl.fieldId})`}
      >
        {paragraph.text.slice(start, end)}
      </mark>,
    );
    cursor = end;
  }

  if (cursor < paragraph.text.length) {
    segments.push(
      <span key={`tail-${cursor}`}>{paragraph.text.slice(cursor)}</span>,
    );
  }

  return (
    <p className="text-sm leading-relaxed text-slate-300 whitespace-pre-wrap">
      {segments}
    </p>
  );
}

/* ── Document Reader Panel ──────────────────────────────── */

function DocumentReader({
  title,
  track,
  document,
  accentColor,
}: {
  title: string;
  track: "original" | "translated";
  document: EvidenceDocument;
  accentColor: string;
}) {
  return (
    <div className="flex flex-col rounded-xl border border-slate-800/50 bg-slate-900/30 overflow-hidden">
      <div
        className="flex items-center gap-2 px-4 py-2.5 border-b border-slate-800/50"
        style={{ backgroundColor: `${accentColor}0d` }}
      >
        <Languages className="h-4 w-4" style={{ color: accentColor }} />
        <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
        <span className="ml-auto text-[11px] capitalize text-slate-600">
          {track} track
        </span>
      </div>
      <div className="edb-scroll max-h-[600px] overflow-y-auto p-4 space-y-4">
        {document.paragraphs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <BookOpen className="h-8 w-8 text-slate-700 mb-2" />
            <p className="text-sm text-slate-600">
              No {track} text available
            </p>
          </div>
        ) : (
          document.paragraphs.map((para) => (
            <div key={para.id} className="relative">
              {para.page && (
                <span className="absolute -left-2 top-0 text-[10px] text-slate-700 font-mono">
                  p.{para.page}
                </span>
              )}
              <HighlightedText paragraph={para} />
            </div>
          ))
        )}
      </div>
    </div>
  );
}

/* ── Category Toggle ────────────────────────────────────── */

function CategoryToggle({
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
      className={cn(
        "flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-xs font-medium cursor-pointer transition-all",
        checked
          ? "border-slate-700/50 bg-slate-900/50"
          : "border-transparent bg-slate-900/20 opacity-40",
      )}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="sr-only"
      />
      <div
        className={cn(
          "flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors",
          checked ? "border-transparent text-slate-900" : "border-slate-600 bg-transparent",
        )}
        style={checked ? { backgroundColor: hex } : undefined}
      >
        {checked && (
          <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none">
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
      <span className="text-slate-300">
        <span className="font-mono">{category}</span>: {categoryLabel(category)}
      </span>
      <span className="ml-auto font-mono text-slate-600">{count}</span>
    </label>
  );
}

/* ── Evidence Navigator ─────────────────────────────────── */

function EvidenceNavigator({
  items,
  selectedId,
  onSelect,
}: {
  items: EvidenceGroupItem[];
  selectedId?: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="space-y-1">
      {items.map((item) => {
        const cat =
          item.category ??
          (item.field_id.includes(".") ? item.field_id.split(".")[0] : null);
        const hex = cat ? CATEGORY_COLORS[cat]?.hex ?? "#64748B" : "#64748B";
        const isSelected = item.canonical_evidence_id === selectedId;
        const confidence = item.confidence ?? 0;
        const confColor = confidence >= 0.7 ? "#22C55E" : confidence >= 0.4 ? "#FFB323" : "#FF4D6D";

        return (
          <button
            key={item.canonical_evidence_id}
            type="button"
            onClick={() => onSelect(item.canonical_evidence_id)}
            className={cn(
              "flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs transition-all",
              isSelected
                ? "bg-cyan-500/10 border border-cyan-500/30"
                : "hover:bg-slate-800/50 border border-transparent",
            )}
          >
            <div
              className="h-2 w-2 shrink-0 rounded-full"
              style={{ backgroundColor: hex, boxShadow: isSelected ? `0 0 6px ${hex}` : undefined }}
            />
            <span className="truncate flex-1 text-slate-300 font-medium">
              {item.field_name ?? item.field_id}
            </span>
            <span className="font-mono text-[10px]" style={{ color: confColor }}>
              {Math.round(confidence * 100)}%
            </span>
          </button>
        );
      })}
    </div>
  );
}

/* ── Active Evidence Card ───────────────────────────────── */

function ActiveEvidenceCard({ item }: { item: EvidenceGroupItem }) {
  const cat =
    item.category ??
    (item.field_id.includes(".") ? item.field_id.split(".")[0] : null);
  const hex = cat ? CATEGORY_COLORS[cat]?.hex ?? "#64748B" : "#64748B";
  const confidence = item.confidence ?? 0;
  const confColor = confidence >= 0.7 ? "#22C55E" : confidence >= 0.4 ? "#FFB323" : "#FF4D6D";

  return (
    <div
      className="rounded-xl border border-slate-800/50 bg-slate-900/40 overflow-hidden"
      style={{ borderLeftColor: hex, borderLeftWidth: 3 }}
    >
      <div className="p-4">
        <div className="flex items-start justify-between gap-2 mb-2">
          <div>
            <p className="text-sm font-semibold text-slate-100">
              {item.field_name ?? item.field_id}
            </p>
            <p className="text-[11px] text-slate-600 font-mono mt-0.5">
              {item.field_id}
            </p>
          </div>
          {cat && (
            <span
              className="inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-medium"
              style={{
                backgroundColor: `${hex}1a`,
                borderColor: `${hex}40`,
                color: hex,
              }}
            >
              <span className="font-mono">{cat}</span>: {categoryLabel(cat)}
            </span>
          )}
        </div>

        {item.value && (
          <div className="rounded-lg bg-slate-950/50 p-3 mb-2">
            <p className="text-sm text-slate-300 leading-relaxed">
              {typeof item.value === "string"
                ? item.value
                : JSON.stringify(item.value, null, 2)}
            </p>
          </div>
        )}

        <div className="flex items-center gap-3 text-[11px] text-slate-600">
          <span className="font-medium" style={{ color: confColor }}>
            {Math.round(confidence * 100)}% confidence
          </span>
          <span>·</span>
          <span className="capitalize">{item.track ?? "original"}</span>
          {item.page && (
            <>
              <span>·</span>
              <span>Page {item.page}</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Main View ──────────────────────────────────────────── */

export function BilingualEvidenceView({
  variantSlug,
  sourceDocumentId,
}: {
  variantSlug: string;
  sourceDocumentId: string;
}) {
  const [enabledCategories, setEnabledCategories] = useState<Set<string>>(
    () => new Set(EVIDENCE_CATEGORIES),
  );
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<
    string | undefined
  >(undefined);

  const { detail: variantDetail, isLoading: isVariantLoading } =
    useVariantDetail(variantSlug);

  const groupId = useMemo(() => {
    if (!variantDetail) return null;
    const group = variantDetail.evidenceGroups.find(
      (g) => g.source_document_id === sourceDocumentId,
    );
    return group?.group_id ?? variantDetail.entry.groupIds[0] ?? null;
  }, [variantDetail, sourceDocumentId]);

  const {
    detail: groupDetail,
    isLoading: isGroupLoading,
    error,
  } = useEvidenceGroupDetail(groupId ?? "");

  const isLoading = isVariantLoading || isGroupLoading;

  const originalDoc = useMemo(
    () =>
      groupDetail
        ? buildEvidenceDocument(
            groupDetail,
            "original",
            undefined,
            selectedEvidenceId,
            enabledCategories,
          )
        : null,
    [groupDetail, selectedEvidenceId, enabledCategories],
  );

  const translatedDoc = useMemo(
    () =>
      groupDetail
        ? buildEvidenceDocument(
            groupDetail,
            "translated",
            undefined,
            selectedEvidenceId,
            enabledCategories,
          )
        : null,
    [groupDetail, selectedEvidenceId, enabledCategories],
  );

  const hasTranslation = groupDetail
    ? hasTranslatedDocumentText(groupDetail)
    : false;

  const categoryCounts = useMemo(
    () => (groupDetail ? countEvidenceCategories(groupDetail.items) : {}),
    [groupDetail],
  );

  const toggleCategory = (cat: string) => {
    setEnabledCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) {
        next.delete(cat);
      } else {
        next.add(cat);
      }
      return next;
    });
  };

  const toggleAllCategories = (on: boolean) => {
    setEnabledCategories(on ? new Set(EVIDENCE_CATEGORIES) : new Set());
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-6 w-6 text-cyan-400" />
      </div>
    );
  }

  if (error || !groupDetail) {
    return (
      <div className="space-y-4">
        <Link
          to={`/evidence-db/${encodeURIComponent(variantSlug)}`}
          className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to variant detail
        </Link>
        <div className="flex items-center gap-3 rounded-xl border border-red-500/30 bg-red-950/30 p-4 text-sm text-red-300">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <span>Failed to load evidence data for this literature.</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 text-sm text-slate-600">
        <Link
          to="/evidence-db"
          className="hover:text-slate-300 transition-colors"
        >
          Evidence DB
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <Link
          to={`/evidence-db/${encodeURIComponent(variantSlug)}`}
          className="font-mono hover:text-slate-300 transition-colors"
        >
          {variantSlug.split(":").slice(0, 2).join(":")}
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="text-slate-400 truncate max-w-[300px]">
          {groupDetail.title ?? "Literature"}
        </span>
      </nav>

      {/* Literature Header */}
      <section className="edb-surface rounded-xl p-5">
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-amber-500/10 text-amber-400">
            <BookOpen className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="font-display text-lg font-medium text-slate-100 leading-snug">
              {groupDetail.title ?? "Untitled Document"}
            </h1>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
              {groupDetail.pmid && (
                <a
                  href={`https://pubmed.ncbi.nlm.nih.gov/${groupDetail.pmid}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 font-mono text-cyan-400 hover:text-cyan-300"
                >
                  PMID:{groupDetail.pmid}
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
              {groupDetail.doi && (
                <a
                  href={`https://doi.org/${groupDetail.doi}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 font-mono text-cyan-400 hover:text-cyan-300"
                >
                  DOI:{groupDetail.doi.slice(0, 30)}
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
              <span>{groupDetail.item_count} evidence fields</span>
              {groupDetail.avg_confidence != null && (
                <span>
                  {Math.round(groupDetail.avg_confidence * 100)}% confidence
                </span>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Main: Bilingual comparison layout */}
      <div className="grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
        {/* Sidebar: controls + navigator */}
        <aside className="space-y-4">
          {/* Category toggles */}
          <div className="edb-card rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Evidence Layers
              </h3>
              <div className="flex gap-1">
                <button
                  type="button"
                  onClick={() => toggleAllCategories(true)}
                  className="rounded px-1.5 py-0.5 text-[10px] text-slate-600 hover:text-slate-300 hover:bg-slate-800/50"
                  title="Show all"
                >
                  <Eye className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => toggleAllCategories(false)}
                  className="rounded px-1.5 py-0.5 text-[10px] text-slate-600 hover:text-slate-300 hover:bg-slate-800/50"
                  title="Hide all"
                >
                  <EyeOff className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
            <div className="space-y-1.5">
              {EVIDENCE_CATEGORIES.map((cat) => (
                <CategoryToggle
                  key={cat}
                  category={cat}
                  count={categoryCounts[cat] ?? 0}
                  checked={enabledCategories.has(cat)}
                  onChange={() => toggleCategory(cat)}
                />
              ))}
            </div>
          </div>

          {/* Evidence navigator */}
          <div className="edb-card rounded-xl p-4">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
              Evidence Fields
            </h3>
            <div className="edb-scroll max-h-[400px] overflow-y-auto">
              <EvidenceNavigator
                items={groupDetail.items}
                selectedId={selectedEvidenceId}
                onSelect={setSelectedEvidenceId}
              />
            </div>
          </div>
        </aside>

        {/* Main: bilingual document readers */}
        <div className="space-y-4">
          {/* Active evidence card */}
          {selectedEvidenceId && (
            <ActiveEvidenceCard
              item={
                groupDetail.items.find(
                  (i) => i.canonical_evidence_id === selectedEvidenceId,
                ) ?? groupDetail.items[0]
              }
            />
          )}

          {/* Bilingual panels */}
          <div
            className={cn(
              "grid gap-4",
              hasTranslation ? "lg:grid-cols-2" : "lg:grid-cols-1",
            )}
          >
            <DocumentReader
              title="Original Text"
              track="original"
              document={originalDoc ?? { track: "original", paragraphs: [] }}
              accentColor="#3B82F6"
            />
            {hasTranslation && (
              <DocumentReader
                title="Translated Text (Chinese)"
                track="translated"
                document={
                  translatedDoc ?? { track: "translated", paragraphs: [] }
                }
                accentColor="#8B5CF6"
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
