import { apiClient } from "@/lib/api/client";
import type {
  EvidenceGroupDetailResponse,
  EvidenceSearchQuery,
  EvidenceSearchResponse,
} from "@/features/evidence-search/types/evidenceSearch";

export async function searchEvidence(
  query: EvidenceSearchQuery,
  defaults?: { page?: number; page_size?: number },
): Promise<EvidenceSearchResponse> {
  const params: Record<string, string | number> = {};
  if (defaults?.page !== undefined) params.page = defaults.page;
  if (defaults?.page_size !== undefined) params.page_size = defaults.page_size;
  if (query.gene) params.gene = query.gene;
  if (query.variant) params.variant = query.variant;
  if (query.disease) params.disease = query.disease;
  if (query.pmid) params.pmid = query.pmid;
  if (query.doi) params.doi = query.doi;
  if (query.page) params.page = query.page;
  if (query.page_size) params.page_size = query.page_size;

  const { data } = await apiClient.get<EvidenceSearchResponse>(
    "/evidence/search",
    { params },
  );
  return data;
}

export async function getEvidenceGroupDetail(
  groupId: string,
): Promise<EvidenceGroupDetailResponse> {
  const { data } = await apiClient.get<EvidenceGroupDetailResponse>(
    "/evidence/groups/detail",
    { params: { group_id: groupId } },
  );
  return data;
}
