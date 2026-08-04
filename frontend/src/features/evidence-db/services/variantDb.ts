import type {
  EvidenceSearchQuery,
  EvidenceSearchResponse,
  EvidenceGroupDetailResponse,
} from "@/features/evidence-search/types/evidenceSearch";
import {
  readCachedEvidenceSearch as _readCachedEvidenceSearch,
  searchEvidence as _searchEvidence,
  getEvidenceGroupDetail,
} from "@/features/evidence-search/services/evidenceSearch";

// Backend caps `page_size` at 1000 (see /evidence/search), so a single call
// silently truncates once the corpus grows past 1000 evidence groups. That
// truncation dropped rows past the window — including many non-English (e.g.
// Chinese) documents — so client-side language filters found nothing. Page
// through the full result set instead.
const MAX_PAGE_SIZE = 1000;
const MAX_PAGES = 50; // Safety cap: 50k groups is well beyond current corpus.

interface FetchAllEvidenceOptions {
  cacheScope?: string;
  refresh?: boolean;
}

function pagedQuery(
  query: EvidenceSearchQuery,
  page: number,
): EvidenceSearchQuery {
  return { ...query, page, page_size: MAX_PAGE_SIZE };
}

/**
 * Fetch all evidence search results for aggregation.
 *
 * Pages through the API until the full result set is loaded, because the
 * backend limits each response to {@link MAX_PAGE_SIZE} groups. Aggregation and
 * filtering happen client-side, so a partial fetch would hide entire slices of
 * the corpus (e.g. languages whose documents sort past the first page).
 */
export async function fetchAllEvidence(
  query: EvidenceSearchQuery = {},
  options: FetchAllEvidenceOptions = {},
): Promise<EvidenceSearchResponse> {
  const first = await _searchEvidence(pagedQuery(query, 1), undefined, options);
  const total = first.total;
  const items = [...first.items];

  const totalPages = Math.min(Math.ceil(total / MAX_PAGE_SIZE), MAX_PAGES);
  for (let page = 2; page <= totalPages; page += 1) {
    const next = await _searchEvidence(pagedQuery(query, page), undefined, options);
    items.push(...next.items);
    if (next.items.length === 0) break;
  }

  return { items, total, page: 1, page_size: items.length };
}

/** Rebuild the aggregate response only when every required page is cached. */
export function readCachedAllEvidence(
  query: EvidenceSearchQuery = {},
  cacheScope?: string,
): EvidenceSearchResponse | undefined {
  const first = _readCachedEvidenceSearch(
    pagedQuery(query, 1),
    undefined,
    cacheScope,
  );
  if (!first) return undefined;

  const items = [...first.items];
  const totalPages = Math.min(
    Math.ceil(first.total / MAX_PAGE_SIZE),
    MAX_PAGES,
  );
  for (let page = 2; page <= totalPages; page += 1) {
    const next = _readCachedEvidenceSearch(
      pagedQuery(query, page),
      undefined,
      cacheScope,
    );
    if (!next || next.items.length === 0) return undefined;
    items.push(...next.items);
  }

  return { items, total: first.total, page: 1, page_size: items.length };
}

/**
 * Fetch evidence group detail, optionally scoped to a specific source document.
 *
 * ``group_id`` values are NOT unique per source document — the same
 * ``gene=<G>|variant=<V>`` string can appear across many papers.  Passing
 * ``sourceDocumentId`` ensures the response contains only items from that
 * particular document.
 */
export async function fetchEvidenceGroupDetail(
  groupId: string,
  sourceDocumentId?: string,
): Promise<EvidenceGroupDetailResponse> {
  return getEvidenceGroupDetail(groupId, sourceDocumentId);
}
