/** Query parameters for evidence search. */
export interface EvidenceSearchQuery {
  gene?: string;
  variant?: string;
  disease?: string;
  pmid?: string;
  doi?: string;
  page?: number;
  page_size?: number;
}

/**
 * A single evidence search result (pivoted from field-level extractions).
 */
export interface EvidenceSearchResult {
  group_id: string;
  source_document_id: string;
  pmid?: string | null;
  doi?: string | null;
  gene?: string | null;
  variant?: string | null;
  disease?: string | null;
  classification?: string | null;
  field_count: number;
  avg_confidence?: number | null;
  review_status: string;
  canonical_evidence_id?: string | null;
}

/** GET /api/v1/evidence/search response. */
export interface EvidenceSearchResponse {
  items: EvidenceSearchResult[];
  total: number;
  page: number;
  page_size: number;
}
