/** Query parameters for listing audit events. */
export interface AuditEventQuery {
  canonical_evidence_id?: string;
  source_document_id?: string;
  reviewer_id?: string;
  limit?: number;
}

/** A single field-level change within an audit event. */
export interface DeltaEntry {
  field: string;
  old_value: string | string[] | null;
  new_value: string | string[] | null;
}

/** Review status values for evidence items. */
export type ReviewStatusValue =
  | "provisional"
  | "approved"
  | "corrected"
  | "rejected";

/** A review audit event returned by the API. */
export interface ReviewAuditEventResponse {
  review_event_id: string;
  canonical_evidence_id: string;
  reviewer_id: string | null;
  target_type: string;
  old_status: ReviewStatusValue | null;
  new_status: ReviewStatusValue | null;
  field_deltas: DeltaEntry[];
  change_reason: string | null;
  created_at: string;
}
