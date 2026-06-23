
import { useQuery } from "@tanstack/react-query";
import { getEvidenceGroupDetail } from "../services/evidenceSearch";

export function useEvidenceGroupDetail(groupId?: string, sourceDocumentId?: string) {
  const query = useQuery({
    queryKey: ["evidence", "group-detail", groupId, sourceDocumentId],
    queryFn: () => getEvidenceGroupDetail(groupId, sourceDocumentId),
    enabled: !!groupId || !!sourceDocumentId,
  });

  return {
    detail: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    refetch: query.refetch,
  };
}
