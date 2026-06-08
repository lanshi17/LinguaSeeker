"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getPipelineStatus } from "../services/pipeline";
import type { PipelineStatusResponse } from "../types/pipeline";

const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled", "awaiting_review"]);
const MAX_POLL_MS = 30 * 60 * 1000; // 30 min safety cap

/**
 * Poll pipeline run status.
 *
 * Polls every 2 seconds while the pipeline is running or queued.
 * Stops polling when the status reaches a terminal state or after 30 minutes.
 */
export function usePipelineStatus(runId: string) {
  const [startedAt] = useState(() => Date.now());

  return useQuery<PipelineStatusResponse>({
    queryKey: ["pipeline", "status", runId],
    queryFn: () => getPipelineStatus(runId),
    refetchInterval: (query) => {
      const status = query.state.data?.pipeline_status;
      if (TERMINAL_STATUSES.has(status ?? "") || Date.now() - startedAt > MAX_POLL_MS) {
        return false;
      }
      return 2000;
    },
  });
}
