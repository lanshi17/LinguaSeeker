"use client";

import { useQuery, type UseQueryOptions } from "@tanstack/react-query";

interface UsePollingOptions<T> extends Omit<UseQueryOptions<T>, "queryKey" | "queryFn"> {
  /** Polling interval in ms. Default 3000. Pass false to disable. */
  interval?: number | false;
}

/**
 * Generic polling hook built on TanStack Query.
 *
 * Features prefer `useQuery` with `refetchInterval` directly.
 * This hook is for cases where a simple polling wrapper is cleaner.
 */
export function usePolling<T>(
  queryKey: string[],
  queryFn: () => Promise<T>,
  options: UsePollingOptions<T> = {},
) {
  const { interval = 3000, ...rest } = options;

  return useQuery<T>({
    queryKey,
    queryFn,
    refetchInterval: interval,
    ...rest,
  });
}
