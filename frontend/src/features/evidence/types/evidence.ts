/** Review status for an evidence card. */
export type ReviewStatus =
  | "provisional"
  | "approved"
  | "corrected"
  | "rejected";

/** PATCH /evidence/{id} request body. */
export interface EvidencePatchRequest {
  status?: ReviewStatus;
  field_updates?: Record<string, unknown>;
  comment?: string;
}

/** PATCH /evidence/{id} response body. */
export interface PatchResultResponse {
  canonical_evidence_id: string;
  status: ReviewStatus;
  audit_event_id: string;
}
