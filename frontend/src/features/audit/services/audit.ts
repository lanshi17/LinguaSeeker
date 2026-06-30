import { apiClient } from "@/lib/api/client";
import type { AuditEventQuery } from "../types/audit";
import type { ReviewAuditEventResponse } from "@/lib/types/evidence";

/** List review audit events with optional filters. */
export async function listAuditEvents(
  query: AuditEventQuery = {},
): Promise<ReviewAuditEventResponse[]> {
  const params: Record<string, string | number> = { limit: query.limit ?? 200 };
  if (query.canonical_evidence_id) {
    params.canonical_evidence_id = query.canonical_evidence_id;
  }
  if (query.source_document_id) {
    params.source_document_id = query.source_document_id;
  }
  if (query.reviewer_id) {
    params.reviewer_id = query.reviewer_id;
  }
  const { data } = await apiClient.get<ReviewAuditEventResponse[]>(
    "/delta-audit/",
    { params },
  );
  return data;
}
