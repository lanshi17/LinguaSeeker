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
  status_url: string;
}

/** Per-phase status detail. */
export interface PhaseStatus {
  phase_id: PhaseId;
  status: ProcessingStatus;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  error?: string;
  summary?: string;
}

/** GET /pipeline/runs/{id}/status response body. */
export interface PipelineStatusResponse {
  processing_run_id: string;
  pipeline_status: ProcessingStatus;
  phases: PhaseStatus[];
  created_at: string;
  updated_at: string;
}

/** Projected step for the PhaseTimeline component. */
export interface PhaseTimelineStep {
  phaseId: PhaseId;
  label: string;
  status: ProcessingStatus;
  duration?: number;
}
