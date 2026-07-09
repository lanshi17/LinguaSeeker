import type {
  EvidenceGroupItem,
  EvidencePatchRequest,
  ReviewStatusValue,
} from "@/features/evidence-search/types/evidenceSearch";
import { cardFieldForFieldId } from "@/features/evidence-search/utils/fieldAssignment";

export { cardFieldForFieldId } from "@/features/evidence-search/utils/fieldAssignment";

interface BuildReviewPatchOperationsArgs {
  items: EvidenceGroupItem[];
  editedFields: Record<string, string>;
  newStatus: ReviewStatusValue;
  changeReason: string;
}

export interface ReviewPatchOperation {
  canonicalEvidenceId: string;
  body: EvidencePatchRequest;
}

export function buildReviewPatchOperations({
  items,
  editedFields,
  newStatus,
  changeReason,
}: BuildReviewPatchOperationsArgs): ReviewPatchOperation[] {
  const trimmedReason = changeReason.trim();
  const candidates = items
    .filter((item) => item.canonical_evidence_id)
    .map((item) => {
      const fields: Record<string, string> = {};
      const editedValue = editedFields[item.field_id]?.trim();
      const cardField = cardFieldForFieldId(item.field_id);

      if (editedValue && editedValue !== (item.value ?? "") && cardField) {
        fields[cardField] = editedValue;
      }

      return { item, fields };
    });

  const hasFieldCorrections = candidates.some(
    (candidate) => Object.keys(candidate.fields).length > 0,
  );

  return candidates
    .filter((candidate) => {
      if (hasFieldCorrections) {
        return Object.keys(candidate.fields).length > 0;
      }
      return candidate.item.review_status !== newStatus;
    })
    .map(({ item, fields }) => {
      const body: EvidencePatchRequest = {
        fields,
        new_status: newStatus,
      };
      if (trimmedReason) {
        body.change_reason = trimmedReason;
      }

      return {
        canonicalEvidenceId: item.canonical_evidence_id,
        body,
      };
    });
}
