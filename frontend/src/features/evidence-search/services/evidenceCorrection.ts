import { apiClient } from "@/lib/api/client";
import type {
  EvidencePatchRequest,
  PatchResultResponse,
  ReviewAuditEventResponse,
} from "../types/evidenceSearch";

export async function patchEvidence(
  canonicalEvidenceId: string,
  body: EvidencePatchRequest,
): Promise<PatchResultResponse> {
  const { data } = await apiClient.patch<PatchResultResponse>(
    `/evidence/${canonicalEvidenceId}`,
    body,
  );
  return data;
}

export async function listAuditEvents(
  canonicalEvidenceId?: string,
  limit = 50,
): Promise<ReviewAuditEventResponse[]> {
  const params: Record<string, string | number> = { limit };
  if (canonicalEvidenceId) {
    params.canonical_evidence_id = canonicalEvidenceId;
  }
  const { data } = await apiClient.get<ReviewAuditEventResponse[]>(
    "/delta-audit/",
    { params },
  );
  return data;
}
