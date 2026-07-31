import type {
  EvidenceSearchQuery,
  EvidenceSearchResponse,
  EvidenceGroupDetailResponse,
} from "@/features/evidence-search/types/evidenceSearch";
import {
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
): Promise<EvidenceSearchResponse> {
  const first = await _searchEvidence(query, { page: 1, page_size: MAX_PAGE_SIZE });
  const total = first.total;
  const items = [...first.items];

  const totalPages = Math.min(Math.ceil(total / MAX_PAGE_SIZE), MAX_PAGES);
  for (let page = 2; page <= totalPages; page += 1) {
    const next = await _searchEvidence(query, { page, page_size: MAX_PAGE_SIZE });
    items.push(...next.items);
    if (next.items.length === 0) break;
  }

  return { items, total, page: 1, page_size: items.length };
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
