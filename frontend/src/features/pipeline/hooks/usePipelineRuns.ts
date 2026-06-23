
import { useQuery } from "@tanstack/react-query";
import { listPipelineRuns } from "../services/pipeline";
import type { PipelineRunListResponse } from "../types/pipeline";

export interface UsePipelineRunsParams {
  page?: number;
  pageSize?: number;
  status?: string;
  search?: string;
}

/**
 * Fetch pipeline runs with server-side pagination, filtering and search.
 *
 * Polls every 5s so a freshly started run appears in the history list without
 * a manual refresh.
 */
export function usePipelineRuns(params: UsePipelineRunsParams = {}) {
  const { page = 1, pageSize = 20, status, search } = params;

  return useQuery<PipelineRunListResponse>({
    queryKey: ["pipeline", "runs", page, pageSize, status, search],
    queryFn: () =>
      listPipelineRuns({
        limit: pageSize,
        offset: (page - 1) * pageSize,
        status: status || undefined,
        search: search || undefined,
      }),
    refetchInterval: 5_000,
    staleTime: 2_000,
    placeholderData: (prev) => prev,
  });
}
