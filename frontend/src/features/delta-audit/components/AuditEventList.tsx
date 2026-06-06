"use client";

import { AuditEventRow } from "./AuditEventRow";
import { Spinner } from "@/components/ui/Spinner";
import { useAuditEvents } from "../hooks/useAuditEvents";

interface AuditEventListProps {
  evidenceId?: string;
  reviewerId?: string;
}

export function AuditEventList({ evidenceId, reviewerId }: AuditEventListProps) {
  const { data, isLoading, error } = useAuditEvents({
    evidenceId,
    reviewerId,
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }

  if (error) {
    return (
      <p className="py-10 text-center text-sm text-red-600">
        Failed to load audit events.
      </p>
    );
  }

  if (!data || data.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-gray-500">
        No audit events found.
      </p>
    );
  }

  return (
    <div>
      {data.map((event) => (
        <AuditEventRow key={event.audit_event_id} event={event} />
      ))}
    </div>
  );
}
