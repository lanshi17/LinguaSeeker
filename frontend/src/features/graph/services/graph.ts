import type { GraphSearchRequest, EvidenceSearchResponse } from "../types/graph";

// Backend endpoints not yet implemented — stubbed to keep the UI functional.
// Replace with real apiClient calls once the backend routes exist.

export async function searchEvidenceGraph(
  _body: GraphSearchRequest,
): Promise<EvidenceSearchResponse> {
  return { nodes: [], edges: [], evidence_records: [] };
}

export async function getGraphStats(): Promise<Record<string, unknown>> {
  return {};
}

export async function resyncDocument(_documentId: string): Promise<void> {
  // no-op
}
