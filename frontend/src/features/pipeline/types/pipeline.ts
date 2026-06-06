import type { ProcessingStatus, PhaseId } from "@/lib/types/common";

/** POST /pipeline/run request body. */
export interface PipelineRunRequest {
  source_type: "local" | "online";
  mode: "full" | "phase";
  /** Base64-encoded file content for local uploads. */
  file_content?: string;
  filename?: string;
  /** Online query string for literature search. */
  query?: string;
  identifiers?: string[];
  /** Target phase when mode is "phase". */
  target_phase?: PhaseId;
}

/** POST /pipeline/run response body. */
export interface PipelineRunResponse {
  processing_run_id: string;
  source_document_id: string;
  status: string;
  status_url: string;
}

/** Per-phase status detail (matches backend PhaseStatusResponse). */
export interface PhaseStatus {
  status: ProcessingStatus;
  started_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
  error?: Record<string, unknown> | null;
  summary?: Record<string, unknown> | null;
}

/** GET /pipeline/runs/{id}/status response body. */
export interface PipelineStatusResponse {
  processing_run_id: string;
  source_document_id: string;
  pipeline_status: ProcessingStatus;
  current_phase?: string | null;
  skip_phase_3_reason?: string | null;
  /** Dict keyed by phase_id ("phase_1", "phase_2", "phase_3"). */
  phases: Record<string, PhaseStatus>;
  error_message?: string | null;
  error_phase?: number | null;
  started_at?: string | null;
  completed_at?: string | null;
}

/** Projected step for the PhaseTimeline component. */
export interface PhaseTimelineStep {
  phaseId: string;
  label: string;
  status: ProcessingStatus;
  duration?: number | null;
}
