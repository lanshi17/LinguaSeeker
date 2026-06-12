import type { ProcessingStatus, PhaseId } from "@/lib/types/common";

export type { ProcessingStatus, PhaseId };

/** POST /pipeline/run request body. */
export interface PipelineRunRequest {
  source_type: "local" | "online";
  mode: "full" | "phase";
  /** Base64-encoded file content for local uploads. */
  content_base64?: string;
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

/** Per-phase sub-node entry reported by backend (e.g. one literature provider, one LLM step). */
export interface PhaseNode {
  /** Stable identifier for the sub-node within a phase. */
  node_id: string;
  /** Human label, e.g. "Crossref fetch", "PubMed translation". */
  label: string;
  status: ProcessingStatus;
  /** Optional sub-step progress 0..1. */
  progress?: number | null;
  started_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
  /** Counter metric — documents fetched, items extracted, etc. */
  count?: number | null;
  /** Free-form metric values (e.g. {"tokens": 1234, "items": 8}). */
  metrics?: Record<string, number | string> | null;
  error?: Record<string, unknown> | string | null;
}

/** Per-phase status detail (matches backend PhaseStatusResponse). */
export interface PhaseStatus {
  status: ProcessingStatus;
  started_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
  error?: Record<string, unknown> | null;
  summary?: Record<string, unknown> | null;
  /** Backend may surface fine-grained sub-nodes; UI degrades gracefully when absent. */
  nodes?: PhaseNode[];
  /** Aggregated count surfaced by the backend for the phase, e.g. documents_collected. */
  count?: number | null;
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
  /** Total elapsed seconds, backend-computed when available. */
  elapsed_seconds?: number | null;
  /** Optional human title — e.g. original query or filename. */
  title?: string | null;
}

/** Compact summary used in the run-history list. */
export interface PipelineRunSummary {
  processing_run_id: string;
  pipeline_status: ProcessingStatus;
  title?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  elapsed_seconds?: number | null;
  current_phase?: string | null;
  /** Number of phases that reached a terminal status — drives the inline progress bar. */
  completed_phases?: number;
  /** Total phases known for this run. */
  total_phases?: number;
}

/** GET /pipeline/runs response body. */
export interface PipelineRunListResponse {
  items: PipelineRunSummary[];
  total: number;
}

/** Projected step for the PhaseTimeline component. */
export interface PhaseTimelineStep {
  phaseId: string;
  label: string;
  status: ProcessingStatus;
  duration?: number | null;
}
