"use client";

import { useQuery } from "@tanstack/react-query";
import { getDashboardSummary } from "../services/dashboard";

/**
 * React Query hook for dashboard summary data.
 * Refetches every 30 seconds to keep stats fresh.
 */
export function useDashboard() {
  const query = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: getDashboardSummary,
    refetchInterval: 30_000,
  });

  return {
    summary: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}
