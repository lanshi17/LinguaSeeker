/** Query parameters for evidence search. */
export interface EvidenceSearchQuery {
  /** Gene name (case-insensitive partial match on active_payload.gene). */
  gene?: string;
  /** Variant description (case-insensitive partial match). */
  variant?: string;
  /** Disease name (case-insensitive partial match). */
  disease?: string;
  /** PubMed ID (exact match). */
  pmid?: string;
  /** Max results (default 50). */
  limit?: number;
}

/**
 * A single evidence search result from the frontend_search_index table.
 *
 * Maps to backend contracts.EvidenceSearchResult.
 */
export interface EvidenceSearchResult {
  canonical_evidence_id: string;
  pmid?: string | null;
  doi?: string | null;
  gene_ids: string[];
  variant_ids: string[];
  field_id: string;
  review_status: string;
  current_best_confidence?: number | null;
  /** Denormalized evidence payload from canonical_evidence_items.active_payload. */
  active_payload: EvidencePayload;
}

/**
 * The active_payload JSONB structure.
 *
 * Maps to backend contracts.EvidenceCardPayload.
 */
export interface EvidencePayload {
  gene?: string;
  variant?: string;
  phenotype?: string;
  disease?: string;
  classification?: string;
  evidence_strength?: string;
  evidence_type?: string;
  functional_impact?: string;
  inheritance_pattern?: string;
  zygosity?: string;
  references?: string[];
  summary?: string;
  gene_ids?: string[];
  variant_ids?: string[];
  entity_ids?: string[];
  search_text?: string;
}

/** GET /api/v1/evidence/search response. */
export interface EvidenceSearchResponse {
  items: EvidenceSearchResult[];
  total: number;
}
