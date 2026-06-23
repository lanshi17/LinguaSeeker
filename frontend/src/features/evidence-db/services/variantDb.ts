import type {
  EvidenceSearchQuery,
  EvidenceSearchResponse,
  EvidenceGroupDetailResponse,
} from "@/features/evidence-search/types/evidenceSearch";
import {
  searchEvidence as _searchEvidence,
  getEvidenceGroupDetail,
} from "@/api/evidence";

/**
 * Fetch all evidence search results for aggregation.
 * Uses a large page_size to get as many results as possible in one call.
 */
export async function fetchAllEvidence(
  query: EvidenceSearchQuery = {},
): Promise<EvidenceSearchResponse> {
  return _searchEvidence(query, { page: 1, page_size: 1000 });
}

export { getEvidenceGroupDetail as fetchEvidenceGroupDetail };
