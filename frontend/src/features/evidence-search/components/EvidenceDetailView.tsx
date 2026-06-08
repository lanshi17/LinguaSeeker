"use client";

import { useMemo, useState } from "react";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { useEvidenceGroupDetail } from "../hooks/useEvidenceGroupDetail";
import { EvidenceHighlightText } from "./EvidenceHighlightText";

interface EvidenceDetailViewProps {
  groupId: string;
}

const STATUS_VARIANT: Record<string, "default" | "success" | "warning" | "error" | "info"> = {
  provisional: "default",
  approved: "success",
  corrected: "warning",
  rejected: "error",
};

function countEntries(record: Record<string, number>) {
  return Object.entries(record).sort(([a], [b]) => a.localeCompare(b));
}

export function EvidenceDetailView({ groupId }: EvidenceDetailViewProps) {
  const { detail, isLoading, error } = useEvidenceGroupDetail(groupId);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);

  const selectedTrace = useMemo(() => {
    if (!detail) return null;
    if (selectedEvidenceId) {
      const selectedItem = detail.items.find(
        (item) => item.canonical_evidence_id === selectedEvidenceId,
      );
      if (selectedItem) {
        return (
          detail.traces.find((trace) => trace.field_id === selectedItem.field_id) ??
          detail.traces[0] ??
          null
        );
      }
    }
    return detail.traces[0] ?? null;
  }, [detail, selectedEvidenceId]);

  if (isLoading) {
    return <div className="flex justify-center py-12"><Spinner /></div>;
  }

  if (error || !detail) {
    return (
      <Card className="py-10 text-center">
        <p className="text-sm text-red-600">Failed to load evidence detail.</p>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Link href="/evidence" className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900">
        <ArrowLeft className="h-4 w-4" />
        Back to evidence
      </Link>

      <Card>
        <div className="grid gap-4 md:grid-cols-4">
          <div>
            <p className="text-xs font-medium uppercase text-gray-400">Gene</p>
            <p className="mt-1 text-sm font-medium text-gray-900">{detail.gene ?? "—"}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase text-gray-400">Variant</p>
            <p className="mt-1 text-sm text-gray-700">{detail.variant ?? "—"}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase text-gray-400">Disease</p>
            <p className="mt-1 text-sm text-gray-700">{detail.disease ?? "—"}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase text-gray-400">Classification</p>
            <p className="mt-1 text-sm text-gray-700">{detail.classification ?? "—"}</p>
          </div>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <div className="space-y-6">
          <Card>
            <h3 className="text-sm font-medium text-gray-900">Evidence Distribution</h3>
            <div className="mt-4 space-y-4">
              <section>
                <p className="mb-2 text-xs font-medium uppercase text-gray-400">Category</p>
                <div className="flex flex-wrap gap-2">
                  {countEntries(detail.distribution.by_category).map(([key, count]) => (
                    <Badge key={key} variant="info">{key}: {count}</Badge>
                  ))}
                </div>
              </section>
              <section>
                <p className="mb-2 text-xs font-medium uppercase text-gray-400">Status</p>
                <div className="flex flex-wrap gap-2">
                  {countEntries(detail.distribution.by_status).map(([key, count]) => (
                    <Badge key={key} variant={STATUS_VARIANT[key] ?? "default"}>{key}: {count}</Badge>
                  ))}
                </div>
              </section>
              <section>
                <p className="mb-2 text-xs font-medium uppercase text-gray-400">Track</p>
                <div className="flex flex-wrap gap-2">
                  {countEntries(detail.distribution.by_track).map(([key, count]) => (
                    <Badge key={key} variant="default">{key}: {count}</Badge>
                  ))}
                </div>
              </section>
            </div>
          </Card>

          <Card>
            <h3 className="text-sm font-medium text-gray-900">Evidence Items</h3>
            <div className="mt-3 max-h-[520px] space-y-2 overflow-y-auto pr-1">
              {detail.items.map((item) => {
                const active = item.field_id === (selectedTrace?.field_id) && item.canonical_evidence_id === (selectedEvidenceId ?? selectedTrace?.canonical_evidence_id);
                return (
                  <button
                    key={item.canonical_evidence_id}
                    onClick={() => setSelectedEvidenceId(item.canonical_evidence_id)}
                    className={
                      active
                        ? "w-full rounded-md border border-primary-200 bg-primary-50 p-3 text-left"
                        : "w-full rounded-md border border-gray-200 bg-white p-3 text-left hover:bg-gray-50"
                    }
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-medium text-gray-500">{item.field_id}</span>
                      <Badge variant={STATUS_VARIANT[item.review_status] ?? "default"}>{item.review_status}</Badge>
                    </div>
                    <p className="mt-1 line-clamp-2 text-sm text-gray-800">{item.value ?? "—"}</p>
                  </button>
                );
              })}
            </div>
          </Card>
        </div>

        <Card>
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-gray-900">Evidence Chain Traceability</h3>
              <p className="mt-1 text-xs text-gray-500">{selectedTrace?.field_id ?? "No evidence selected"}</p>
            </div>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <section>
              <h4 className="mb-2 text-xs font-medium uppercase text-gray-400">Original</h4>
              <EvidenceHighlightText highlight={selectedTrace?.original} active />
            </section>
            <section>
              <h4 className="mb-2 text-xs font-medium uppercase text-gray-400">Translated</h4>
              <EvidenceHighlightText highlight={selectedTrace?.translated} active />
            </section>
          </div>
        </Card>
      </div>
    </div>
  );
}
