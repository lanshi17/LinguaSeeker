import { apiClient } from "@/lib/api/client";
import type { ReviewAuditEventResponse } from "../types/deltaAudit";

interface AuditFilters {
  canonical_evidence_id?: string;
  reviewer_id?: string;
}

export async function listAuditEvents(
  filters?: AuditFilters,
): Promise<ReviewAuditEventResponse[]> {
  const { data } = await apiClient.get<ReviewAuditEventResponse[]>(
    "/delta-audit/",
    { params: filters },
  );
  return data;
}
