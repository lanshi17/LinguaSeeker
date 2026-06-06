"use client";

import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import type { EvidenceSearchResult } from "../types/evidenceSearch";

interface EvidenceResultsTableProps {
  results: EvidenceSearchResult[];
  total: number;
  isLoading?: boolean;
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
  isLoading,
}: EvidenceResultsTableProps) {
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
    <div className="space-y-2">
      <p className="text-sm text-gray-500">
        {total} result{total !== 1 ? "s" : ""} found
      </p>

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
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {results.map((item) => (
              <tr
                key={item.canonical_evidence_id}
                className="cursor-pointer transition-colors hover:bg-gray-50"
              >
                <td className="px-4 py-3 font-mono text-xs text-gray-500">
                  {item.pmid ?? "—"}
                </td>
                <td className="px-4 py-3 font-medium text-gray-900">
                  {item.active_payload?.gene ?? item.gene_ids?.[0] ?? "—"}
                </td>
                <td className="px-4 py-3 text-gray-700">
                  {item.active_payload?.variant ??
                    item.variant_ids?.[0] ??
                    "—"}
                </td>
                <td className="px-4 py-3 text-gray-700">
                  {item.active_payload?.disease ?? "—"}
                </td>
                <td className="px-4 py-3 text-gray-700">
                  {item.active_payload?.classification ?? "—"}
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
                  {item.current_best_confidence != null
                    ? `${(item.current_best_confidence * 100).toFixed(0)}%`
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
