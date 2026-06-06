import { apiClient } from "@/lib/api/client";
import type {
  LiteratureCandidateSearchRequest,
  LiteratureCandidateSearchResponse,
} from "../types/literature";

export async function searchCandidates(
  body: LiteratureCandidateSearchRequest,
): Promise<LiteratureCandidateSearchResponse> {
  const { data } = await apiClient.post<LiteratureCandidateSearchResponse>(
    "/tasks/requests/literature/candidates",
    body,
  );
  return data;
}

export async function submitSelection(
  candidateIds: string[],
): Promise<void> {
  await apiClient.post("/tasks/requests/literature/submit", {
    candidate_ids: candidateIds,
  });
}
