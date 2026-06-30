/** Query parameters for listing audit events. */
export interface AuditEventQuery {
  canonical_evidence_id?: string;
  source_document_id?: string;
  reviewer_id?: string;
  limit?: number;
}

export type { DeltaEntry, ReviewStatusValue, ReviewAuditEventResponse } from "@/lib/types/evidence";
