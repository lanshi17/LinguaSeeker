export type ReviewStatusValue =
  | "provisional"
  | "approved"
  | "corrected"
  | "rejected";

export interface DeltaEntry {
  field: string;
  old_value: string | string[] | null;
  new_value: string | string[] | null;
}

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
