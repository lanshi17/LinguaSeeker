"use client";

import { useQuery } from "@tanstack/react-query";
import { listAuditEvents } from "../services/deltaAudit";

interface UseAuditEventsOptions {
  evidenceId?: string;
  reviewerId?: string;
  enabled?: boolean;
}

export function useAuditEvents({
  evidenceId,
  reviewerId,
  enabled = true,
}: UseAuditEventsOptions = {}) {
  return useQuery({
    queryKey: ["delta-audit", { evidenceId, reviewerId }],
    queryFn: () =>
      listAuditEvents({
        canonical_evidence_id: evidenceId,
        reviewer_id: reviewerId,
      }),
    enabled,
  });
}
