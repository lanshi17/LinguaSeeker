import { useQuery } from "@tanstack/react-query";
import { listAuditEvents } from "../services/audit";
import type { AuditEventQuery } from "../types/audit";

/**
 * Fetch review audit events with optional filters.
 *
 * Polls every 10s so newly recorded events appear without manual refresh.
 */
export function useAuditEvents(query: AuditEventQuery = {}) {
  return useQuery({
    queryKey: ["audit", "events", query.canonical_evidence_id, query.reviewer_id, query.limit],
    queryFn: () => listAuditEvents(query),
    refetchInterval: 10_000,
    staleTime: 5_000,
  });
}
