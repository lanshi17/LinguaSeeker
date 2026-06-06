import { apiClient } from "@/lib/api/client";
import type { EvidencePatchRequest, PatchResultResponse } from "../types/evidence";

export async function patchEvidence(
  evidenceId: string,
  body: EvidencePatchRequest,
): Promise<PatchResultResponse> {
  const { data } = await apiClient.patch<PatchResultResponse>(
    `/evidence/${evidenceId}`,
    body,
  );
  return data;
}
