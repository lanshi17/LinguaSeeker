import { useQuery } from "@tanstack/react-query";
import { History, ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatRelative } from "@/lib/utils/format";
import { listAuditEvents } from "../services/evidenceCorrection";
import type { ReviewStatusValue } from "../types/evidenceSearch";

interface EvidenceAuditHistoryProps {
  sourceDocumentId: string;
}

const STATUS_VARIANT: Record<
  ReviewStatusValue,
  "default" | "success" | "warning" | "error"
> = {
  provisional: "default",
  approved: "success",
  corrected: "warning",
  rejected: "error",
};

export function EvidenceAuditHistory({
  sourceDocumentId,
}: EvidenceAuditHistoryProps) {
  const { data: events, isLoading } = useQuery({
    queryKey: ["delta-audit", sourceDocumentId],
    queryFn: () => listAuditEvents(undefined, 50),
    staleTime: 10_000,
    select: (all) =>
      all.filter(
        (e) =>
          all.length <= 50 ||
          true,
      ).slice(0, 20),
  });

  const relevantEvents = events?.filter(
    (e) => e.field_deltas.length > 0 || e.old_status !== e.new_status,
  );

  return (
    <section className="rounded-xl border border-gray-200 bg-white shadow-sm">
      <div className="border-b border-gray-100 px-5 py-3">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
          <History className="h-4 w-4 text-primary-700" />
          Correction history
        </h3>
      </div>
      <div className="p-4">
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="space-y-1.5">
                <Skeleton width="w-24" height="h-2" />
                <Skeleton width="w-full" height="h-3" />
              </div>
            ))}
          </div>
        ) : !relevantEvents || relevantEvents.length === 0 ? (
          <p className="text-xs text-gray-400">No corrections yet.</p>
        ) : (
          <ol className="space-y-3">
            {relevantEvents.map((event) => (
              <li key={event.review_event_id} className="relative pl-4">
                <div className="absolute left-0 top-1.5 h-2 w-2 rounded-full bg-primary-400" />
                <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-gray-500">
                  <span className="font-mono tabular-nums">
                    {formatRelative(event.created_at)}
                  </span>
                  {event.old_status && event.new_status && (
                    <span className="flex items-center gap-1">
                      <Badge
                        variant={
                          STATUS_VARIANT[event.old_status] ?? "default"
                        }
                      >
                        {event.old_status}
                      </Badge>
                      <ArrowRight className="h-3 w-3 text-gray-400" />
                      <Badge
                        variant={
                          STATUS_VARIANT[event.new_status] ?? "default"
                        }
                      >
                        {event.new_status}
                      </Badge>
                    </span>
                  )}
                </div>
                {event.field_deltas.length > 0 && (
                  <div className="mt-1 space-y-0.5">
                    {event.field_deltas.map((d) => (
                      <p key={d.field} className="text-[11px] text-gray-600">
                        <span className="font-medium">{d.field}</span>
                        {d.old_value && (
                          <span className="text-red-500 line-through">
                            {" "}
                            {String(d.old_value).slice(0, 40)}
                          </span>
                        )}
                        {d.new_value && (
                          <span className="text-emerald-700">
                            {" "}
                            → {String(d.new_value).slice(0, 40)}
                          </span>
                        )}
                      </p>
                    ))}
                  </div>
                )}
                {event.change_reason && (
                  <p className="mt-0.5 text-[10px] italic text-gray-400">
                    {event.change_reason}
                  </p>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}
