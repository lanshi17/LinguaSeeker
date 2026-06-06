"use client";

import { useMutation } from "@tanstack/react-query";
import { startPipelineRun } from "../services/pipeline";
import type { PipelineRunRequest, PipelineRunResponse } from "../types/pipeline";

/** Mutation hook to start a new pipeline run. */
export function usePipelineRun() {
  return useMutation<PipelineRunResponse, Error, PipelineRunRequest>({
    mutationFn: startPipelineRun,
  });
}
