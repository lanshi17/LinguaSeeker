"use client";

import {
  ChevronLeft,
  ChevronRight,
  FileText,
  Layers3,
  Search,
  Database,
  BarChart3,
  Calendar,
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
    primary: "border-primary-200/60 bg-primary-50/80 text-primary-800",
    success: "border-success-200/60 bg-success-50/80 text-success-800",
    amber: "border-amber-200/60 bg-amber-50/80 text-amber-800",
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
          className={`max-w-[12rem] truncate rounded-md border px-2 py-0.5 text-xs font-medium shadow-sm ${toneClass}`}
        >
          {value}
        </span>
      ))}
      {hiddenCount > 0 && (
        <span className="rounded-md border border-gray-200 bg-white px-2 py-0.5 text-xs font-medium text-gray-500 shadow-sm">
          +{hiddenCount}
        </span>
      )}
    </div>
  );
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
      <div className="flex flex-col items-center justify-center gap-4 rounded-xl border border-gray-200 bg-white py-16">
        <div className="relative">
          <div className="absolute inset-0 animate-ping rounded-full bg-primary-200 opacity-20" />
          <Spinner />
        </div>
        <p className="text-sm font-medium text-gray-600">
          Loading evidence data...
        </p>
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="relative overflow-hidden rounded-xl border border-dashed border-gray-300 bg-gradient-to-br from-gray-50 to-white px-6 py-16 text-center">
        {/* Decorative background */}
        <div className="absolute inset-0 opacity-[0.03]">
          <svg className="h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
            <defs>
              <pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse">
                <path d="M 10 0 L 0 0 0 10" fill="none" stroke="currentColor" strokeWidth="0.5" />
              </pattern>
            </defs>
            <rect width="100" height="100" fill="url(#grid)" />
          </svg>
        </div>
        <div className="relative">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary-100 to-primary-50 shadow-inner">
            <Search className="h-8 w-8 text-primary-500" />
          </div>
          <p className="mt-5 text-base font-semibold text-gray-900">
            No literature matched this search
          </p>
          <p className="mt-2 max-w-sm text-sm text-gray-500">
            Try adjusting the gene, variant, disease, or PMID filters to broaden your search criteria.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Results header with stats and pagination */}
      <div className="flex flex-col gap-4 rounded-xl border border-gray-200 bg-white px-5 py-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-50">
            <Database className="h-5 w-5 text-primary-600" />
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-900">
              {rows.length} literature row{rows.length !== 1 ? "s" : ""}
            </p>
            <p className="mt-0.5 text-xs text-gray-500">
              {total} evidence group{total !== 1 ? "s" : ""} total
              <span className="mx-1.5 text-gray-300">·</span>
              Showing {startItem}&ndash;{endItem}
            </p>
          </div>
        </div>

        {/* Modern pagination */}
        <div className="flex items-center gap-1.5 rounded-lg bg-gray-50 p-1">
          <button
            onClick={() => onPageChange?.(page - 1)}
            disabled={page <= 1}
            className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-md text-gray-600 transition-all hover:bg-white hover:shadow-sm disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:shadow-none"
            aria-label="Previous page"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <div className="flex h-8 min-w-[4rem] items-center justify-center rounded-md bg-white px-3 shadow-sm">
            <span className="text-sm font-medium text-gray-900">
              {page}
            </span>
            <span className="mx-1 text-gray-400">/</span>
            <span className="text-sm text-gray-500">
              {totalPages}
            </span>
          </div>
          <button
            onClick={() => onPageChange?.(page + 1)}
            disabled={page >= totalPages}
            className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-md text-gray-600 transition-all hover:bg-white hover:shadow-sm disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:shadow-none"
            aria-label="Next page"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Mobile cards */}
      <div className="space-y-3 md:hidden">
        {rows.map((row, index) => (
          <button
            key={row.documentId}
            type="button"
            onClick={() => onRowClick?.(row)}
            className="group w-full cursor-pointer rounded-xl border border-gray-200 bg-white p-4 text-left shadow-sm transition-all hover:border-primary-200 hover:shadow-md focus-visible:ring-2 focus-visible:ring-primary-500"
            style={{ animationDelay: `${index * 50}ms` }}
          >
            <div className="flex items-start gap-3">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-primary-100 to-primary-50 text-primary-700 shadow-sm transition-transform group-hover:scale-105">
                <FileText className="h-5 w-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="line-clamp-2 text-sm font-semibold leading-5 text-gray-950 group-hover:text-primary-700">
                  {literatureTitle(row)}
                </p>
                <p className="mt-1 truncate font-mono text-xs text-gray-400">
                  {row.documentId.slice(0, 8)}...
                </p>
              </div>
              <Badge variant={STATUS_VARIANT[row.reviewStatus] ?? "info"}>
                {row.reviewStatus}
              </Badge>
            </div>
            <div className="mt-4 space-y-3">
              <div className="flex flex-wrap gap-2 text-xs text-gray-500">
                <span className="rounded bg-gray-100 px-1.5 py-0.5">PMID {row.pmid ?? "\u2014"}</span>
                <span className="rounded bg-gray-100 px-1.5 py-0.5">DOI {row.doi ?? "\u2014"}</span>
              </div>
              <TokenList values={row.genes} tone="primary" />
              <TokenList values={row.variants} tone="success" />
              <p className="line-clamp-2 text-sm text-gray-700">
                {joinedLabel(row.diseases)}
              </p>
            </div>
            <div className="mt-4 flex flex-wrap gap-2 border-t border-gray-100 pt-3">
              <StatBadge icon={Layers3} value={row.groupCount} label="groups" />
              <StatBadge icon={BarChart3} value={row.fieldCount} label="fields" />
              <StatBadge icon={Calendar} value={formatDate(row.createdAt)} label="" />
            </div>
          </button>
        ))}
      </div>

      {/* Desktop table */}
      <div className="hidden overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm md:block">
        <table className="w-full table-fixed text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gradient-to-r from-gray-50 via-gray-50 to-gray-50/50">
              <th className="w-[20%] px-4 py-3.5 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                Literature
              </th>
              <th className="w-[18%] px-4 py-3.5 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                Evidence Focus
              </th>
              <th className="w-[16%] px-4 py-3.5 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                Disease
              </th>
              <th className="w-[14%] px-4 py-3.5 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                Classification
              </th>
              <th className="w-[10%] px-4 py-3.5 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                Created
              </th>
              <th className="w-[10%] px-4 py-3.5 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                Review
              </th>
              <th className="w-[8%] px-4 py-3.5 text-right text-xs font-semibold uppercase tracking-wider text-gray-500">
                Fields
              </th>
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
                className="group cursor-pointer transition-all duration-150 hover:bg-gradient-to-r hover:from-primary-50/60 hover:to-transparent focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-inset"
              >
                <td className="px-4 py-4 align-top">
                  <div className="flex min-w-0 items-start gap-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-primary-100 to-primary-50 text-primary-700 shadow-sm transition-transform group-hover:scale-105">
                      <FileText className="h-4.5 w-4.5" />
                    </span>
                    <div className="min-w-0">
                      <p className="line-clamp-2 text-sm font-semibold leading-5 text-gray-950 group-hover:text-primary-700">
                        {literatureTitle(row)}
                      </p>
                      <p className="mt-1 truncate font-mono text-xs text-gray-400">
                        {row.documentId.slice(0, 8)}...
                      </p>
                      <div className="mt-1.5 flex items-center gap-2 text-xs text-gray-500">
                        <span className="rounded bg-gray-100 px-1.5 py-0.5 font-medium">
                          PMID {row.pmid ?? "\u2014"}
                        </span>
                      </div>
                    </div>
                  </div>
                </td>
                <td className="space-y-2 px-4 py-4 align-top">
                  <TokenList values={row.genes} tone="primary" />
                  <TokenList values={row.variants} tone="success" />
                </td>
                <td className="px-4 py-4 align-top">
                  <p className="line-clamp-3 text-gray-700" title={joinedLabel(row.diseases)}>
                    {joinedLabel(row.diseases)}
                  </p>
                </td>
                <td className="px-4 py-4 align-top">
                  <TokenList values={row.classifications} tone="amber" />
                </td>
                <td className="px-4 py-4 align-top">
                  <div className="flex items-center gap-1.5 text-xs text-gray-500">
                    <Calendar className="h-3.5 w-3.5 text-gray-400" />
                    {formatDate(row.createdAt)}
                  </div>
                </td>
                <td className="px-4 py-4 align-top">
                  <Badge variant={STATUS_VARIANT[row.reviewStatus] ?? "info"}>
                    {row.reviewStatus}
                  </Badge>
                  <div className="mt-2 flex items-center gap-1 text-xs text-gray-500">
                    <BarChart3 className="h-3 w-3" />
                    {formatPercent(row.avgConfidence)}
                  </div>
                </td>
                <td className="px-4 py-4 text-right align-top">
                  <span className="inline-flex h-7 min-w-[1.75rem] items-center justify-center rounded-md bg-gray-100 px-2 text-sm font-semibold text-gray-700">
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
