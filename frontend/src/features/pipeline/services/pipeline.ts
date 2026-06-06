import { apiClient } from "@/lib/api/client";
import type {
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
