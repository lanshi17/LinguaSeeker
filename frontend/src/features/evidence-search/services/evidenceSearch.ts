import type {
  EvidenceSearchQuery,
  EvidenceSearchResponse,
} from "../types/evidenceSearch";

// Backend GET /evidence/search not yet implemented — stubbed for frontend development.
// Replace with real apiClient.get call once the backend route exists.

export async function searchEvidence(
  _query: EvidenceSearchQuery,
): Promise<EvidenceSearchResponse> {
  return { items: [], total: 0 };
}
