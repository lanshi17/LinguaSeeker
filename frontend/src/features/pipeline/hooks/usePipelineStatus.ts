"use client";

import { useQuery } from "@tanstack/react-query";
import { getPipelineStatus } from "../services/pipeline";
import type { PipelineStatusResponse } from "../types/pipeline";

/**
 * Poll pipeline run status.
 *
 * Polls every 2 seconds while the pipeline is running or queued.
 * Stops polling when the status reaches a terminal state (completed / failed / cancelled).
 */
export function usePipelineStatus(runId: string) {
  return useQuery<PipelineStatusResponse>({
    queryKey: ["pipeline", "status", runId],
    queryFn: () => getPipelineStatus(runId),
    refetchInterval: (query) => {
      const status = query.state.data?.pipeline_status;
      if (status === "completed" || status === "failed" || status === "cancelled") {
        return false;
      }
      return 2000;
    },
  });
}
