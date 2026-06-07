import { apiClient } from "@/lib/api/client";
import type {
  EvidenceSearchQuery,
  EvidenceSearchResponse,
} from "../types/evidenceSearch";

/**
 * Search evidence cards via the frontend search index.
 *
 * GET /api/v1/evidence/search
 * - No filters → returns all evidence (default list, ordered by PMID)
 * - With filters → returns matching evidence
 */
export async function searchEvidence(
  query: EvidenceSearchQuery,
): Promise<EvidenceSearchResponse> {
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
