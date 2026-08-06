import type {
  EvidenceSearchQuery,
  EvidenceSearchResponse,
  EvidenceSearchResult,
  EvidenceGroupDetailResponse,
} from "@/features/evidence-search/types/evidenceSearch";
import {
  readCachedEvidenceSearch as _readCachedEvidenceSearch,
  searchEvidence as _searchEvidence,
  getEvidenceGroupDetail,
} from "@/features/evidence-search/services/evidenceSearch";
import { apiClient, readCachedApiResponse } from "@/lib/api/client";
import type {
  ClassificationLevel,
  VariantIndexData,
  VariantIndexEntry,
  VariantIndexFilters,
} from "../types/variantDb";

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

// ── Server-side variant index (GET /evidence/variants) ───────────────────
//
// The variant index is now paginated server-side: the backend aggregates
// evidence groups into variant rows and returns only the current page plus
// pre-filter stats and autocomplete candidates. The response uses snake_case
// (matching the rest of the API); the mappers below convert it to the
// camelCase VariantIndexEntry shape consumed across the UI.

interface VariantIndexEntryRaw {
  variant_slug: string;
  gene: string;
  variant: string;
  disease: string;
  classification: string;
  classification_level: ClassificationLevel;
  evidence_group_count: number;
  literature_count: number;
  avg_confidence: number;
  field_count: number;
  category_distribution: Record<string, number>;
  review_status: string;
  review_progress: {
    total: number;
    reviewed: number;
    approved: number;
    corrected: number;
    rejected: number;
    provisional: number;
    reviewed_percent: number;
  };
  created_at: string | null;
  group_ids: string[];
  source_document_ids: string[];
  source_languages: string[];
  group_document_pairs: Array<{ group_id: string; source_document_id: string }>;
  representative: EvidenceSearchResult;
}

interface VariantSearchResponseRaw {
  items: VariantIndexEntryRaw[];
  total: number;
  page: number;
  page_size: number;
  stats: {
    total_variants: number;
    total_evidence_groups: number;
    total_literature: number;
    avg_confidence: number;
    classification_distribution: Record<ClassificationLevel, number>;
  };
  candidates: { genes: string[]; variants: string[]; diseases: string[] };
}

function buildVariantIndexParams(
  filters: VariantIndexFilters,
): Record<string, string | number> {
  const params: Record<string, string | number> = {
    page: filters.page,
    page_size: filters.pageSize,
  };
  if (filters.gene) params.gene = filters.gene;
  if (filters.variant) params.variant = filters.variant;
  if (filters.disease) params.disease = filters.disease;
  if (filters.classification) params.classification = filters.classification;
  if (filters.reviewStatus) params.review_status = filters.reviewStatus;
  if (filters.sourceLanguage) params.source_language = filters.sourceLanguage;
  if (filters.sortBy) params.sort_by = filters.sortBy;
  if (filters.sortOrder) params.sort_order = filters.sortOrder;
  return params;
}

function mapVariantIndexEntry(raw: VariantIndexEntryRaw): VariantIndexEntry {
  const rp = raw.review_progress;
  return {
    variantSlug: raw.variant_slug,
    gene: raw.gene,
    variant: raw.variant,
    disease: raw.disease,
    classification: raw.classification,
    classificationLevel: raw.classification_level,
    evidenceGroupCount: raw.evidence_group_count,
    literatureCount: raw.literature_count,
    avgConfidence: raw.avg_confidence,
    fieldCount: raw.field_count,
    categoryDistribution: raw.category_distribution,
    reviewStatus: raw.review_status,
    reviewProgress: {
      total: rp.total,
      reviewed: rp.reviewed,
      approved: rp.approved,
      corrected: rp.corrected,
      rejected: rp.rejected,
      provisional: rp.provisional,
      reviewedPercent: rp.reviewed_percent,
    },
    createdAt: raw.created_at,
    groupIds: raw.group_ids,
    sourceDocumentIds: raw.source_document_ids,
    sourceLanguages: raw.source_languages,
    groupDocumentPairs: raw.group_document_pairs.map((p) => ({
      groupId: p.group_id,
      sourceDocumentId: p.source_document_id,
    })),
    representative: raw.representative,
  };
}

function mapVariantSearchResponse(raw: VariantSearchResponseRaw): VariantIndexData {
  return {
    items: raw.items.map(mapVariantIndexEntry),
    total: raw.total,
    page: raw.page,
    pageSize: raw.page_size,
    stats: {
      totalVariants: raw.stats.total_variants,
      totalEvidenceGroups: raw.stats.total_evidence_groups,
      totalLiterature: raw.stats.total_literature,
      avgConfidence: raw.stats.avg_confidence,
      classificationDistribution: raw.stats.classification_distribution,
    },
    candidates: {
      genes: raw.candidates.genes,
      variants: raw.candidates.variants,
      diseases: raw.candidates.diseases,
    },
  };
}

/**
 * Fetch one page of variant rows from the server-side aggregation endpoint.
 *
 * Unlike {@link fetchAllEvidence}, this downloads only the current page (~24
 * rows) plus lightweight stats and autocomplete candidates - the backend does
 * the group→variant aggregation, filtering, and pagination.
 */
export async function fetchVariantIndex(
  filters: VariantIndexFilters,
  options: FetchAllEvidenceOptions = {},
): Promise<VariantIndexData> {
  const { data } = await apiClient.get<VariantSearchResponseRaw>(
    "/evidence/variants",
    {
      params: buildVariantIndexParams(filters),
      responseCache: { scope: options.cacheScope },
    },
  );
  return mapVariantSearchResponse(data);
}

/** Read a cached variant-index page for instant render on mount. */
export function readCachedVariantIndex(
  filters: VariantIndexFilters,
  cacheScope?: string,
): VariantIndexData | undefined {
  const raw = readCachedApiResponse<VariantSearchResponseRaw>(
    "/evidence/variants",
    buildVariantIndexParams(filters),
    cacheScope,
  );
  return raw ? mapVariantSearchResponse(raw) : undefined;
}
