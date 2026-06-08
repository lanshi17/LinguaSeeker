import type {
  EvidenceGroupDetailResponse,
  EvidenceSearchResult,
} from "../types/evidenceSearch";

export interface LiteratureEvidenceRow {
  documentId: string;
  representativeGroupId: string;
  pmid?: string | null;
  doi?: string | null;
  genes: string[];
  variants: string[];
  diseases: string[];
  classifications: string[];
  fieldCount: number;
  groupCount: number;
  avgConfidence?: number | null;
  reviewStatus: string;
}

interface MutableLiteratureEvidenceRow extends LiteratureEvidenceRow {
  confidenceTotal: number;
  confidenceWeight: number;
  statuses: Set<string>;
}

function appendUnique(values: string[], value?: string | null) {
  const normalized = value?.trim();
  if (!normalized || normalized === "\u2014" || values.includes(normalized)) {
    return;
  }
  values.push(normalized);
}

function finalizeReviewStatus(statuses: Set<string>) {
  if (statuses.size === 0) {
    return "unknown";
  }
  if (statuses.size === 1) {
    return Array.from(statuses)[0];
  }
  return "mixed";
}

export function buildLiteratureRows(
  results: EvidenceSearchResult[],
): LiteratureEvidenceRow[] {
  const rows = new Map<string, MutableLiteratureEvidenceRow>();

  for (const item of results) {
    const documentId = item.source_document_id || item.group_id;
    let row = rows.get(documentId);

    if (!row) {
      row = {
        documentId,
        representativeGroupId: item.group_id,
        pmid: item.pmid,
        doi: item.doi,
        genes: [],
        variants: [],
        diseases: [],
        classifications: [],
        fieldCount: 0,
        groupCount: 0,
        avgConfidence: null,
        reviewStatus: "unknown",
        confidenceTotal: 0,
        confidenceWeight: 0,
        statuses: new Set<string>(),
      };
      rows.set(documentId, row);
    }

    appendUnique(row.genes, item.gene);
    appendUnique(row.variants, item.variant);
    appendUnique(row.diseases, item.disease);
    appendUnique(row.classifications, item.classification);

    row.fieldCount += item.field_count;
    row.groupCount += 1;
    if (item.review_status) {
      row.statuses.add(item.review_status);
    }
    if (item.avg_confidence != null) {
      const weight = Math.max(1, item.field_count);
      row.confidenceTotal += item.avg_confidence * weight;
      row.confidenceWeight += weight;
    }
  }

  return Array.from(rows.values()).map((row) => {
    const { confidenceTotal, confidenceWeight, statuses, ...publicRow } = row;
    return {
      ...publicRow,
      avgConfidence:
        confidenceWeight > 0 ? confidenceTotal / confidenceWeight : null,
      reviewStatus: finalizeReviewStatus(statuses),
    };
  });
}

export function findInitialEvidenceId(
  detail: EvidenceGroupDetailResponse,
  requestedEvidenceId?: string | null,
) {
  if (
    requestedEvidenceId &&
    detail.items.some(
      (item) => item.canonical_evidence_id === requestedEvidenceId,
    )
  ) {
    return requestedEvidenceId;
  }

  const traceableIds = new Set(
    detail.traces.map((trace) => trace.canonical_evidence_id),
  );
  return (
    detail.items.find((item) =>
      traceableIds.has(item.canonical_evidence_id),
    )?.canonical_evidence_id ??
    detail.items[0]?.canonical_evidence_id ??
    null
  );
}

export function buildBilingualCompareHref(
  groupId: string,
  evidenceId?: string | null,
) {
  const params = new URLSearchParams({ groupId, view: "compare" });
  if (evidenceId) {
    params.set("evidenceId", evidenceId);
  }
  return `/evidence/detail?${params.toString()}`;
}
