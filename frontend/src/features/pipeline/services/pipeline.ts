import { ApiError } from "@/lib/api/error";
import { apiClient } from "@/lib/api/client";
import type {
  PipelineRunListResponse,
  PipelineRunRequest,
  PipelineRunResponse,
  PipelineStatusResponse,
} from "../types/pipeline";

/** Start a new pipeline run (POST /pipeline/run). */
export async function startPipelineRun(
  body: PipelineRunRequest,
): Promise<PipelineRunResponse> {
  const { data } = await apiClient.post<PipelineRunResponse>(
    "/pipeline/run",
    body,
  );
  return data;
}

/** Get pipeline run status (GET /pipeline/runs/{id}/status). */
export async function getPipelineStatus(
  runId: string,
): Promise<PipelineStatusResponse> {
  const { data } = await apiClient.get<PipelineStatusResponse>(
    `/pipeline/runs/${runId}/status`,
  );
  return data;
}

/**
 * List all pipeline runs (GET /pipeline/runs).
 * Tolerates 404 / 501 from backends that have not yet shipped the list
 * endpoint — returns an empty list so the UI can render an empty state
 * rather than an error.
 */
export async function listPipelineRuns(): Promise<PipelineRunListResponse> {
  try {
    const { data } = await apiClient.get<PipelineRunListResponse>(
      "/pipeline/runs",
    );
    return data;
  } catch (err) {
    if (err instanceof ApiError) {
      if (err.status === 404 || err.status === 501) {
        return { items: [], total: 0 };
      }
    }
    throw err;
  }
}
