import { apiClient, readCachedApiResponse } from "@/lib/api/client";
import type {
  EvidenceGroupDetailResponse,
  EvidenceSearchQuery,
  EvidenceSearchResponse,
} from "@/features/evidence-search/types/evidenceSearch";

interface EvidenceSearchRequestOptions {
  cacheScope?: string;
  refresh?: boolean;
}

function buildEvidenceSearchParams(
  query: EvidenceSearchQuery,
  defaults?: { page?: number; page_size?: number },
): Record<string, string | number> {
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
  return params;
}

export async function searchEvidence(
  query: EvidenceSearchQuery,
  defaults?: { page?: number; page_size?: number },
  options: EvidenceSearchRequestOptions = {},
): Promise<EvidenceSearchResponse> {
  const { data } = await apiClient.get<EvidenceSearchResponse>(
    "/evidence/search",
    {
      headers: options.refresh ? { "Cache-Control": "no-cache" } : undefined,
      params: buildEvidenceSearchParams(query, defaults),
      responseCache: { scope: options.cacheScope },
    },
  );
  return data;
}

export function readCachedEvidenceSearch(
  query: EvidenceSearchQuery,
  defaults?: { page?: number; page_size?: number },
  cacheScope?: string,
): EvidenceSearchResponse | undefined {
  return readCachedApiResponse<EvidenceSearchResponse>(
    "/evidence/search",
    buildEvidenceSearchParams(query, defaults),
    cacheScope,
  );
}

export async function getEvidenceGroupDetail(
  groupId?: string,
  sourceDocumentId?: string,
): Promise<EvidenceGroupDetailResponse> {
  const params: Record<string, string> = {};
  if (groupId) {
    params.group_id = groupId;
  }
  if (sourceDocumentId) {
    params.source_document_id = sourceDocumentId;
  }
  const { data } = await apiClient.get<EvidenceGroupDetailResponse>(
    "/evidence/groups/detail",
    { params },
  );
  return data;
}
