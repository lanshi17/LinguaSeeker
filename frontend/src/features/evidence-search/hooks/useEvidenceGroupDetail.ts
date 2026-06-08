"use client";

import { useQuery } from "@tanstack/react-query";
import { getEvidenceGroupDetail } from "../services/evidenceSearch";

export function useEvidenceGroupDetail(groupId: string) {
  const query = useQuery({
    queryKey: ["evidence", "group-detail", groupId],
    queryFn: () => getEvidenceGroupDetail(groupId),
    enabled: !!groupId,
  });

  return {
    detail: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    refetch: query.refetch,
  };
}
