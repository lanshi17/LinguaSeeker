import type {
  EvidenceGroupDetailResponse,
  EvidenceSearchResult,
} from "../types/evidenceSearch";

export interface LiteratureEvidenceRow {
  documentId: string;
  representativeGroupId: string;
  title?: string | null;
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
  createdAt?: string | null;
}

interface MutableLiteratureEvidenceRow extends LiteratureEvidenceRow {
  confidenceTotal: number;
  confidenceWeight: number;
  statuses: Set<string>;
  keys: Set<string>;
}

function appendUnique(values: string[], value?: string | null) {
  const normalized = value?.trim();
  if (!normalized || normalized === "\u2014" || values.includes(normalized)) {
    return;
  }
  values.push(normalized);
}

function normalizeDoi(value?: string | null) {
  const normalized = value
    ?.trim()
    .toLowerCase()
    .replace(/^doi:\s*/, "")
    .replace(/^https?:\/\/(dx\.)?doi\.org\//, "");
  return normalized || null;
}

function normalizePmid(value?: string | null) {
  const normalized = value?.trim().replace(/^pmid:\s*/i, "");
  return normalized || null;
}

function normalizeTitle(value?: string | null) {
  const normalized = value?.normalize("NFKC").trim().toLowerCase().replace(/\s+/g, " ");
  if (!normalized || normalized.length < 24) {
    return null;
  }
  return normalized;
}

function literatureKeys(item: EvidenceSearchResult) {
  const keys: string[] = [];
  const pmid = normalizePmid(item.pmid);
  const doi = normalizeDoi(item.doi);
  const title = normalizeTitle(item.title);
  const documentId = item.source_document_id || item.group_id;

  if (pmid) {
    keys.push(`pmid:${pmid}`);
  }
  if (doi) {
    keys.push(`doi:${doi}`);
  }
  if (title) {
    keys.push(`title:${title}`);
  }
  keys.push(`document:${documentId}`);
  return keys;
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

function selectLatestCreatedAt(
  current: string | null | undefined,
  candidate: string | null | undefined,
) {
  if (!candidate) {
    return current ?? null;
  }
  if (!current || Date.parse(candidate) > Date.parse(current)) {
    return candidate;
  }
  return current;
}

function mergeMutableRows(
  target: MutableLiteratureEvidenceRow,
  source: MutableLiteratureEvidenceRow,
) {
  for (const value of source.genes) {
    appendUnique(target.genes, value);
  }
  for (const value of source.variants) {
    appendUnique(target.variants, value);
  }
  for (const value of source.diseases) {
    appendUnique(target.diseases, value);
  }
  for (const value of source.classifications) {
    appendUnique(target.classifications, value);
  }
  for (const status of source.statuses) {
    target.statuses.add(status);
  }
  for (const key of source.keys) {
    target.keys.add(key);
  }

  target.title = target.title || source.title;
  target.pmid = target.pmid || source.pmid;
  target.doi = target.doi || source.doi;
  target.createdAt = selectLatestCreatedAt(target.createdAt, source.createdAt);
  target.fieldCount += source.fieldCount;
  target.groupCount += source.groupCount;
  target.confidenceTotal += source.confidenceTotal;
  target.confidenceWeight += source.confidenceWeight;
}

function appendResultToRow(
  row: MutableLiteratureEvidenceRow,
  item: EvidenceSearchResult,
) {
  if (!row.title && item.title?.trim()) {
    row.title = item.title;
  }
  if (!row.pmid && item.pmid?.trim()) {
    row.pmid = item.pmid;
  }
  if (!row.doi && item.doi?.trim()) {
    row.doi = item.doi;
  }
  row.createdAt = selectLatestCreatedAt(row.createdAt, item.created_at);

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

export function buildLiteratureRows(
  results: EvidenceSearchResult[],
): LiteratureEvidenceRow[] {
  const rows: MutableLiteratureEvidenceRow[] = [];
  const rowsByKey = new Map<string, MutableLiteratureEvidenceRow>();

  for (const item of results) {
    const documentId = item.source_document_id || item.group_id;
    const keys = literatureKeys(item);
    const matchingRows = new Set<MutableLiteratureEvidenceRow>();
    for (const key of keys) {
      const existing = rowsByKey.get(key);
      if (existing) {
        matchingRows.add(existing);
      }
    }

    let row = Array.from(matchingRows)[0];
    if (!row) {
      row = {
        documentId,
        representativeGroupId: item.group_id,
        title: item.title,
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
        createdAt: item.created_at ?? null,
        confidenceTotal: 0,
        confidenceWeight: 0,
        statuses: new Set<string>(),
        keys: new Set<string>(),
      };
      rows.push(row);
    } else if (matchingRows.size > 1) {
      for (const duplicateRow of matchingRows) {
        if (duplicateRow === row) {
          continue;
        }
        mergeMutableRows(row, duplicateRow);
        rows.splice(rows.indexOf(duplicateRow), 1);
        for (const key of duplicateRow.keys) {
          rowsByKey.set(key, row);
        }
      }
    }

    for (const key of keys) {
      row.keys.add(key);
      rowsByKey.set(key, row);
    }
    appendResultToRow(row, item);
  }

  return rows.map((row) => {
    const { confidenceTotal, confidenceWeight, statuses, keys, ...publicRow } = row;
    void keys;
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
