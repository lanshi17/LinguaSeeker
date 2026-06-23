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

/**
 * Fetch evidence group detail, optionally scoped to a specific source document.
 *
 * ``group_id`` values are NOT unique per source document — the same
 * ``gene=<G>|variant=<V>`` string can appear across many papers.  Passing
 * ``sourceDocumentId`` ensures the response contains only items from that
 * particular document.
 */
export async function fetchEvidenceGroupDetail(
  groupId: string,
  sourceDocumentId?: string,
): Promise<EvidenceGroupDetailResponse> {
  return getEvidenceGroupDetail(groupId, sourceDocumentId);
}
