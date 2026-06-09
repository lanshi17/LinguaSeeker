"use client";

import { useMemo, useState, type ReactNode } from "react";
import {
  ArrowLeft,
  BookOpen,
  Columns2,
  FileText,
  Highlighter,
  Languages,
  ListChecks,
  Percent,
  Search,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { cn } from "@/lib/utils/cn";
import { useEvidenceGroupDetail } from "../hooks/useEvidenceGroupDetail";
import type {
  EvidenceGroupDetailResponse,
  EvidenceGroupItem,
  EvidenceHighlightTone,
} from "../types/evidenceSearch";
import {
  buildEvidenceDocument,
  CATEGORY_COLORS,
  EVIDENCE_CATEGORIES,
  countEvidenceCategories,
  type EvidenceDocumentHighlight,
  type EvidenceDocumentParagraph,
} from "../utils/evidenceDocument";
import {
  buildBilingualCompareHref,
  findInitialEvidenceId,
} from "../utils/literatureRows";

type DetailViewMode = "overview" | "compare";

interface EvidenceDetailViewProps {
  groupId: string;
  initialEvidenceId?: string;
  initialView?: DetailViewMode;
}

const STATUS_VARIANT: Record<
  string,
  "default" | "success" | "warning" | "error" | "info"
> = {
  provisional: "default",
  approved: "success",
  corrected: "warning",
  rejected: "error",
};

const CATEGORY_LABELS: Record<string, string> = Object.fromEntries(
  Object.entries(CATEGORY_COLORS).map(([k, v]) => [k, v.label]),
);

/** Chip styles keyed by category letter, falling back to tone styles. */
function categoryChipStyle(category?: string | null): string {
  if (category && CATEGORY_COLORS[category]) {
    return CATEGORY_COLORS[category].chip;
  }
  return "border-gray-200 bg-gray-50 text-gray-700";
}

/** Mark/highlight styles keyed by category letter, falling back to neutral. */
function categoryMarkStyle(category?: string | null): string {
  if (category && CATEGORY_COLORS[category]) {
    return CATEGORY_COLORS[category].mark;
  }
  return "bg-gray-200 text-gray-950 ring-1 ring-gray-300";
}

const HIGHLIGHT_TONES: EvidenceHighlightTone[] = [
  "gene",
  "variant",
  "disease",
  "classification",
  "functional",
  "neutral",
];

function formatPercent(value?: number | null) {
  if (value == null) {
    return "\u2014";
  }
  return `${(value * 100).toFixed(0)}%`;
}

function categoryFromItem(item?: EvidenceGroupItem | null) {
  if (!item) {
    return null;
  }
  if (item.category) {
    return item.category;
  }
  return item.field_id.includes(".") ? item.field_id.split(".", 1)[0] : null;
}

function categoryLabel(category?: string | null) {
  if (!category) {
    return "Uncategorized";
  }
  return CATEGORY_LABELS[category] ?? category;
}

function itemLabel(item: EvidenceGroupItem) {
  return item.field_name ?? item.field_id;
}

function countEntries(record: Record<string, number>) {
  return Object.entries(record).sort(([a], [b]) => a.localeCompare(b));
}

function selectedTraceFor(
  detail: EvidenceGroupDetailResponse,
  selectedEvidenceId: string | null,
) {
  if (!selectedEvidenceId) {
    return detail.traces[0] ?? null;
  }

  const selectedItem = detail.items.find(
    (item) => item.canonical_evidence_id === selectedEvidenceId,
  );
  return (
    detail.traces.find(
      (trace) => trace.canonical_evidence_id === selectedEvidenceId,
    ) ??
    detail.traces.find((trace) => trace.field_id === selectedItem?.field_id) ??
    detail.traces[0] ??
    null
  );
}

function detailTitle(detail: EvidenceGroupDetailResponse) {
  const title = detail.title?.trim();
  return title || "Untitled literature record";
}

function MetadataToken({
  label,
  value,
}: {
  label: string;
  value?: string | null;
}) {
  return (
    <span className="inline-flex max-w-full items-center gap-1.5 rounded-md border border-primary-100 bg-white px-2.5 py-1 text-xs text-primary-900">
      <span className="font-semibold">{label}</span>
      <span className="truncate font-mono">{value?.trim() || "\u2014"}</span>
    </span>
  );
}

function EvidenceTonePill({ item }: { item: EvidenceGroupItem }) {
  const cat = categoryFromItem(item);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium",
        categoryChipStyle(cat),
      )}
    >
      {cat && CATEGORY_COLORS[cat] && (
        <span
          className="inline-block h-2 w-2 shrink-0 rounded-full"
          style={{ backgroundColor: CATEGORY_COLORS[cat].hex }}
          aria-hidden="true"
        />
      )}
      {categoryLabel(cat)}
    </span>
  );
}

function EvidenceItemSummary({
  groupId,
  item,
}: {
  groupId: string;
  item: EvidenceGroupItem;
}) {
  return (
    <article className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <EvidenceTonePill item={item} />
            <Badge variant={STATUS_VARIANT[item.review_status] ?? "default"}>
              {item.review_status}
            </Badge>
          </div>
          <h3 className="mt-3 text-sm font-semibold text-gray-900">
            {itemLabel(item)}
          </h3>
          <p className="mt-1 font-mono text-xs text-gray-500">
            {item.field_id}
          </p>
        </div>
        <Link
          href={buildBilingualCompareHref(groupId, item.canonical_evidence_id)}
          className="inline-flex h-10 cursor-pointer items-center gap-2 rounded-md border border-primary-200 bg-primary-50 px-3 text-sm font-medium text-primary-800 transition-colors hover:bg-primary-100 focus-visible:ring-2 focus-visible:ring-primary-500"
        >
          <Columns2 className="h-4 w-4" />
          Compare full text
        </Link>
      </div>

      <p className="mt-4 line-clamp-3 text-sm leading-6 text-gray-700">
        {item.value ?? "\u2014"}
      </p>

      <div className="mt-4 grid grid-cols-2 gap-3 border-t border-gray-100 pt-3 text-xs text-gray-500 sm:grid-cols-3">
        <span>Confidence {formatPercent(item.confidence)}</span>
        <span>Track {item.track ?? "\u2014"}</span>
        <span>Page {item.page ?? "\u2014"}</span>
      </div>
    </article>
  );
}

function LiteratureOverview({
  detail,
  groupId,
}: {
  detail: EvidenceGroupDetailResponse;
  groupId: string;
}) {
  return (
    <div className="space-y-5">
      <Link
        href="/evidence"
        className="inline-flex items-center gap-2 text-sm font-medium text-gray-500 transition-colors hover:text-gray-900"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to literature
      </Link>

      <section className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-primary-100 bg-primary-50 px-5 py-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-primary-800">
                <BookOpen className="h-4 w-4" />
                Literature record
              </p>
              <h2 className="mt-2 max-w-4xl text-xl font-semibold leading-7 text-gray-950">
                {detailTitle(detail)}
              </h2>
              <div className="mt-3 flex max-w-4xl flex-wrap gap-2">
                <MetadataToken
                  label="UUID"
                  value={detail.source_document_id}
                />
                <MetadataToken label="PMID" value={detail.pmid} />
                <MetadataToken label="DOI" value={detail.doi} />
              </div>
            </div>
            <Badge variant={STATUS_VARIANT.approved}>Traceable</Badge>
          </div>
        </div>

        <div className="grid gap-0 md:grid-cols-4">
          {[
            ["Gene", detail.gene],
            ["Variant", detail.variant],
            ["Disease", detail.disease],
            ["Classification", detail.classification],
          ].map(([label, value]) => (
            <div
              key={label}
              className="border-b border-gray-100 px-5 py-4 md:border-b-0 md:border-r last:md:border-r-0"
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                {label}
              </p>
              <p className="mt-2 line-clamp-3 text-sm font-medium text-gray-900">
                {value ?? "\u2014"}
              </p>
            </div>
          ))}
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="space-y-5">
          <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
              <ListChecks className="h-4 w-4 text-primary-700" />
              Evidence coverage
            </h3>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-lg bg-gray-50 p-3">
                <p className="text-xs text-gray-500">Items</p>
                <p className="mt-1 text-2xl font-semibold text-gray-950">
                  {detail.item_count}
                </p>
              </div>
              <div className="rounded-lg bg-gray-50 p-3">
                <p className="text-xs text-gray-500">Confidence</p>
                <p className="mt-1 text-2xl font-semibold text-gray-950">
                  {formatPercent(detail.avg_confidence)}
                </p>
              </div>
              <div className="rounded-lg bg-gray-50 p-3">
                <p className="text-xs text-gray-500">Traces</p>
                <p className="mt-1 text-2xl font-semibold text-gray-950">
                  {detail.traces.length}
                </p>
              </div>
              <div className="rounded-lg bg-gray-50 p-3">
                <p className="text-xs text-gray-500">Fields</p>
                <p className="mt-1 text-2xl font-semibold text-gray-950">
                  {Object.keys(detail.distribution.by_field).length}
                </p>
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-gray-900">
              Evidence categories
            </h3>
            <div className="mt-4 flex flex-wrap gap-2">
              {countEntries(detail.distribution.by_category).map(
                ([key, count]) => (
                  <span
                    key={key}
                    className="rounded-md border border-gray-200 bg-gray-50 px-2.5 py-1.5 text-xs font-medium text-gray-700"
                  >
                    {categoryLabel(key)} · {count}
                  </span>
                ),
              )}
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-gray-900">
              Review status
            </h3>
            <div className="mt-4 flex flex-wrap gap-2">
              {countEntries(detail.distribution.by_status).map(
                ([key, count]) => (
                  <Badge key={key} variant={STATUS_VARIANT[key] ?? "default"}>
                    {key}: {count}
                  </Badge>
                ),
              )}
            </div>
          </section>
        </aside>

        <section className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-gray-950">
                Extracted evidence fields
              </h2>
              <p className="mt-1 text-sm text-gray-500">
                {detail.items.length} field-level evidence items
              </p>
            </div>
            {detail.items[0] && (
              <Link
                href={buildBilingualCompareHref(
                  groupId,
                  detail.items[0].canonical_evidence_id,
                )}
                className="inline-flex h-10 cursor-pointer items-center gap-2 rounded-md bg-primary-700 px-3 text-sm font-medium text-white transition-colors hover:bg-primary-800 focus-visible:ring-2 focus-visible:ring-primary-500"
              >
                <Languages className="h-4 w-4" />
                Full-text comparison
              </Link>
            )}
          </div>

          <div className="grid gap-3">
            {detail.items.map((item) => (
              <EvidenceItemSummary
                key={item.canonical_evidence_id}
                groupId={groupId}
                item={item}
              />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function normalizedHighlights(paragraph: EvidenceDocumentParagraph) {
  const highlights = [...paragraph.highlights].sort((a, b) => a.start - b.start);
  const normalized: EvidenceDocumentHighlight[] = [];
  let cursor = 0;

  for (const highlight of highlights) {
    const start = Math.max(cursor, Math.max(0, Math.min(highlight.start, paragraph.text.length)));
    const end = Math.max(start, Math.min(highlight.end, paragraph.text.length));
    if (end <= start) {
      continue;
    }
    normalized.push({ ...highlight, start, end });
    cursor = end;
  }

  return normalized;
}

function HighlightedParagraph({
  paragraph,
}: {
  paragraph: EvidenceDocumentParagraph;
}) {
  const highlights = normalizedHighlights(paragraph);
  const nodes: ReactNode[] = [];
  let cursor = 0;

  highlights.forEach((highlight, index) => {
    if (highlight.start > cursor) {
      nodes.push(paragraph.text.slice(cursor, highlight.start));
    }
    nodes.push(
      <mark
        key={`${highlight.evidenceId}-${highlight.start}-${index}`}
        className={cn(
          "rounded px-1 py-0.5 font-semibold",
          categoryMarkStyle(highlight.category),
          highlight.selected &&
            "outline outline-2 outline-offset-2 outline-primary-700",
        )}
        aria-label={`${categoryLabel(highlight.category)} evidence: ${highlight.label}`}
      >
        {paragraph.text.slice(highlight.start, highlight.end)}
      </mark>,
    );
    cursor = highlight.end;
  });

  if (cursor < paragraph.text.length) {
    nodes.push(paragraph.text.slice(cursor));
  }

  return (
    <div className="border-b border-gray-100 py-4 last:border-b-0">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-gray-500">
        <span className="rounded-md bg-gray-100 px-2 py-1 font-medium text-gray-700">
          {paragraph.highlights[0]?.label ?? "Document text"}
        </span>
        <span>Page {paragraph.page ?? "\u2014"}</span>
      </div>
      <p className="whitespace-pre-wrap text-sm leading-7 text-gray-800">
        {nodes.length > 0 ? nodes : paragraph.text}
      </p>
    </div>
  );
}

function EvidenceDocumentReader({
  title,
  paragraphs,
}: {
  title: string;
  paragraphs: EvidenceDocumentParagraph[];
}) {
  return (
    <section className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
      <div className="border-b border-gray-100 bg-gray-50 px-4 py-3">
        <h3 className="text-sm font-semibold text-gray-950">{title}</h3>
        <p className="mt-1 text-xs text-gray-500">
          {paragraphs.length} aligned paragraph{paragraphs.length !== 1 ? "s" : ""}
        </p>
      </div>
      <div className="max-h-[720px] overflow-y-auto px-4">
        {paragraphs.length > 0 ? (
          paragraphs.map((paragraph) => (
            <HighlightedParagraph key={paragraph.id} paragraph={paragraph} />
          ))
        ) : (
          <div className="px-2 py-10 text-center text-sm text-gray-500">
            No document text is available for this track.
          </div>
        )}
      </div>
    </section>
  );
}

function CategoryLayerToggle({
  checked,
  count,
  onChange,
  category,
}: {
  checked: boolean;
  count: number;
  onChange: () => void;
  category: string;
}) {
  const cat = CATEGORY_COLORS[category];
  return (
    <label
      className={cn(
        "flex min-h-11 cursor-pointer items-center justify-between gap-3 rounded-lg border px-3 py-2 transition-colors",
        checked
          ? "border-primary-200 bg-primary-50"
          : "border-gray-200 bg-white hover:bg-gray-50",
        count === 0 && "cursor-not-allowed opacity-50",
      )}
      style={
        checked && cat
          ? { borderColor: cat.hex + "40", backgroundColor: cat.hex + "10" }
          : undefined
      }
    >
      <input
        type="checkbox"
        checked={checked}
        disabled={count === 0}
        onChange={onChange}
        className="peer sr-only"
      />
      <span className="flex min-w-0 items-center gap-2">
        <span
          className="inline-block h-3 w-3 shrink-0 rounded-full"
          style={{ backgroundColor: cat?.hex ?? "#9CA3AF" }}
          aria-hidden="true"
        />
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium text-gray-900">
            {cat?.label ?? category}
          </span>
          <span className="text-xs text-gray-500">
            {count} item{count !== 1 ? "s" : ""}
          </span>
        </span>
      </span>
      <span
        className={cn(
          "relative h-6 w-11 shrink-0 rounded-full transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-primary-500 peer-focus-visible:ring-offset-2",
          checked ? "bg-primary-700" : "bg-gray-300",
        )}
        aria-hidden="true"
      >
        <span
          className={cn(
            "absolute left-1 top-1 h-4 w-4 rounded-full bg-white shadow-sm transition-transform",
            checked && "translate-x-5",
          )}
        />
      </span>
    </label>
  );
}

function BilingualComparison({
  detail,
  groupId,
  selectedEvidenceId,
  setSelectedEvidenceId,
}: {
  detail: EvidenceGroupDetailResponse;
  groupId: string;
  selectedEvidenceId: string | null;
  setSelectedEvidenceId: (value: string) => void;
}) {
  const [enabledTones] = useState<Set<EvidenceHighlightTone>>(
    () => new Set(HIGHLIGHT_TONES),
  );
  const [enabledCategories, setEnabledCategories] = useState<Set<string>>(
    () => new Set(EVIDENCE_CATEGORIES),
  );
  const selectedItem =
    detail.items.find(
      (item) => item.canonical_evidence_id === selectedEvidenceId,
    ) ??
    detail.items[0] ??
    null;
  const selectedTrace = selectedTraceFor(detail, selectedEvidenceId);
  const categoryCounts = useMemo(
    () => countEvidenceCategories(detail.items),
    [detail.items],
  );
  const originalDocument = useMemo(
    () =>
      buildEvidenceDocument(
        detail,
        "original",
        enabledTones,
        selectedEvidenceId,
        enabledCategories,
      ),
    [detail, enabledTones, selectedEvidenceId, enabledCategories],
  );
  const translatedDocument = useMemo(
    () =>
      buildEvidenceDocument(
        detail,
        "translated",
        enabledTones,
        selectedEvidenceId,
        enabledCategories,
      ),
    [detail, enabledTones, selectedEvidenceId, enabledCategories],
  );
  // Translate-track data availability ignores user-applied filters: a reader should still be shown
  // (and let its built-in empty-state render) when the API delivered translated content even if the
  // active category/toner set filters every span out. Collapsing the reader on every toggle caused
  // layout flicker for English originals with translated trace highlights.
  const showTranslatedDocument =
    Boolean(detail.translated_document_text?.trim()) ||
    detail.traces.some((trace) => Boolean(trace.translated?.text));

  const toggleCategory = (cat: string) => {
    setEnabledCategories((current) => {
      const next = new Set(current);
      if (next.has(cat)) {
        next.delete(cat);
      } else {
        next.add(cat);
      }
      return next;
    });
  };

  return (
    <div className="space-y-5">
      <Link
        href={`/evidence/detail?groupId=${encodeURIComponent(groupId)}`}
        className="inline-flex items-center gap-2 text-sm font-medium text-gray-500 transition-colors hover:text-gray-900"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to literature detail
      </Link>

      <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-primary-800">
              <Columns2 className="h-4 w-4" />
              Bilingual full-text document
            </p>
            <h2 className="mt-2 max-w-4xl text-xl font-semibold leading-7 text-gray-950">
              {detailTitle(detail)}
            </h2>
            <div className="mt-3 flex max-w-4xl flex-wrap gap-2">
              <MetadataToken label="UUID" value={detail.source_document_id} />
              <MetadataToken label="PMID" value={detail.pmid} />
              <MetadataToken label="DOI" value={detail.doi} />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {selectedItem && <EvidenceTonePill item={selectedItem} />}
            {selectedItem && (
              <Badge
                variant={
                  STATUS_VARIANT[selectedItem.review_status] ?? "default"
                }
              >
                {selectedItem.review_status}
              </Badge>
            )}
          </div>
        </div>

        <div className="mt-5 grid gap-3 border-t border-gray-100 pt-4 sm:grid-cols-3">
          <div className="flex items-center gap-3 rounded-lg bg-gray-50 p-3">
            <Percent className="h-4 w-4 text-primary-700" />
            <div>
              <p className="text-xs text-gray-500">Item confidence</p>
              <p className="text-sm font-semibold text-gray-900">
                {formatPercent(selectedItem?.confidence)}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-lg bg-gray-50 p-3">
            <ShieldCheck className="h-4 w-4 text-primary-700" />
            <div>
              <p className="text-xs text-gray-500">Alignment confidence</p>
              <p className="text-sm font-semibold text-gray-900">
                {formatPercent(selectedTrace?.alignment_confidence)}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-lg bg-gray-50 p-3">
            <FileText className="h-4 w-4 text-primary-700" />
            <div>
              <p className="text-xs text-gray-500">Source page</p>
              <p className="text-sm font-semibold text-gray-900">
                {selectedTrace?.original?.page ??
                  selectedTrace?.translated?.page ??
                  selectedItem?.page ??
                  "\u2014"}
              </p>
            </div>
          </div>
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <section className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
              <SlidersHorizontal className="h-4 w-4 text-primary-700" />
              Evidence categories
            </h3>
            <div className="mt-4 space-y-2">
              {EVIDENCE_CATEGORIES.map((cat) => (
                <CategoryLayerToggle
                  key={cat}
                  category={cat}
                  count={categoryCounts[cat] ?? 0}
                  checked={enabledCategories.has(cat)}
                  onChange={() => toggleCategory(cat)}
                />
              ))}
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
              <Search className="h-4 w-4 text-primary-700" />
              Evidence navigator
            </h3>
            <div className="mt-4 max-h-[460px] space-y-2 overflow-y-auto pr-1">
              {detail.items.map((item) => {
                const active =
                  item.canonical_evidence_id === selectedItem?.canonical_evidence_id;
                const cat = categoryFromItem(item);
                const catColor = cat && CATEGORY_COLORS[cat];
                return (
                  <button
                    key={item.canonical_evidence_id}
                    type="button"
                    onClick={() => setSelectedEvidenceId(item.canonical_evidence_id)}
                    className={cn(
                      "w-full cursor-pointer rounded-lg border p-3 text-left transition-colors focus-visible:ring-2 focus-visible:ring-primary-500",
                      active
                        ? "border-primary-300 bg-primary-50"
                        : "border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50",
                    )}
                    style={
                      active && catColor
                        ? {
                            borderColor: catColor.hex + "60",
                            backgroundColor: catColor.hex + "12",
                          }
                        : undefined
                    }
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <EvidenceTonePill item={item} />
                      <span className="text-xs text-gray-500">
                        {formatPercent(item.confidence)}
                      </span>
                    </div>
                    <p className="mt-2 line-clamp-2 text-sm font-medium text-gray-900">
                      {itemLabel(item)}
                    </p>
                    <p className="mt-1 line-clamp-2 text-xs text-gray-500">
                      {item.value ?? "\u2014"}
                    </p>
                  </button>
                );
              })}
            </div>
          </section>
        </aside>

        <section className="space-y-4">
          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
                  <Highlighter className="h-4 w-4 text-primary-700" />
                  Active evidence
                </p>
                <h3 className="mt-2 text-sm font-semibold text-gray-950">
                  {selectedItem ? itemLabel(selectedItem) : "No evidence selected"}
                </h3>
                <p className="mt-1 font-mono text-xs text-gray-500">
                  {selectedItem?.field_id ?? "\u2014"}
                </p>
              </div>
              {selectedItem && (
                <Badge
                  variant={
                    STATUS_VARIANT[selectedItem.review_status] ?? "default"
                  }
                >
                  {selectedItem.review_status}
                </Badge>
              )}
            </div>
            <p className="mt-3 text-sm leading-6 text-gray-800">
              {selectedItem?.value ?? "\u2014"}
            </p>
          </div>

          <div
            className={cn(
              "grid gap-4",
              showTranslatedDocument && "xl:grid-cols-2",
            )}
          >
            <EvidenceDocumentReader
              title="Original document"
              paragraphs={originalDocument.paragraphs}
            />
            {showTranslatedDocument && (
              <EvidenceDocumentReader
                title="English translation"
                paragraphs={translatedDocument.paragraphs}
              />
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

export function EvidenceDetailView({
  groupId,
  initialEvidenceId,
  initialView = "overview",
}: EvidenceDetailViewProps) {
  const { detail, isLoading, error } = useEvidenceGroupDetail(groupId);
  const [selectedOverrideId, setSelectedOverrideId] = useState<string | null>(
    null,
  );

  const selectedEvidenceId = useMemo(() => {
    if (!detail) {
      return null;
    }
    if (
      selectedOverrideId &&
      detail.items.some(
        (item) => item.canonical_evidence_id === selectedOverrideId,
      )
    ) {
      return selectedOverrideId;
    }
    return findInitialEvidenceId(detail, initialEvidenceId);
  }, [detail, initialEvidenceId, selectedOverrideId]);

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-6 py-10 text-center">
        <p className="text-sm font-medium text-red-700">
          Failed to load evidence detail.
        </p>
      </div>
    );
  }

  if (initialView === "compare") {
    return (
      <BilingualComparison
        detail={detail}
        groupId={groupId}
        selectedEvidenceId={selectedEvidenceId}
        setSelectedEvidenceId={setSelectedOverrideId}
      />
    );
  }

  return <LiteratureOverview detail={detail} groupId={groupId} />;
}
