"use client";

import { useMemo, useState } from "react";
import {
  ArrowLeft,
  BookOpen,
  Columns2,
  FileText,
  Languages,
  ListChecks,
  Percent,
  Search,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { cn } from "@/lib/utils/cn";
import { useEvidenceGroupDetail } from "../hooks/useEvidenceGroupDetail";
import type {
  EvidenceGroupDetailResponse,
  EvidenceGroupItem,
} from "../types/evidenceSearch";
import {
  buildBilingualCompareHref,
  findInitialEvidenceId,
} from "../utils/literatureRows";
import {
  EvidenceHighlightText,
  type EvidenceHighlightTone,
} from "./EvidenceHighlightText";

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

const CATEGORY_LABELS: Record<string, string> = {
  A: "Variant information",
  B: "Case and phenotype",
  C: "Segregation",
  D: "Population frequency",
  E: "Computational evidence",
  F: "Functional evidence",
  G: "Case-control evidence",
  H: "Contradiction evidence",
  I: "Gene function",
  J: "Authority and validity",
};

const TONE_CHIP_STYLES: Record<EvidenceHighlightTone, string> = {
  classification: "border-amber-200 bg-amber-50 text-amber-800",
  disease: "border-rose-200 bg-rose-50 text-rose-800",
  functional: "border-success-200 bg-success-50 text-success-800",
  gene: "border-primary-200 bg-primary-50 text-primary-800",
  neutral: "border-gray-200 bg-gray-50 text-gray-700",
  variant: "border-cyan-200 bg-cyan-50 text-cyan-800",
};

function formatPercent(value?: number | null) {
  if (value == null) {
    return "\u2014";
  }
  return `${(value * 100).toFixed(0)}%`;
}

function categoryFromItem(item: EvidenceGroupItem) {
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

function evidenceTone(item?: EvidenceGroupItem | null): EvidenceHighlightTone {
  const fieldId = item?.field_id.toLowerCase() ?? "";
  const category = item ? categoryFromItem(item) : null;

  if (fieldId.includes("gene")) {
    return "gene";
  }
  if (fieldId.includes("variant") || fieldId.includes("hgvs")) {
    return "variant";
  }
  if (fieldId.includes("disease") || fieldId.includes("phenotype")) {
    return "disease";
  }
  if (
    fieldId.includes("classification") ||
    fieldId.includes("pathogenic") ||
    fieldId.includes("acmg")
  ) {
    return "classification";
  }
  if (["F", "G", "I"].includes(category ?? "")) {
    return "functional";
  }
  return "neutral";
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

function EvidenceTonePill({ item }: { item: EvidenceGroupItem }) {
  const tone = evidenceTone(item);
  return (
    <span
      className={cn(
        "rounded-md border px-2 py-1 text-xs font-medium",
        TONE_CHIP_STYLES[tone],
      )}
    >
      {categoryLabel(categoryFromItem(item))}
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
          Compare text
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
              <h2 className="mt-2 text-xl font-semibold text-gray-950">
                PMID {detail.pmid ?? "\u2014"}
              </h2>
              <p className="mt-1 truncate text-sm text-primary-900">
                DOI {detail.doi ?? "\u2014"}
              </p>
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
                Open comparison
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
  const selectedItem =
    detail.items.find(
      (item) => item.canonical_evidence_id === selectedEvidenceId,
    ) ??
    detail.items[0] ??
    null;
  const selectedTrace = selectedTraceFor(detail, selectedEvidenceId);
  const tone = evidenceTone(selectedItem);

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
              Bilingual evidence trace
            </p>
            <h2 className="mt-2 text-xl font-semibold text-gray-950">
              {selectedItem ? itemLabel(selectedItem) : "No evidence selected"}
            </h2>
            <p className="mt-1 font-mono text-xs text-gray-500">
              {selectedItem?.field_id ?? "\u2014"}
            </p>
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
        <aside className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
            <Search className="h-4 w-4 text-primary-700" />
            Evidence items
          </h3>
          <div className="mt-4 max-h-[620px] space-y-2 overflow-y-auto pr-1">
            {detail.items.map((item) => {
              const active =
                item.canonical_evidence_id === selectedItem?.canonical_evidence_id;
              return (
                <button
                  key={item.canonical_evidence_id}
                  type="button"
                  onClick={() => setSelectedEvidenceId(item.canonical_evidence_id)}
                  className={cn(
                    "w-full cursor-pointer rounded-lg border p-3 text-left transition-colors focus-visible:ring-2 focus-visible:ring-primary-500",
                    active
                      ? "border-primary-300 bg-primary-50"
                      : "border-gray-200 bg-white hover:border-primary-200 hover:bg-gray-50",
                  )}
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
        </aside>

        <section className="space-y-4">
          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Extracted value
            </p>
            <p className="mt-2 text-sm leading-6 text-gray-800">
              {selectedItem?.value ?? "\u2014"}
            </p>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <section>
              <h3 className="mb-2 text-sm font-semibold text-gray-900">
                Original text
              </h3>
              <EvidenceHighlightText
                highlight={selectedTrace?.original}
                label={selectedItem?.field_id}
                tone={tone}
                active
              />
            </section>
            <section>
              <h3 className="mb-2 text-sm font-semibold text-gray-900">
                Translated text
              </h3>
              <EvidenceHighlightText
                highlight={selectedTrace?.translated}
                label={selectedItem?.field_id}
                tone={tone}
                active
              />
            </section>
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
