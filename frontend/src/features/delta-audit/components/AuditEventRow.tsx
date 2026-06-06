import { Badge } from "@/components/ui/Badge";
import type { ReviewAuditEventResponse } from "../types/deltaAudit";

interface AuditEventRowProps {
  event: ReviewAuditEventResponse;
}

export function AuditEventRow({ event }: AuditEventRowProps) {
  return (
    <div className="border-b border-gray-100 py-3">
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-400">
          {new Date(event.created_at).toLocaleString()}
        </span>
        <Badge variant="default">{event.target_type}</Badge>
        {event.old_status && event.new_status && (
          <span className="text-xs text-gray-600">
            {event.old_status} → {event.new_status}
          </span>
        )}
      </div>
      {event.deltas.length > 0 && (
        <div className="mt-1 space-y-0.5">
          {event.deltas.map((d, i) => (
            <p key={i} className="text-xs text-gray-500">
              <span className="font-medium">{d.field}:</span>{" "}
              {JSON.stringify(d.old_value)} → {JSON.stringify(d.new_value)}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
