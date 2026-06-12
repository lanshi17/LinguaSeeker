"use client";

import { useQuery } from "@tanstack/react-query";
import { listPipelineRuns } from "../services/pipeline";
import type { PipelineRunListResponse } from "../types/pipeline";

/**
 * List every known pipeline run.
 *
 * Polls every 5s so a freshly started run appears in the history list without
 * a manual refresh. Service tolerates 404 from backends that have not yet
 * shipped the endpoint, returning an empty list.
 */
export function usePipelineRuns() {
  return useQuery<PipelineRunListResponse>({
    queryKey: ["pipeline", "runs"],
    queryFn: listPipelineRuns,
    refetchInterval: 5_000,
    staleTime: 2_000,
  });
}
