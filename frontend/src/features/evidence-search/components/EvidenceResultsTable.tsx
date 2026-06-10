"use client";

import {
  BookOpen,
  ChevronLeft,
  ChevronRight,
  FileText,
  Layers3,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import type { EvidenceSearchResult } from "../types/evidenceSearch";
import {
  buildLiteratureRows,
  type LiteratureEvidenceRow,
} from "../utils/literatureRows";

interface EvidenceResultsTableProps {
  results: EvidenceSearchResult[];
  total: number;
  page: number;
  pageSize: number;
  isLoading?: boolean;
  onPageChange?: (page: number) => void;
  onRowClick?: (item: LiteratureEvidenceRow) => void;
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

function formatPercent(value?: number | null) {
  if (value == null) {
    return "\u2014";
  }
  return `${(value * 100).toFixed(0)}%`;
}

function formatDate(isoString?: string | null) {
  if (!isoString) {
    return "\u2014";
  }
  try {
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) {
      return "\u2014";
    }
    return date.toLocaleDateString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  } catch {
    return "\u2014";
  }
}

function joinedLabel(values: string[]) {
  return values.length > 0 ? values.join(", ") : "\u2014";
}

function literatureTitle(row: LiteratureEvidenceRow) {
  return row.title?.trim() || "Untitled literature record";
}

function TokenList({
  values,
  tone,
}: {
  values: string[];
  tone: "primary" | "success" | "amber" | "gray";
}) {
  const visible = values.slice(0, 3);
  const hiddenCount = Math.max(0, values.length - visible.length);
  const toneClass = {
    primary: "border-primary-100 bg-primary-50 text-primary-900",
    success: "border-success-100 bg-success-50 text-success-800",
    amber: "border-amber-100 bg-amber-50 text-amber-800",
    gray: "border-gray-200 bg-gray-50 text-gray-700",
  }[tone];

  if (values.length === 0) {
    return <span className="text-sm text-gray-400">\u2014</span>;
  }

  return (
    <div className="flex min-w-0 flex-wrap gap-1.5" title={joinedLabel(values)}>
      {visible.map((value) => (
        <span
          key={value}
          className={`max-w-[12rem] truncate rounded-md border px-2 py-1 text-xs font-medium ${toneClass}`}
        >
          {value}
        </span>
      ))}
      {hiddenCount > 0 && (
        <span className="rounded-md border border-gray-200 bg-white px-2 py-1 text-xs font-medium text-gray-500">
          +{hiddenCount}
        </span>
      )}
    </div>
  );
}

export function EvidenceResultsTable({
  results,
  total,
  page,
  pageSize,
  isLoading,
  onPageChange,
  onRowClick,
}: EvidenceResultsTableProps) {
  const rows = buildLiteratureRows(results);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const startItem = (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, total);

  if (isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 bg-white px-6 py-12 text-center">
        <BookOpen className="mx-auto h-10 w-10 text-gray-300" />
        <p className="mt-3 text-sm font-medium text-gray-900">
          No literature matched this search.
        </p>
        <p className="mt-1 text-sm text-gray-500">
          Adjust the gene, variant, disease, or PMID filters and search again.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-medium text-gray-900">
            {rows.length} literature row{rows.length !== 1 ? "s" : ""} on this page
          </p>
          <p className="mt-0.5 text-xs text-gray-500">
            {total} evidence group{total !== 1 ? "s" : ""} &middot; Showing {startItem}
            &ndash;{endItem}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => onPageChange?.(page - 1)}
            disabled={page <= 1}
            className="flex h-10 w-10 cursor-pointer items-center justify-center rounded-md border border-gray-200 text-gray-600 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Previous page"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="min-w-[5.5rem] text-center text-sm text-gray-600">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => onPageChange?.(page + 1)}
            disabled={page >= totalPages}
            className="flex h-10 w-10 cursor-pointer items-center justify-center rounded-md border border-gray-200 text-gray-600 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Next page"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="space-y-3 md:hidden">
        {rows.map((row) => (
          <button
            key={row.documentId}
            type="button"
            onClick={() => onRowClick?.(row)}
            className="w-full cursor-pointer rounded-lg border border-gray-200 bg-white p-4 text-left shadow-sm transition-colors hover:border-primary-200 hover:bg-primary-50/30 focus-visible:ring-2 focus-visible:ring-primary-500"
          >
            <div className="flex items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary-50 text-primary-700">
                <FileText className="h-5 w-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="line-clamp-2 text-sm font-semibold leading-5 text-gray-950">
                  {literatureTitle(row)}
                </p>
                <p className="mt-1 truncate font-mono text-xs text-gray-500">
                  UUID {row.documentId}
                </p>
              </div>
              <Badge variant={STATUS_VARIANT[row.reviewStatus] ?? "info"}>
                {row.reviewStatus}
              </Badge>
            </div>
            <div className="mt-4 space-y-3">
              <div className="flex flex-wrap gap-2 text-xs text-gray-500">
                <span>PMID {row.pmid ?? "\u2014"}</span>
                <span>DOI {row.doi ?? "\u2014"}</span>
              </div>
              <TokenList values={row.genes} tone="primary" />
              <TokenList values={row.variants} tone="success" />
              <p className="line-clamp-2 text-sm text-gray-700">
                {joinedLabel(row.diseases)}
              </p>
            </div>
            <div className="mt-4 grid grid-cols-4 gap-2 border-t border-gray-100 pt-3 text-xs text-gray-500">
              <span>{row.groupCount} group{row.groupCount !== 1 ? "s" : ""}</span>
              <span>{row.fieldCount} fields</span>
              <span>{formatPercent(row.avgConfidence)}</span>
              <span>{formatDate(row.createdAt)}</span>
            </div>
          </button>
        ))}
      </div>

      <div className="hidden overflow-hidden rounded-lg border border-gray-200 bg-white md:block">
        <table className="w-full table-fixed text-sm">
          <thead className="border-b border-gray-200 bg-gray-50">
            <tr className="text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              <th className="w-[20%] px-4 py-3">Literature</th>
              <th className="w-[18%] px-4 py-3">Evidence Focus</th>
              <th className="w-[16%] px-4 py-3">Disease</th>
              <th className="w-[14%] px-4 py-3">Classification</th>
              <th className="w-[10%] px-4 py-3">Created</th>
              <th className="w-[10%] px-4 py-3">Review</th>
              <th className="w-[8%] px-4 py-3 text-right">Fields</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {rows.map((row) => (
              <tr
                key={row.documentId}
                role={onRowClick ? "link" : undefined}
                tabIndex={onRowClick ? 0 : undefined}
                aria-label={`Open literature evidence ${row.title ?? row.pmid ?? row.documentId}`}
                onClick={() => onRowClick?.(row)}
                onKeyDown={(e) => {
                  if (onRowClick && (e.key === "Enter" || e.key === " ")) {
                    e.preventDefault();
                    onRowClick(row);
                  }
                }}
                className="cursor-pointer transition-colors hover:bg-primary-50/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-inset"
              >
                <td className="px-4 py-4 align-top">
                  <div className="flex min-w-0 items-start gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary-50 text-primary-700">
                      <FileText className="h-4 w-4" />
                    </span>
                    <div className="min-w-0">
                      <p className="line-clamp-2 text-sm font-semibold leading-5 text-gray-950">
                        {literatureTitle(row)}
                      </p>
                      <p className="mt-1 truncate font-mono text-xs text-gray-500">
                        UUID {row.documentId}
                      </p>
                      <p className="mt-1 truncate text-xs text-gray-500">
                        PMID {row.pmid ?? "\u2014"} · DOI {row.doi ?? "\u2014"}
                      </p>
                      <p className="mt-2 inline-flex items-center gap-1 text-xs text-gray-500">
                        <Layers3 className="h-3.5 w-3.5" />
                        {row.groupCount} evidence group{row.groupCount !== 1 ? "s" : ""}
                      </p>
                    </div>
                  </div>
                </td>
                <td className="space-y-2 px-4 py-4 align-top">
                  <TokenList values={row.genes} tone="primary" />
                  <TokenList values={row.variants} tone="success" />
                </td>
                <td className="px-4 py-4 align-top text-gray-700">
                  <p className="line-clamp-3" title={joinedLabel(row.diseases)}>
                    {joinedLabel(row.diseases)}
                  </p>
                </td>
                <td className="px-4 py-4 align-top">
                  <TokenList values={row.classifications} tone="amber" />
                </td>
                <td className="px-4 py-4 align-top text-xs text-gray-500">
                  {formatDate(row.createdAt)}
                </td>
                <td className="px-4 py-4 align-top">
                  <Badge variant={STATUS_VARIANT[row.reviewStatus] ?? "info"}>
                    {row.reviewStatus}
                  </Badge>
                  <p className="mt-2 text-xs text-gray-500">
                    {formatPercent(row.avgConfidence)} confidence
                  </p>
                </td>
                <td className="px-4 py-4 text-right align-top">
                  <span className="text-sm font-semibold text-gray-900">
                    {row.fieldCount}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
