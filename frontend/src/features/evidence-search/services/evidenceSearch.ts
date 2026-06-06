import { apiClient } from "@/lib/api/client";
import type {
  EvidenceSearchQuery,
  EvidenceSearchResponse,
} from "../types/evidenceSearch";

/**
 * Search evidence cards via the backend search index.
 * When called with empty query, returns all results (default list).
 */
export async function searchEvidence(
  query: EvidenceSearchQuery,
): Promise<EvidenceSearchResponse> {
  // Filter out empty string values so they don't override defaults.
  const params: Record<string, string | number> = {};
  if (query.gene) params.gene = query.gene;
  if (query.variant) params.variant = query.variant;
  if (query.disease) params.disease = query.disease;
  if (query.pmid) params.pmid = query.pmid;
  if (query.limit) params.limit = query.limit;

  const { data } = await apiClient.get<EvidenceSearchResponse>(
    "/evidence/search",
    { params },
  );
  return data;
}
