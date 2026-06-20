import { apiClient } from "@/lib/api/client";
import type {
  EvidenceSearchQuery,
  EvidenceSearchResponse,
  EvidenceGroupDetailResponse,
} from "@/features/evidence-search/types/evidenceSearch";

/**
 * Fetch all evidence search results for aggregation.
 * Uses a large page_size to get as many results as possible in one call.
 */
export async function fetchAllEvidence(
  query: EvidenceSearchQuery = {},
): Promise<EvidenceSearchResponse> {
  const params: Record<string, string | number> = {
    page: query.page ?? 1,
    page_size: query.page_size ?? 200,
  };
  if (query.gene) params.gene = query.gene;
  if (query.variant) params.variant = query.variant;
  if (query.disease) params.disease = query.disease;
  if (query.pmid) params.pmid = query.pmid;
  if (query.doi) params.doi = query.doi;

  const { data } = await apiClient.get<EvidenceSearchResponse>(
    "/evidence/search",
    { params },
  );
  return data;
}

/**
 * Fetch full detail for a single evidence group.
 */
export async function fetchEvidenceGroupDetail(
  groupId: string,
): Promise<EvidenceGroupDetailResponse> {
  const { data } = await apiClient.get<EvidenceGroupDetailResponse>(
    "/evidence/groups/detail",
    { params: { group_id: groupId } },
  );
  return data;
}
