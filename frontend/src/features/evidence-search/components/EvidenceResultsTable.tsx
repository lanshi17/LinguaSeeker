"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import type { EvidenceSearchResult } from "../types/evidenceSearch";

interface EvidenceResultsTableProps {
  results: EvidenceSearchResult[];
  total: number;
  page: number;
  pageSize: number;
  isLoading?: boolean;
  onPageChange?: (page: number) => void;
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

export function EvidenceResultsTable({
  results,
  total,
  page,
  pageSize,
  isLoading,
  onPageChange,
}: EvidenceResultsTableProps) {
  const totalPages = Math.ceil(total / pageSize);
  const startItem = (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, total);

  if (isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-gray-500">
        No evidence found. Try a different search.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary and pagination */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          {total} result{total !== 1 ? "s" : ""} &middot; Showing {startItem}&ndash;{endItem}
        </p>

        <div className="flex items-center gap-2">
          <button
            onClick={() => onPageChange?.(page - 1)}
            disabled={page <= 1}
            className="flex h-8 w-8 items-center justify-center rounded-md border border-gray-200 text-gray-500 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Previous page"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="min-w-[5rem] text-center text-sm text-gray-600">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => onPageChange?.(page + 1)}
            disabled={page >= totalPages}
            className="flex h-8 w-8 items-center justify-center rounded-md border border-gray-200 text-gray-500 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Next page"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr className="text-left text-xs font-medium uppercase text-gray-500">
              <th className="px-4 py-3">PMID</th>
              <th className="px-4 py-3">Gene</th>
              <th className="px-4 py-3">Variant</th>
              <th className="px-4 py-3">Disease</th>
              <th className="px-4 py-3">Classification</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Confidence</th>
              <th className="px-4 py-3">Fields</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {results.map((item) => (
              <tr
                key={item.group_id}
                className="cursor-pointer transition-colors hover:bg-gray-50"
              >
                <td className="px-4 py-3 font-mono text-xs text-gray-500">
                  {item.pmid ?? "\u2014"}
                </td>
                <td className="max-w-[200px] truncate px-4 py-3 font-medium text-gray-900">
                  {item.gene ?? "\u2014"}
                </td>
                <td className="max-w-[200px] truncate px-4 py-3 text-gray-700">
                  {item.variant ?? "\u2014"}
                </td>
                <td className="max-w-[200px] truncate px-4 py-3 text-gray-700">
                  {item.disease ?? "\u2014"}
                </td>
                <td className="max-w-[200px] truncate px-4 py-3 text-gray-700">
                  {item.classification ?? "\u2014"}
                </td>
                <td className="px-4 py-3">
                  <Badge
                    variant={
                      STATUS_VARIANT[item.review_status ?? ""] ?? "default"
                    }
                  >
                    {item.review_status ?? "unknown"}
                  </Badge>
                </td>
                <td className="px-4 py-3 text-gray-500">
                  {item.avg_confidence != null
                    ? `${(item.avg_confidence * 100).toFixed(0)}%`
                    : "\u2014"}
                </td>
                <td className="px-4 py-3 text-xs text-gray-400">
                  {item.field_count}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
