"use client";

import { Badge } from "@/components/ui/Badge";
import type { EvidenceSearchResult } from "../types/evidenceSearch";

interface EvidenceResultsTableProps {
  results: EvidenceSearchResult[];
  total?: number;
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
}: EvidenceResultsTableProps) {
  if (results.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-gray-500">
        No evidence found. Try a different search.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {total !== undefined && (
        <p className="text-sm text-gray-500">
          {total} result{total !== 1 ? "s" : ""} found
        </p>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-xs font-medium uppercase text-gray-500">
              <th className="px-3 py-2">Gene</th>
              <th className="px-3 py-2">Variant</th>
              <th className="px-3 py-2">Disease</th>
              <th className="px-3 py-2">Classification</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">PMID</th>
              <th className="px-3 py-2">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {results.map((item) => (
              <tr
                key={item.canonical_evidence_id}
                className="cursor-pointer border-b border-gray-100 transition-colors hover:bg-gray-50"
              >
                <td className="px-3 py-2 font-medium text-gray-900">
                  {item.active_payload?.gene ?? item.gene_ids?.[0] ?? "—"}
                </td>
                <td className="px-3 py-2 text-gray-700">
                  {item.active_payload?.variant ??
                    item.variant_ids?.[0] ??
                    "—"}
                </td>
                <td className="px-3 py-2 text-gray-700">
                  {item.active_payload?.disease ?? "—"}
                </td>
                <td className="px-3 py-2 text-gray-700">
                  {item.active_payload?.classification ?? "—"}
                </td>
                <td className="px-3 py-2">
                  <Badge
                    variant={
                      STATUS_VARIANT[item.review_status ?? ""] ?? "default"
                    }
                  >
                    {item.review_status ?? "unknown"}
                  </Badge>
                </td>
                <td className="px-3 py-2 text-gray-500">
                  {item.pmid ?? "—"}
                </td>
                <td className="px-3 py-2 text-gray-500">
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
