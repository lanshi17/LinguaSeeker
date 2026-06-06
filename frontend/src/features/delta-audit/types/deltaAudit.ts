/** Target type for an audit event. */
export type TargetType = "evidence" | "entity";

/** Field-level change entry in an audit event. */
export interface DeltaEntry {
  field: string;
  old_value: unknown;
  new_value: unknown;
}

/** GET /delta-audit/ response item. */
export interface ReviewAuditEventResponse {
  audit_event_id: string;
  target_type: TargetType;
  target_id: string;
  reviewer_id?: string;
  old_status?: string;
  new_status?: string;
  deltas: DeltaEntry[];
  created_at: string;
}
