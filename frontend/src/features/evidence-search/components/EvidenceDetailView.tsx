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
  Database,
  Hash,
  Link2,
  TrendingUp,
  AlertCircle,
  Dna,
  FlaskConical,
  Stethoscope,
  Layers3,
  Pencil,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { cn } from "@/lib/utils/cn";
import { useEvidenceGroupDetail } from "../hooks/useEvidenceGroupDetail";
import { EvidenceCorrectionForm } from "./EvidenceCorrectionForm";
import { EvidenceAuditHistory } from "./EvidenceAuditHistory";
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
  hasTranslatedDocumentText,
  type EvidenceDocumentHighlight,
  type EvidenceDocumentParagraph,
} from "../utils/evidenceDocument";
import {
  buildBilingualCompareHref,
  findInitialEvidenceId,
} from "../utils/literatureRows";
import { MarkdownDocumentViewer } from "./MarkdownDocumentViewer";

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

import {
  categoryChipStyle,
  categoryLabel,
  categoryMarkStyle,
} from "../utils/categoryStyles";

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

function StatBadge({
  icon: Icon,
  value,
  label,
}: {
  icon: React.ComponentType<{ className?: string }>;
  value: string | number;
  label: string;
}) {
  return (
    <div className="flex items-center gap-1.5 rounded-md bg-gray-50 px-2 py-1 text-xs">
      <Icon className="h-3.5 w-3.5 text-gray-400" />
      <span className="font-medium text-gray-700">{value}</span>
      <span className="text-gray-500">{label}</span>
    </div>
  );
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
  icon: Icon,
}: {
  label: string;
  value?: string | null;
  icon?: React.ComponentType<{ className?: string }>;
}) {
  return (
    <span className="inline-flex max-w-full items-center gap-1.5 rounded-md border border-primary-200/60 bg-white px-2.5 py-1 text-xs text-primary-900 shadow-sm">
      {Icon && <Icon className="h-3 w-3 shrink-0 text-primary-500" />}
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

const FIELD_ID_TO_CARD_FIELD: Record<string, string> = {
  "A.gene_symbol": "gene",
  "B.disease_diagnosis": "disease",
  "B.clinical_diagnosis": "disease",
  "J.authority_classification": "classification",
};

function cardFieldForFieldId(fieldId: string): string | null {
  if (FIELD_ID_TO_CARD_FIELD[fieldId]) return FIELD_ID_TO_CARD_FIELD[fieldId];
  if (fieldId.startsWith("A.variant_hgvs_")) return "variant";
  return null;
}

function EvidenceItemSummary({
  groupId,
  item,
}: {
  groupId: string;
  item: EvidenceGroupItem;
}) {
  const [editing, setEditing] = useState(false);
  const cardField = cardFieldForFieldId(item.field_id);

  return (
    <article className="group relative overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm transition-all hover:border-primary-200 hover:shadow-md">
      <div className="absolute left-0 top-0 h-full w-1 bg-gradient-to-b from-primary-400 to-primary-600 opacity-0 transition-opacity group-hover:opacity-100" />

      <div className="p-5">
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
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setEditing((v) => !v)}
              className={cn(
                "inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-md border px-2.5 text-sm font-medium transition-colors",
                editing
                  ? "border-primary-300 bg-primary-100 text-primary-800"
                  : "border-gray-200 bg-white text-gray-600 hover:border-primary-200 hover:bg-primary-50 hover:text-primary-700",
              )}
            >
              <Pencil className="h-3.5 w-3.5" />
              {editing ? "Close" : "Edit"}
            </button>
            <Link
              to={buildBilingualCompareHref(groupId, item.canonical_evidence_id)}
              className="inline-flex h-9 cursor-pointer items-center gap-2 rounded-md border border-primary-200 bg-primary-50 px-3 text-sm font-medium text-primary-800 transition-colors hover:bg-primary-100 focus-visible:ring-2 focus-visible:ring-primary-500"
            >
              <Columns2 className="h-4 w-4" />
              Compare
            </Link>
          </div>
        </div>

        <p className="mt-4 line-clamp-3 text-sm leading-6 text-gray-700">
          {item.value ?? "\u2014"}
        </p>

        <div className="mt-4 flex flex-wrap gap-2 border-t border-gray-100 pt-3">
          <StatBadge icon={Percent} value={formatPercent(item.confidence)} label="confidence" />
          <StatBadge icon={Layers3} value={item.track ?? "\u2014"} label="track" />
          <StatBadge icon={FileText} value={item.page ?? "\u2014"} label="page" />
        </div>
      </div>

      {editing && (
        <EvidenceCorrectionForm
          canonicalEvidenceId={item.canonical_evidence_id}
          currentValue={item.value ?? null}
          currentStatus={item.review_status}
          fieldId={item.field_id}
          cardField={cardField}
          groupId={groupId}
          onClose={() => setEditing(false)}
        />
      )}
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
        to="/evidence"
        className="inline-flex items-center gap-2 text-sm font-medium text-gray-500 transition-colors hover:text-primary-600"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to literature
      </Link>

      <section className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
        <div className="relative border-b border-primary-100 bg-gradient-to-r from-primary-50 via-primary-50/50 to-transparent px-6 py-5">
          <div className="absolute left-0 top-0 h-full w-1 bg-gradient-to-b from-primary-400 to-primary-600" />
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
                  icon={Hash}
                />
                <MetadataToken label="PMID" value={detail.pmid} icon={FileText} />
                <MetadataToken label="DOI" value={detail.doi} icon={Link2} />
              </div>
            </div>
            <Badge variant={STATUS_VARIANT.approved}>Traceable</Badge>
          </div>
        </div>

        <div className="grid gap-0 md:grid-cols-4">
          {(
            [
              { label: "Gene", value: detail.gene, Icon: Dna },
              { label: "Variant", value: detail.variant, Icon: FlaskConical },
              { label: "Disease", value: detail.disease, Icon: Stethoscope },
              { label: "Classification", value: detail.classification, Icon: ShieldCheck },
            ] as const
          ).map(({ label, value, Icon }) => (
            <div
              key={label}
              className="border-b border-gray-100 px-5 py-4 md:border-b-0 md:border-r last:md:border-r-0"
            >
              <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
                <Icon className="h-3.5 w-3.5" />
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
          <section className="rounded-xl border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-100 px-5 py-3">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
                <ListChecks className="h-4 w-4 text-primary-700" />
                Evidence coverage
              </h3>
            </div>
            <div className="grid grid-cols-2 gap-0">
              {[
                { label: "Items", value: detail.item_count, icon: Database },
                { label: "Confidence", value: formatPercent(detail.avg_confidence), icon: TrendingUp },
                { label: "Traces", value: detail.traces.length, icon: Search },
                { label: "Fields", value: Object.keys(detail.distribution.by_field).length, icon: FileText },
              ].map((stat, idx) => (
                <div
                  key={stat.label}
                  className={cn(
                    "p-4",
                    idx % 2 === 0 && "border-r border-gray-100",
                    idx < 2 && "border-b border-gray-100",
                  )}
                >
                  <div className="flex items-center gap-2">
                    <stat.icon className="h-3.5 w-3.5 text-gray-400" />
                    <p className="text-xs font-medium text-gray-500">{stat.label}</p>
                  </div>
                  <p className="mt-1.5 text-xl font-bold text-gray-950">
                    {stat.value}
                  </p>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-xl border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-100 px-5 py-3">
              <h3 className="text-sm font-semibold text-gray-900">
                Evidence categories
              </h3>
            </div>
            <div className="flex flex-wrap gap-2 p-4">
              {countEntries(detail.distribution.by_category).map(
                ([key, count]) => (
                  <span
                    key={key}
                    className="rounded-md border border-gray-200 bg-gray-50 px-2.5 py-1.5 text-xs font-medium text-gray-700 shadow-sm"
                  >
                    {categoryLabel(key)} · {count}
                  </span>
                ),
              )}
            </div>
          </section>

          <section className="rounded-xl border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-100 px-5 py-3">
              <h3 className="text-sm font-semibold text-gray-900">
                Review status
              </h3>
            </div>
            <div className="flex flex-wrap gap-2 p-4">
              {countEntries(detail.distribution.by_status).map(
                ([key, count]) => (
                  <Badge key={key} variant={STATUS_VARIANT[key] ?? "default"}>
                    {key}: {count}
                  </Badge>
                ),
              )}
            </div>
          </section>

          <EvidenceAuditHistory sourceDocumentId={detail.source_document_id} />
        </aside>

        <section className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-gray-200 bg-white px-5 py-4 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-50">
                <ListChecks className="h-5 w-5 text-primary-600" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-gray-950">
                  Extracted evidence fields
                </h2>
                <p className="mt-0.5 text-sm text-gray-500">
                  {detail.items.length} field-level evidence items
                </p>
              </div>
            </div>
            {detail.items[0] && (
              <Link
                to={buildBilingualCompareHref(
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
  const isFullText = paragraphs.length === 1 && paragraphs[0].text.length > 500;

  return (
    <section className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
      <div className="sticky top-0 z-10 border-b border-gray-100 bg-gradient-to-r from-gray-50 via-gray-50 to-gray-50/50 px-5 py-3 backdrop-blur-sm">
        <h3 className="text-sm font-semibold text-gray-950">{title}</h3>
        <p className="mt-0.5 text-xs text-gray-500">
          {isFullText
            ? "Full document with evidence highlights"
            : `${paragraphs.length} aligned paragraph${paragraphs.length !== 1 ? "s" : ""}`}
        </p>
      </div>
      <div className="max-h-[720px] overflow-y-auto px-5">
        {paragraphs.length > 0 ? (
          isFullText ? (
            <MarkdownDocumentViewer
              markdown={paragraphs[0].text}
              highlights={paragraphs[0].highlights}
            />
          ) : (
            paragraphs.map((paragraph) => (
              <HighlightedParagraph key={paragraph.id} paragraph={paragraph} />
            ))
          )
        ) : (
          <div className="flex flex-col items-center gap-3 px-2 py-12 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gray-100">
              <FileText className="h-6 w-6 text-gray-400" />
            </div>
            <p className="text-sm text-gray-500">
              No document text is available for this track.
            </p>
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

function BilingualCompareView({
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
  // Data availability ignores user-applied filters so category toggles do not mount/unmount
  // the translated reader or reflow the document grid.
  const showTranslatedDocument = hasTranslatedDocumentText(detail);

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
        to={`/evidence/detail?groupId=${encodeURIComponent(groupId)}`}
        className="inline-flex items-center gap-2 text-sm font-medium text-gray-500 transition-colors hover:text-primary-600"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to literature detail
      </Link>

      <section className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
        <div className="relative border-b border-purple-100 bg-gradient-to-r from-purple-50 via-purple-50/50 to-transparent px-6 py-5">
          <div className="absolute left-0 top-0 h-full w-1 bg-gradient-to-b from-purple-400 to-purple-600" />
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-purple-800">
                <Columns2 className="h-4 w-4" />
                Bilingual full-text document
              </p>
              <h2 className="mt-2 max-w-4xl text-xl font-semibold leading-7 text-gray-950">
                {detailTitle(detail)}
              </h2>
              <div className="mt-3 flex max-w-4xl flex-wrap gap-2">
                <MetadataToken label="UUID" value={detail.source_document_id} icon={Hash} />
                <MetadataToken label="PMID" value={detail.pmid} icon={FileText} />
                <MetadataToken label="DOI" value={detail.doi} icon={Link2} />
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
        </div>

        <div className="grid gap-0 sm:grid-cols-3">
          {[
            { label: "Item confidence", value: formatPercent(selectedItem?.confidence), icon: TrendingUp },
            { label: "Alignment confidence", value: formatPercent(selectedTrace?.alignment_confidence), icon: ShieldCheck },
            { label: "Source page", value: selectedTrace?.original?.page ?? selectedTrace?.translated?.page ?? selectedItem?.page ?? "\u2014", icon: FileText },
          ].map((stat, idx) => (
            <div
              key={stat.label}
              className={cn(
                "flex items-center gap-3 p-4",
                idx < 2 && "border-b sm:border-b-0 sm:border-r border-gray-100",
              )}
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-purple-100 to-purple-50">
                <stat.icon className="h-4 w-4 text-purple-700" />
              </div>
              <div>
                <p className="text-xs text-gray-500">{stat.label}</p>
                <p className="text-sm font-semibold text-gray-900">
                  {stat.value}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <section className="rounded-xl border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-100 px-4 py-3">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
                <SlidersHorizontal className="h-4 w-4 text-primary-700" />
                Evidence categories
              </h3>
            </div>
            <div className="space-y-2 p-4">
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

          <section className="rounded-xl border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-100 px-4 py-3">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
                <Search className="h-4 w-4 text-primary-700" />
                Evidence navigator
              </h3>
            </div>
            <div className="max-h-[460px] space-y-2 overflow-y-auto p-4 pr-3">
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
                      "group w-full cursor-pointer rounded-lg border p-3 text-left transition-all focus-visible:ring-2 focus-visible:ring-primary-500",
                      active
                        ? "border-primary-300 bg-primary-50 shadow-sm"
                        : "border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50 hover:shadow-sm",
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
                    <p className="mt-2 line-clamp-2 text-sm font-medium text-gray-900 group-hover:text-primary-700">
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
          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
            <div className="relative border-b border-gray-100 bg-gradient-to-r from-primary-50/50 to-transparent px-5 py-4">
              <div className="absolute left-0 top-0 h-full w-1 bg-gradient-to-b from-primary-400 to-primary-600" />
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-primary-800">
                    <Highlighter className="h-4 w-4" />
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
            </div>
            <div className="px-5 py-4">
              <p className="text-sm leading-6 text-gray-800">
                {selectedItem?.value ?? "\u2014"}
              </p>
            </div>
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
      <div className="flex flex-col items-center justify-center gap-4 rounded-xl border border-gray-200 bg-white py-16">
        <div className="relative">
          <div className="absolute inset-0 animate-ping rounded-full bg-primary-200 opacity-20" />
          <Spinner />
        </div>
        <p className="text-sm font-medium text-gray-600">
          Loading evidence detail...
        </p>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="relative overflow-hidden rounded-xl border border-red-200 bg-gradient-to-br from-red-50 to-white px-6 py-14 text-center">
        <div className="relative">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-red-100">
            <AlertCircle className="h-7 w-7 text-red-500" />
          </div>
          <p className="mt-4 text-sm font-semibold text-red-800">
            Failed to load evidence detail
          </p>
          <p className="mt-1 text-sm text-red-600">
            {error?.message ?? "The requested evidence group could not be found."}
          </p>
          <Link
            to="/evidence"
            className="mt-5 inline-flex items-center gap-2 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to literature
          </Link>
        </div>
      </div>
    );
  }

  if (initialView === "compare") {
    return (
      <BilingualCompareView
        detail={detail}
        groupId={groupId}
        selectedEvidenceId={selectedEvidenceId}
        setSelectedEvidenceId={setSelectedOverrideId}
      />
    );
  }

  return <LiteratureOverview detail={detail} groupId={groupId} />;
}
