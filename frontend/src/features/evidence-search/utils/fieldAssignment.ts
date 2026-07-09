import type { EvidenceFieldSpec } from "@/lib/constants/evidenceFields";
import type {
  EvidenceGroupDetailResponse,
  EvidenceGroupItem,
  EvidencePatchRequest,
  ReviewStatusValue,
} from "../types/evidenceSearch";

export type EvidenceCardField =
  | "gene"
  | "variant"
  | "phenotype"
  | "disease"
  | "classification"
  | "evidence_strength"
  | "evidence_type"
  | "functional_impact"
  | "inheritance_pattern"
  | "zygosity"
  | "references"
  | "summary";

export interface FieldTypeOption {
  fieldId: string;
  label: string;
  category?: string | null;
}

export interface FieldAssignmentPatch {
  canonicalEvidenceId: string;
  cardField: EvidenceCardField;
  body: EvidencePatchRequest;
}

const SUMMARY_CARD_FIELDS = new Set<EvidenceCardField>([
  "gene",
  "variant",
  "disease",
  "classification",
]);

const FIELD_ID_TO_CARD_FIELD: Record<string, EvidenceCardField> = {
  "A.gene_symbol": "gene",
  "B.disease_diagnosis": "disease",
  "B.clinical_diagnosis": "disease",
  "J.authority_classification": "classification",
};

const EVIDENCE_CARD_FIELDS = new Set<EvidenceCardField>([
  "gene",
  "variant",
  "phenotype",
  "disease",
  "classification",
  "evidence_strength",
  "evidence_type",
  "functional_impact",
  "inheritance_pattern",
  "zygosity",
  "references",
  "summary",
]);

export function cardFieldForFieldId(fieldId: string): EvidenceCardField | null {
  if (EVIDENCE_CARD_FIELDS.has(fieldId as EvidenceCardField)) {
    return fieldId as EvidenceCardField;
  }
  if (fieldId.startsWith("A.variant_hgvs_") || fieldId === "A.variant_legacy_name") {
    return "variant";
  }
  return FIELD_ID_TO_CARD_FIELD[fieldId] ?? null;
}

export function buildAssignableFieldTypes(
  items: EvidenceGroupItem[],
  specs: EvidenceFieldSpec[],
): FieldTypeOption[] {
  const specsByFieldId = new Map(specs.map((spec) => [spec.fieldId, spec]));
  const seenFieldIds = new Set<string>();
  const options: FieldTypeOption[] = [];

  for (const item of items) {
    if (seenFieldIds.has(item.field_id) || !cardFieldForFieldId(item.field_id)) {
      continue;
    }
    seenFieldIds.add(item.field_id);
    const spec = specsByFieldId.get(item.field_id);
    options.push({
      fieldId: item.field_id,
      label: item.field_name ?? spec?.fieldName ?? item.field_id,
      category: item.category ?? spec?.categoryId ?? null,
    });
  }

  return options;
}

export function buildFieldAssignmentPatch(
  items: EvidenceGroupItem[],
  selectedText: string,
  fieldId: string,
): FieldAssignmentPatch | null {
  const cardField = cardFieldForFieldId(fieldId);
  if (!cardField) {
    return null;
  }

  const targetItem =
    items.find((item) => item.field_id === fieldId) ??
    items.find((item) => cardFieldForFieldId(item.field_id) === cardField);
  if (!targetItem) {
    return null;
  }

  return {
    canonicalEvidenceId: targetItem.canonical_evidence_id,
    cardField,
    body: {
      fields: { [cardField]: selectedText },
      change_reason: `Text selection assignment to ${fieldId}`,
    },
  };
}

function updateStatusCounts(
  counts: Record<string, number>,
  oldStatus: string,
  newStatus: string,
) {
  if (oldStatus === newStatus) {
    return counts;
  }

  const next = { ...counts };
  const oldCount = next[oldStatus] ?? 0;
  if (oldCount <= 1) {
    delete next[oldStatus];
  } else {
    next[oldStatus] = oldCount - 1;
  }
  next[newStatus] = (next[newStatus] ?? 0) + 1;
  return next;
}

export function applyReviewStatusToDetail(
  detail: EvidenceGroupDetailResponse | undefined,
  evidenceId: string,
  status: ReviewStatusValue,
): EvidenceGroupDetailResponse | undefined {
  if (!detail) {
    return detail;
  }

  const targetItem = detail.items.find(
    (item) => item.canonical_evidence_id === evidenceId,
  );
  if (!targetItem || targetItem.review_status === status) {
    return detail;
  }

  return {
    ...detail,
    distribution: {
      ...detail.distribution,
      by_status: updateStatusCounts(
        detail.distribution.by_status,
        targetItem.review_status,
        status,
      ),
    },
    items: detail.items.map((item) =>
      item.canonical_evidence_id === evidenceId
        ? { ...item, review_status: status }
        : item,
    ),
  };
}

export function applyFieldAssignmentToDetail(
  detail: EvidenceGroupDetailResponse | undefined,
  assignment: FieldAssignmentPatch,
  selectedText: string,
  newStatus?: ReviewStatusValue,
): EvidenceGroupDetailResponse | undefined {
  if (!detail) {
    return detail;
  }

  const targetItem = detail.items.find(
    (item) => item.canonical_evidence_id === assignment.canonicalEvidenceId,
  );
  if (!targetItem) {
    return detail;
  }

  const nextStatus = newStatus ?? targetItem.review_status;
  const nextDetail: EvidenceGroupDetailResponse = {
    ...detail,
    distribution: {
      ...detail.distribution,
      by_status: updateStatusCounts(
        detail.distribution.by_status,
        targetItem.review_status,
        nextStatus,
      ),
    },
    items: detail.items.map((item) =>
      item.canonical_evidence_id === assignment.canonicalEvidenceId
        ? { ...item, value: selectedText, review_status: nextStatus }
        : item,
    ),
  };

  if (SUMMARY_CARD_FIELDS.has(assignment.cardField)) {
    return {
      ...nextDetail,
      [assignment.cardField]: selectedText,
    };
  }

  return nextDetail;
}
