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
    queryFn: () => listAuditEvents(undefined, 50, sourceDocumentId),
    staleTime: 10_000,
    select: (all) => all.slice(0, 20),
  });

  const relevantEvents = events?.filter(
    (e) => e.field_deltas.length > 0 || e.old_status !== e.new_status,
  );

  return (
    <section style={{ borderRadius: 12, border: "1px solid #e5e7eb", backgroundColor: "#fff", boxShadow: "0 1px 2px rgba(0,0,0,0.05)" }}>
      <div style={{ borderBottom: "1px solid #f3f4f6", padding: "12px 20px" }}>
        <h3 style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 600, color: "#111827", margin: 0 }}>
          <History style={{ width: 16, height: 16, color: "var(--color-primary-700)" }} />
          Correction history
        </h3>
      </div>
      <div style={{ padding: 16 }}>
        {isLoading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <Skeleton style={{ width: 96, height: 8 }} />
                <Skeleton style={{ width: "100%", height: 12 }} />
              </div>
            ))}
          </div>
        ) : !relevantEvents || relevantEvents.length === 0 ? (
          <p style={{ fontSize: 12, color: "#9ca3af", margin: 0 }}>No corrections yet.</p>
        ) : (
          <ol style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 12 }}>
            {relevantEvents.map((event) => (
              <li key={event.review_event_id} style={{ position: "relative", paddingLeft: 16 }}>
                <div style={{
                  position: "absolute",
                  left: 0,
                  top: 6,
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  backgroundColor: "var(--color-primary-400)",
                }} />
                <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6, fontSize: 11, color: "#6b7280" }}>
                  <span style={{ fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums" }}>
                    {formatRelative(event.created_at)}
                  </span>
                  {event.old_status && event.new_status && (
                    <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      <Badge
                        variant={
                          STATUS_VARIANT[event.old_status] ?? "default"
                        }
                      >
                        {event.old_status}
                      </Badge>
                      <ArrowRight style={{ width: 12, height: 12, color: "#9ca3af" }} />
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
                  <div style={{ marginTop: 4, display: "flex", flexDirection: "column", gap: 2 }}>
                    {event.field_deltas.map((d) => (
                      <p key={d.field} style={{ fontSize: 11, color: "#4b5563", margin: 0 }}>
                        <span style={{ fontWeight: 500 }}>{d.field}</span>
                        {d.old_value && (
                          <span style={{ color: "#ef4444", textDecoration: "line-through" }}>
                            {" "}
                            {String(d.old_value).slice(0, 40)}
                          </span>
                        )}
                        {d.new_value && (
                          <span style={{ color: "var(--color-success-700)" }}>
                            {" "}
                            → {String(d.new_value).slice(0, 40)}
                          </span>
                        )}
                      </p>
                    ))}
                  </div>
                )}
                {event.change_reason && (
                  <p style={{ marginTop: 2, fontSize: 10, fontStyle: "italic", color: "#9ca3af" }}>
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
