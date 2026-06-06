import { apiClient } from "@/lib/api/client";
import type { GraphSearchRequest, EvidenceSearchResponse } from "../types/graph";

export async function searchEvidenceGraph(
  body: GraphSearchRequest,
): Promise<EvidenceSearchResponse> {
  const { data } = await apiClient.post<EvidenceSearchResponse>(
    "/evidence/search",
    body,
  );
  return data;
}

export async function getGraphStats(): Promise<Record<string, unknown>> {
  const { data } = await apiClient.get("/evidence/graph/stats");
  return data;
}

export async function resyncDocument(documentId: string): Promise<void> {
  await apiClient.post(`/evidence/sync/document/${documentId}`);
}
