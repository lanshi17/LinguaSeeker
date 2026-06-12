/**
 * Shared type primitives used across feature modules.
 */

/** Standard paginated API response wrapper. */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

/** API error shape returned by the backend. */
export interface ApiErrorResponse {
  detail?: string;
  message?: string;
  status_code?: number;
}

/** Processing run status shared across pipeline features. */
export type ProcessingStatus =
  | "pending"
  | "running"
  | "awaiting_review"
  | "completed"
  | "failed"
  | "skipped";

/** Phase identifier in the 3-phase pipeline. */
export type PhaseId = "phase_1" | "phase_2" | "phase_3";
